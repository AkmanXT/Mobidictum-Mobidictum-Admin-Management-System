import { chromium, Browser, Page } from 'playwright';
import fs from 'fs';
import path from 'path';
function escapeRegex(source: string): string {
  return source.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function normalizeCodeText(value: string): string {
  return value
    .trim()
    .toUpperCase()
    .replace(/[O]/g, '0')
    .replace(/[IL]/g, '1')
    .replace(/\s+/g, '');
}
import { AppConfig } from './config';
import { logger } from './logger';

export class FientaClient {
  private browser: Browser | null = null;
  private page: Page | null = null;
  private readonly config: AppConfig;

  constructor(config: AppConfig) {
    this.config = config;
  }

  async updateExistingCodes(records: Array<Record<string, string>>, percent: number): Promise<void> {
    const page = this.requirePage();
    const discountsUrl = this.config.discountsUrl || `${this.config.fientaBaseUrl}/my/events/discounts`;
    logger.info({ count: records.length, percent }, 'Updating existing discount codes to target percent');

    // Precompute descriptions per email group if available
    const totalsByEmail = new Map<string, number>();
    for (const r of records) {
      const key = String(r.email || '').toLowerCase();
      if (!key) continue;
      const idx = Number(r.ticket_index || 0) || 0;
      totalsByEmail.set(key, Math.max(totalsByEmail.get(key) || 0, idx));
    }

    for (const record of records) {
      const code = String(record.code || '').trim();
      if (!code) continue;
      try {
        await page.goto(`${discountsUrl}?search=${encodeURIComponent(code)}`);
        await page.waitForLoadState('networkidle');
        const link = page.locator('a[href*="/discounts/"]').filter({ hasText: code }).first();
        if (!(await link.count())) {
          logger.warn({ code }, 'Code not found for update');
          continue;
        }
        await link.click();
        await page.waitForLoadState('networkidle');

        // Update percent unit and amount
        const unitBtn = page.locator('button#type-1.btn.dropdown-toggle.type');
        if (await unitBtn.count()) {
          try {
            // If currently shows €, switch to %
            const current = (await unitBtn.textContent() || '').trim();
            if (/€/.test(current)) {
              await unitBtn.click();
              const percentBtn = page.locator('button#type-2.dropdown-item.type');
              await percentBtn.waitFor({ state: 'visible', timeout: 5000 });
              await percentBtn.click();
              // Verify
              await unitBtn.waitFor({ state: 'visible', timeout: 2000 }).catch(() => undefined);
              const after = (await unitBtn.textContent() || '').trim();
              if (!/%/.test(after)) {
                // Retry once
                await unitBtn.click().catch(() => undefined);
                await percentBtn.waitFor({ state: 'visible', timeout: 3000 }).catch(() => undefined);
                await percentBtn.click().catch(() => undefined);
              }
            }
          } catch {}
        }
        const amountInput = page.locator('input#amount[name="amount"].form-control.form-control-lg');
        if (await amountInput.count()) {
          await amountInput.focus();
          await page.keyboard.press('Control+A');
          await page.keyboard.press('Delete');
          await amountInput.type(String(percent), { delay: 10 });
          await amountInput.evaluate((el: HTMLElement) => el.blur());
        }

        // Update description
        const emailKey = String(record.email || '').toLowerCase();
        const total = totalsByEmail.get(emailKey) || Number(record.ticket_index || 1) || 1;
        const index = Number(record.ticket_index || 1) || 1;
        const desc = `#${index} of ${total} tickets for ${record.studio || ''}, ${percent}% discount`;
        if (record.studio) {
          const titleInput = page.locator('input#title[name="title"], textarea#title[name="title"]');
          if (await titleInput.count()) {
            await titleInput.focus();
            await page.keyboard.press('Control+A');
            await page.keyboard.press('Delete');
            await titleInput.type(desc, { delay: 5 });
            await titleInput.evaluate((el: HTMLElement) => el.blur());
          }
        }

        // Save
        const saveBtn = page.locator('button:has-text("Update"), button:has-text("Save"), [type="submit"]:has-text("Update"), [type="submit"]:has-text("Save")').first();
        if (await saveBtn.count()) {
          await saveBtn.scrollIntoViewIfNeeded();
          await saveBtn.click();
        } else {
          await page.keyboard.press('Control+Enter');
        }
        await Promise.race([
          page.waitForURL(/\/discounts(\?|\/|$)/, { timeout: 2000 }).catch(() => undefined),
          page.waitForTimeout(1000),
        ]);
        logger.info({ code }, 'Updated');
      } catch (err) {
        logger.error({ err, code }, 'Failed to update code');
      }
    }
  }
  async start(): Promise<void> {
    this.browser = await chromium.launch({ headless: this.config.headless });
    const storagePath = this.config.storageStatePath;
    const storageExists = !!storagePath && fs.existsSync(storagePath);
    const context = await this.browser.newContext({ storageState: storageExists ? storagePath : undefined });
    this.page = await context.newPage();
  }

  async stop(): Promise<void> {
    await this.browser?.close();
    this.browser = null;
    this.page = null;
  }

  requirePage(): Page {
    if (!this.page) throw new Error('Browser page is not initialized');
    return this.page;
  }

  async login(): Promise<void> {
    const page = this.requirePage();
    const { fientaBaseUrl, fientaEmail, fientaPassword } = this.config;

    logger.info('Logging in to Fienta...');
    // Go to target (discounts page if provided) to trigger login redirect if needed
    const initialUrl = this.config.discountsUrl || `${fientaBaseUrl}/my/events`;
    await page.goto(initialUrl);
    await page.waitForLoadState('domcontentloaded');

    // Detect login status by presence of login inputs (robust selectors)
    const emailInput = page.locator('input[type="email"], input[name="email" i]');
    const passwordInput = page.locator('input[type="password"], input[name="password" i]');
    const loginFormVisible = (await emailInput.count()) > 0 && (await passwordInput.count()) > 0;

    if (loginFormVisible) {
      if (this.config.manualLogin) {
        // Let the user log in manually; wait until login form disappears or timeouts
        logger.info({ timeoutMs: this.config.loginTimeoutMs }, 'Waiting for manual login...');
        await page.waitForFunction(() => !document.querySelector('input[type="email"], input[name="email" i]') && !document.querySelector('input[type="password"], input[name="password" i]'), { timeout: this.config.loginTimeoutMs });
      } else {
        await emailInput.first().fill(fientaEmail);
        await passwordInput.first().fill(fientaPassword);
        const loginBtn = page.locator('button[type="submit"], input[type="submit"], button:has-text("Log in"), button:has-text("Login"), button:has-text("Sign in")').first();
        if (await loginBtn.count()) {
          await loginBtn.click();
        } else {
          await page.keyboard.press('Enter');
        }
        await page.waitForLoadState('networkidle');
      }
      // save storage state
      if (this.config.storageStatePath) {
        const dir = path.dirname(this.config.storageStatePath);
        if (!fs.existsSync(dir)) {
          fs.mkdirSync(dir, { recursive: true });
        }
        await page.context().storageState({ path: this.config.storageStatePath });
      }
      logger.info('Logged in.');
    } else {
      logger.info('Already logged in, continuing.');
    }
  }

  // Placeholder: implement according to actual Fienta UI for codes management
  async createOrCustomizeCodes(records: Array<Record<string, string>>): Promise<void> {
    const page = this.requirePage();
    logger.info({ count: records.length }, 'Creating new discount codes');

    // Precompute total tickets per recipient (by email) to write a useful description
    const totalsByEmail = new Map<string, number>();
    for (const r of records) {
      const key = String(r.email || '').toLowerCase();
      if (!key) continue;
      const current = totalsByEmail.get(key) || 0;
      const idx = Number(r.ticket_index || 0) || 0;
      totalsByEmail.set(key, Math.max(current, idx));
    }

    for (const record of records) {
      if (this.config.dryRun) {
        logger.info({ record }, 'DRY RUN - would create code');
        continue;
      }
      try {
        const code = String(record.code || '').trim();
        if (!code) {
          logger.warn({ record }, 'Skipping record without code');
          continue;
        }
        const orderLimit = String(record.order_limit || '1');
        const ticketLimit = String(record.ticket_limit || '1');
        const discountsUrl = this.config.discountsUrl || `${this.config.fientaBaseUrl}/my/events/discounts`;
        const emailKey = String(record.email || '').toLowerCase();
        const totalForThisContact = totalsByEmail.get(emailKey) || Number(record.ticket_index || 1) || 1;
        const idxForThis = Number(record.ticket_index || 1) || 1;
        const description = `#${idxForThis} of ${totalForThisContact} tickets for ${record.studio || ''}, 100% discount`;

        // Go to discounts list
        await page.goto(discountsUrl);
        await page.waitForLoadState('networkidle');

        // Click exact Add code link you provided, fallback to menu/new url
        let clicked = false;
        const addHref = page.locator('a[href$="/discounts/create"], a[href*="/discounts/create"]').first();
        if (await addHref.count()) {
          try { await addHref.scrollIntoViewIfNeeded(); await addHref.click(); await page.waitForLoadState('networkidle'); clicked = true; } catch {}
        }
        if (!clicked) {
          const bulkMenu = page.locator('a.btn.btn-transparent.btn-narrow').first();
          if (await bulkMenu.count()) {
            try { await bulkMenu.click(); } catch {}
            const addInMenu = page.locator('a.dropdown-item[href*="/discounts/create"]').first();
            if (await addInMenu.count()) {
              try { await addInMenu.click(); await page.waitForLoadState('networkidle'); clicked = true; } catch {}
            }
          }
        }
        if (!clicked) {
          await page.goto(`https://fienta.com/my/events/118714/discounts/create`);
          await page.waitForLoadState('networkidle');
        }

        // Fill Code field (exact selectors from provided HTML)
        const codeField = page.locator('input#code[name="code"].form-control.form-control-lg');
        await codeField.waitFor({ state: 'visible', timeout: 20000 });
        await codeField.focus();
        await page.keyboard.press('Control+A');
        await page.keyboard.press('Delete');
        await codeField.type(code, { delay: 10 });
        await codeField.evaluate((el: HTMLElement) => el.blur());

        // Discount amount and unit (switch to % then set 40)
        const amountInput = page.locator('input#amount[name="amount"].form-control.form-control-lg');
        if (await amountInput.count()) {
          await amountInput.focus();
          await page.keyboard.press('Control+A');
          await page.keyboard.press('Delete');
          await amountInput.type('40', { delay: 10 });
          await amountInput.evaluate((el: HTMLElement) => el.blur());
        }
        const unitDropdown = page.locator('button#type-1.btn.dropdown-toggle.type');
        if (await unitDropdown.count()) {
          try {
            await unitDropdown.click();
            const percentItem = page.locator('button#type-2.dropdown-item.type');
            await percentItem.waitFor({ state: 'visible', timeout: 5000 });
            await percentItem.click();
          } catch {}
        }

        // Limits
        const orderInput = page.locator('input#usage_limit[name="usage_limit"]');
        if (await orderInput.count()) {
          await orderInput.focus();
          await page.keyboard.press('Control+A');
          await page.keyboard.press('Delete');
          await orderInput.type(orderLimit, { delay: 5 });
          await orderInput.evaluate((el: HTMLElement) => el.blur());
        }
        const ticketInput = page.locator('input#ticket_limit[name="ticket_limit"]');
        if (await ticketInput.count()) {
          await ticketInput.focus();
          await page.keyboard.press('Control+A');
          await page.keyboard.press('Delete');
          await ticketInput.type(ticketLimit, { delay: 5 });
          await ticketInput.evaluate((el: HTMLElement) => el.blur());
        }

        // Internal description (title)
        const titleInput = page.locator('input#title[name="title"], textarea#title[name="title"]');
        if (await titleInput.count()) {
          await titleInput.focus();
          await page.keyboard.press('Control+A');
          await page.keyboard.press('Delete');
          await titleInput.type(description.replace('100%','40%'), { delay: 5 });
          await titleInput.evaluate((el: HTMLElement) => el.blur());
        }

        // Save (Create)
        const saveBtn = page.locator('button:has-text("Create"), button:has-text("Save"), [type="submit"]:has-text("Create"), [type="submit"]:has-text("Save")').first();
        if (await saveBtn.count()) {
          await saveBtn.scrollIntoViewIfNeeded();
          await saveBtn.click();
        } else {
          await page.keyboard.press('Control+Enter');
        }

        // Small wait and return to list
        await Promise.race([
          page.waitForURL(/\/discounts(\?|\/|$)/, { timeout: 2000 }).catch(() => undefined),
          page.waitForTimeout(1200),
        ]);
        logger.info({ code }, 'Created discount code');
      } catch (err) {
        logger.error({ err, record }, 'Failed to create code');
      }
    }
  }

  async renameExistingCodes(pairs: Array<{ old: string; new: string }>): Promise<void> {
    const page = this.requirePage();
    logger.info({ count: pairs.length }, 'Renaming existing codes');

    const discountsUrl = this.config.discountsUrl || `${this.config.fientaBaseUrl}/my/events/discounts`;
    await page.goto(discountsUrl);
    await page.waitForLoadState('networkidle');

    for (const pair of pairs) {
      if (!pair.old || !pair.new) continue;
      if (this.config.dryRun) {
        logger.info({ pair }, 'DRY RUN - would rename code');
        continue;
      }
      try {
        async function searchAndOpenByCode(code: string): Promise<boolean> {
          try {
            // Fast path: open list with search query and click the matching discount link
            await page.goto(`${discountsUrl}?search=${encodeURIComponent(code)}`);
            await page.waitForLoadState('networkidle');

            // Prefer direct anchor that contains the code text
            const link = page
              .locator('a[href*="/discounts/"]')
              .filter({ hasText: code })
              .first();
            if (await link.count()) {
              await link.scrollIntoViewIfNeeded();
              await link.click();
              await page.waitForLoadState('networkidle');
              return true;
            }

            // Fallback: find any row containing the code and click its anchor
            const row = page.locator(`text="${code}"`).first();
            const rowEl = await row.elementHandle().catch(() => null);
            if (!rowEl) return false;
            const clicked = await rowEl.evaluate((node) => {
              const container = (node as HTMLElement).closest('[class*="row"], li, tr, div');
              if (!container) return false;
              const linkInside = container.querySelector('a[href*="/discounts/"]') as HTMLAnchorElement | null;
              if (linkInside) {
                linkInside.click();
                return true;
              }
              (container as HTMLElement).click();
              return true;
            });
            if (clicked) {
              await page.waitForLoadState('networkidle');
              return true;
            }
            return false;
          } catch {
            return false;
          }
        }

        // Try with old code; if not found, try with new code (after previous renames)
        let opened = false;
        try {
          opened = await searchAndOpenByCode(pair.old);
        } catch (e) {
          opened = false;
        }
        if (!opened) {
          logger.warn({ pair }, 'Old code not found, trying new code');
          try {
            opened = await searchAndOpenByCode(pair.new);
          } catch (e) {
            opened = false;
          }
        }
        if (!opened) {
          logger.warn({ pair }, 'Code not found in list');
          continue;
        }

        // Optionally update code name unless onlyUpdateLimit is set
        if (!this.config.onlyUpdateLimit) {
          // Edit code field - be explicit to avoid matching the checkbox labeled "Code is temporarily disabled"
          const codeField = page.locator('input#code[name="code"]');
          await codeField.waitFor({ state: 'visible', timeout: 10000 });
          await codeField.focus();
          await page.keyboard.press('Control+A');
          await page.keyboard.press('Delete');
          await codeField.type(pair.new, { delay: 20 });
          // Blur to ensure form detects change
          await codeField.evaluate((el: HTMLElement) => el.blur());
        }

        // Optionally set per-order and ticket limits if provided
        if (this.config.limitPerOrder !== undefined) {
          const value = String(this.config.limitPerOrder);
          const orderInput = page.locator('input#usage_limit[name="usage_limit"]');
          if (await orderInput.count()) {
            await orderInput.scrollIntoViewIfNeeded();
            await orderInput.focus();
            await page.keyboard.press('Control+A');
            await page.keyboard.press('Delete');
            await orderInput.type(value, { delay: 5 });
            await orderInput.evaluate((el: HTMLElement) => el.blur());
          } else {
            logger.warn({ pair }, 'Order limit input not found');
          }
        }
        if (this.config.limitPerTicket !== undefined) {
          const value = String(this.config.limitPerTicket);
          const ticketInput = page.locator('input#ticket_limit[name="ticket_limit"]');
          if (await ticketInput.count()) {
            await ticketInput.scrollIntoViewIfNeeded();
            await ticketInput.focus();
            await page.keyboard.press('Control+A');
            await page.keyboard.press('Delete');
            await ticketInput.type(value, { delay: 5 });
            await ticketInput.evaluate((el: HTMLElement) => el.blur());
          } else {
            logger.warn({ pair }, 'Ticket limit input not found');
          }
        }

        // Save (button can be labeled "Update" on Fienta)
        const saveBtn = page.locator('button:has-text("Update"), button:has-text("Save"), [type="submit"]:has-text("Update"), [type="submit"]:has-text("Save")').first();
        if (await saveBtn.count()) {
          await saveBtn.scrollIntoViewIfNeeded();
          await saveBtn.click();
        } else {
          await page.keyboard.press('Control+Enter');
        }

        // Wait briefly or for navigation back to list
        await Promise.race([
          page.waitForURL(/\/discounts(\?|\/|$)/, { timeout: 2000 }).catch(() => undefined),
          page.waitForTimeout(1200),
        ]);

        logger.info({ pair }, 'Renamed');

        // Return to list for next iteration via sidebar link
        const backLink = page.getByRole('link', { name: /discount codes/i });
        if (await backLink.count()) {
          await backLink.first().click();
          await page.waitForLoadState('networkidle');
        } else {
          await page.goto(discountsUrl);
          await page.waitForLoadState('networkidle');
        }
        // Clear list search
        const search2 = page.locator('input[name="search"]');
        if (await search2.count()) await search2.fill('');
      } catch (err) {
        logger.error({ err, pair }, 'Failed to rename');
      }
    }
  }
}


