const { chromium } = require('playwright');
(async () => {
  const editUrl = process.argv[2];
  if (!editUrl) { console.error('No URL provided'); process.exit(2); }
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  try {
    const fs = require('fs');
    const authStatePath = 'auth/state.json';
    if (fs.existsSync(authStatePath)) {
      const authState = JSON.parse(fs.readFileSync(authStatePath, 'utf8'));
      await context.addCookies(authState.cookies || []);
    }
    console.log('Navigating to:', editUrl);
    await page.goto(editUrl);
    await page.waitForLoadState('networkidle');
    const deleteButton = page.locator('button.btn-delete, .btn-delete, button:has-text("Delete")').first();
    await deleteButton.waitFor({ state: 'visible', timeout: 10000 });
    await deleteButton.click();
    await page.waitForTimeout(1000);
    const confirm = page.locator('button:has-text("Confirm"), .btn-danger:has-text("Delete")').first();
    if (await confirm.count()) { await confirm.click(); }
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const url = page.url();
    console.log('Current URL:', url);
    if (url.includes('/discounts') && !url.includes('/edit')) {
      console.log('SUCCESS');
      process.exit(0);
    } else {
      console.log('STILL_ON_EDIT');
      process.exit(1);
    }
  } catch (e) {
    console.error('ERROR:', e.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
