import fs from 'fs';
import path from 'path';

type OutreachAction = 'send_new_code' | 'reject' | 'review';

interface PreviewRow {
  name: string;
  email: string;
  studio: string;
  tickets: number | null;
  action: OutreachAction;
  code_suggestion?: string | null;
  limit_per_order?: number | null;
  limit_per_ticket?: number | null;
  notes?: string;
}

interface EmailItem {
  to: string[];
  cc: string[];
  subject: string;
  text: string;
  html: string;
  metadata: Record<string, unknown>;
}

interface CodeRow {
  email: string;
  name: string;
  studio: string;
  ticket_index: number;
  code: string;
  order_limit: number;
  ticket_limit: number;
}

function ensureDir(filePath: string): void {
  fs.mkdirSync(path.dirname(path.resolve(filePath)), { recursive: true });
}

function readCsv(filePath: string): PreviewRow[] {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split(/\r?\n/).filter(l => l.trim().length > 0);
  if (lines.length <= 1) return [];
  const [headerLine, ...rows] = lines;
  const headers = headerLine.split(',').map(h => h.trim());
  const idx = (name: string) => headers.findIndex(h => h === name);

  const mapVal = (v: string) => v.replace(/^"|"$/g, '').replace(/""/g, '"');

  return rows.map(r => {
    // naive CSV split respecting simple quotes; our generator uses simple commas
    const parts = [] as string[];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < r.length; i++) {
      const ch = r[i];
      if (ch === '"') {
        inQuotes = !inQuotes;
        cur += ch;
      } else if (ch === ',' && !inQuotes) {
        parts.push(cur);
        cur = '';
      } else {
        cur += ch;
      }
    }
    parts.push(cur);

    const get = (name: string): string => mapVal(parts[idx(name)] ?? '');
    const num = (name: string): number | null => {
      const v = get(name);
      if (!v) return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };

    return {
      name: get('name'),
      email: get('email'),
      studio: get('studio'),
      tickets: num('tickets'),
      action: (get('action') as OutreachAction) || 'review',
      code_suggestion: get('code_suggestion') || null,
      limit_per_order: num('limit_per_order'),
      limit_per_ticket: num('limit_per_ticket'),
      notes: get('notes') || '',
    };
  });
}

function readCodesCsv(filePath: string): Map<string, CodeRow[]> {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split(/\r?\n/).filter(l => l.trim().length > 0);
  if (lines.length <= 1) return new Map();
  const [headerLine, ...rows] = lines;
  const headers = headerLine.split(',').map(h => h.trim());
  const idx = (name: string) => headers.findIndex(h => h === name);

  const mapVal = (v: string) => v.replace(/^"|"$/g, '').replace(/""/g, '"');
  const out = new Map<string, CodeRow[]>();

  for (const r of rows) {
    const parts = [] as string[];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < r.length; i++) {
      const ch = r[i];
      if (ch === '"') { inQuotes = !inQuotes; cur += ch; }
      else if (ch === ',' && !inQuotes) { parts.push(cur); cur = ''; }
      else { cur += ch; }
    }
    parts.push(cur);

    const get = (name: string): string => mapVal(parts[idx(name)] ?? '');
    const num = (name: string): number => {
      const v = get(name);
      const n = Number(v);
      return Number.isFinite(n) ? n : 0;
    };

    const row: CodeRow = {
      email: get('email'),
      name: get('name'),
      studio: get('studio'),
      ticket_index: num('ticket_index'),
      code: get('code'),
      order_limit: num('order_limit'),
      ticket_limit: num('ticket_limit'),
    };

    if (!row.email || !row.code) continue;
    const key = row.email.toLowerCase();
    const list = out.get(key) || [];
    list.push(row);
    out.set(key, list);
  }

  // sort codes by ticket_index per contact
  for (const [k, list] of out.entries()) {
    list.sort((a, b) => a.ticket_index - b.ticket_index);
    out.set(k, list);
  }

  return out;
}

function firstName(fullName: string): string {
  const t = (fullName || '').trim();
  if (!t) return 'there';
  return t.split(/\s+/)[0];
}

function studioOneLiner(studio: string): string {
  if (!studio) return 'We created a dedicated code for your team.';
  return `We created a dedicated code for ${studio}.`;
}

function stripDiacritics(s: string): string {
  return (s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
}

function emailFirstName(email: string): string {
  const local = (email || '').split('@')[0] || '';
  const token = (local.split(/[._+-]/)[0] || '').trim();
  if (!token) return '';
  return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
}

function namesRoughlyMatch(a: string, b: string): boolean {
  const na = stripDiacritics((a || '').trim()).toLowerCase();
  const nb = stripDiacritics((b || '').trim()).toLowerCase();
  return na !== '' && nb !== '' && na === nb;
}

function normalizeStudioBrand(studio: string): string {
  const s = studio || '';
  const repl: Array<[RegExp, string]> = [
    [/\bdigital realm entertainment,? inc\.?/i, 'Digital Realm Entertainment, Inc.'],
    [/\bbe nice games\b/i, 'Be Nice Games'],
    [/\bplay2day games\b/i, 'Play2Day Games'],
    [/\beastup inveractive\b/i, 'Eastup Interactive'],
  ];
  for (const [re, val] of repl) {
    if (re.test(s)) return val;
  }
  return s; // keep original to avoid unintended changes
}

function normalizeEventDates(s: string): string {
  let out = (s || '').trim();
  // Fix missing dash pattern like 2122 October
  out = out.replace(/\b21\s*22\s*October,?\s*Istanbul\b/i, '21–22 October, Istanbul');
  // De-duplicate Istanbul if present twice
  out = out.replace(/,\s*Istanbul\s*,\s*Istanbul\b/i, ', Istanbul');
  return out;
}

function properCase(word: string): string {
  if (!word) return word;
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
}

function generateEmail(row: PreviewRow, opts: { cc: string[]; eventName: string; eventDates: string; ticketType: string; discountsUrl?: string; codes?: CodeRow[] }): EmailItem {
  const fn = firstName(row.name);
  const codes = (opts.codes || []).map(c => c.code);
  const qty = codes.length || row.tickets || 1;
  const subjectBase = `Mobidictum Conference 2025`;
  let subject = subjectBase;
  let text = '';
  let html = '';
  const brandStudio = normalizeStudioBrand(row.studio);
  const emailFN = emailFirstName(row.email);
  // Use form response name (from source/preview) as primary greeting
  const formName = properCase(firstName(row.name));
  const greet = formName || emailFN || 'there';
  const needsNameCheck = false;
  const fixedDates = normalizeEventDates(opts.eventDates);

  if (row.action === 'send_new_code' && qty > 0) {
    // Subject per provided template
    subject = `Confirmed: ${qty === 1 ? '1 pass' : qty + ' passes'} allocated to ${brandStudio} - ${subjectBase}`;

    const codesTableHtml = `Code Ticket allowance`;
    const tableRowsHtml = codes.map(c => `<tr><td style=\"padding:6px 10px;border:1px solid #ddd;\">${c}</td><td style=\"padding:6px 10px;border:1px solid #ddd;\">1 ticket</td></tr>`).join('');
    const tableHtml = `<table cellspacing=\"0\" cellpadding=\"0\" style=\"border-collapse:collapse;\"><thead><tr><th style=\"text-align:left;padding:6px 10px;border:1px solid #ddd;\">Code</th><th style=\"text-align:left;padding:6px 10px;border:1px solid #ddd;\">Ticket allowance</th></tr></thead><tbody>${tableRowsHtml}</tbody></table>`;
    const codesListText = codes.map(c => `- ${c}  (1 ticket)`).join('\n');

    const redeemText = opts.discountsUrl ? `Redeem link: ${opts.discountsUrl}` : 'Redeem in Fienta checkout.';
    const redeemHtml = opts.discountsUrl ? `Redeem link: <a href=\"${opts.discountsUrl}\">Get your tickets here</a>` : 'Redeem in Fienta checkout.';
    const shareLineText = qty > 1 ? '\n- Share the codes within your team, one per attendee.' : '';
    const shareLineHtml = qty > 1 ? '<br/>- Share the codes within your team, one per attendee.' : '';

    // TEXT body
    const belowText = qty === 1
      ? 'Below is your unique code — valid for one ticket.'
      : 'Below are your unique codes — each is valid for one ticket.';
    text = `Hello ${greet},\n\nWe’re pleased to confirm your ticket allocation for Mobidictum Conference 2025 (${fixedDates}).\n\n${belowText}\n\nCode  Ticket allowance\n${codesListText}\n\n${redeemText}\n\nHow it works:\n- Each code can be used once to redeem 1 ticket of any type.\n- Codes are exclusive to ${brandStudio} and cannot be reused or transferred.${shareLineText}\n\nPlease redeem them soon to secure your place. We look forward to welcoming the ${brandStudio} team in Istanbul for two days of global networking, insights, and growth.\n\nBest regards,\n\nMobidictum Conference Team\n\nPS: Explore hotel discounts on our website for easier planning.`;

    // HTML body
    const belowHtml = qty === 1
      ? 'Below is your unique code — valid for one ticket.'
      : 'Below are your unique codes — each is valid for one ticket.';
    html = `Hello ${greet},<br/><br/>We’re pleased to confirm your ticket allocation for Mobidictum Conference 2025 (${fixedDates}).<br/><br/>${belowHtml}<br/><br/>${tableHtml}<br/><br/>${redeemHtml}<br/><br/><b>How it works:</b><br/>- Each code can be used once to redeem 1 ticket of any type.<br/>- Codes are exclusive to ${brandStudio} and cannot be reused or transferred.${shareLineHtml}<br/><br/>Please redeem them soon to secure your place. We look forward to welcoming the ${brandStudio} team in Istanbul for two days of global networking, insights, and growth.<br/><br/>Best regards,<br/><br/>Mobidictum Conference Team<br/><br/>PS: Explore hotel discounts on our website for easier planning.`;
  } else if (row.action === 'reject') {
    subject = `Regarding your ticket request – ${row.studio}`;
    text = `Hello ${fn},\n\nThank you for your interest in Mobidictum Conference. After reviewing the details, we’re not able to provide a code for this request.\n\nReason/context: ${row.notes || 'Not a suitable profile for this program.'}\n\nIf we missed anything, feel free to reply with additional context.\n\nBest regards,\nMobidictum Conference Team`;
    html = `Hello ${fn},<br/><br/>Thank you for your interest in Mobidictum Conference. After reviewing the details, we’re not able to provide a code for this request.<br/><br/><b>Reason/context:</b> ${row.notes || 'Not a suitable profile for this program.'}<br/><br/>If we missed anything, feel free to reply with additional context.<br/><br/>Best regards,<br/>Mobidictum Conference Team`;
  } else {
    subject = `Follow-up on your ticket request – ${row.studio}`;
    text = `Hello ${fn},\n\nThanks for reaching out to Mobidictum Conference. Could you please share a bit more about your team and needs so we can assign the right code?\n\nWhat we have so far: ${row.notes || '-'}\n\nLooking forward,\nMobidictum Conference Team`;
    html = `Hello ${fn},<br/><br/>Thanks for reaching out to Mobidictum Conference. Could you please share a bit more about your team and needs so we can assign the right code?<br/><br/><b>What we have so far:</b> ${row.notes || '-'}<br/><br/>Looking forward,<br/>Mobidictum Conference Team`;
  }

  return {
    to: [row.email].filter(Boolean),
    cc: opts.cc,
    subject,
    text,
    html,
    metadata: {
      name: row.name,
      studio: row.studio,
      tickets: row.tickets,
      action: row.action,
      codes,
      codes_count: qty,
      brand_studio: brandStudio,
      greeting: greet,
      name_mismatch: needsNameCheck,
      limit_per_order: row.limit_per_order ?? 1,
      limit_per_ticket: row.limit_per_ticket ?? (row.tickets ?? 1),
    },
  };
}

function toTxt(items: EmailItem[]): string {
  return items.map(i => [
    `TO: ${i.to.join(', ')}`,
    `CC: ${i.cc.join(', ')}`,
    `SUBJECT: ${i.subject}`,
    '',
    i.text,
    ''.padEnd(60, '-')
  ].join('\n')).join('\n');
}

function readArg(name: string, fallback?: string): string | undefined {
  const idx = process.argv.findIndex(a => a === `--${name}`);
  if (idx !== -1 && idx + 1 < process.argv.length) return process.argv[idx + 1];
  return fallback;
}

function main() {
  const previewCsv = readArg('previewCsv', 'logs/outreach_preview.csv')!;
  const outJson = readArg('outJson', 'email_outreach/outbox_preview.json')!;
  const outTxt = readArg('outTxt', 'email_outreach/outbox_preview.txt')!;
  const ccArg = readArg('cc', 'serdar@mobidictum.com,batuhan@mobidictum.com')!;
  const cc = ccArg.split(',').map(s => s.trim()).filter(Boolean);
  const eventName = readArg('eventName', 'Mobidictum Conference 2025')!;
  const eventDates = readArg('eventDates', '21–22 October, Istanbul')!;
  const ticketType = readArg('ticketType', 'Executive')!;
  const discountsUrl = readArg('discountsUrl');
  const hotelsUrl = readArg('hotelsUrl', 'https://bit.ly/mobidictum-conference-2025')!;
  const codesCsv = readArg('codesCsv', 'logs/outreach_codes.csv');

  const rows = readCsv(previewCsv);
  const codesMap = codesCsv && fs.existsSync(codesCsv) ? readCodesCsv(codesCsv) : new Map<string, CodeRow[]>();
  const onlySendNew = rows.filter(r => r.action === 'send_new_code');
  const emails = onlySendNew.map(r => {
    const codes = codesMap.get((r.email || '').toLowerCase()) || [];
    const email = generateEmail(r, { cc, eventName, eventDates, ticketType, discountsUrl, codes });
    // Replace PS with explicit conference events page wording + link
    email.text = email.text.replace(
      /PS: .*hotel discounts.*$/m,
      `PS: Explore hotel discounts on our conference events page: ${hotelsUrl}`
    );
    email.html = email.html.replace(
      /PS: .*hotel discounts.*$/,
      `PS: Explore hotel discounts on our <a href=\"${hotelsUrl}\">conference events page</a>.`
    );
    return email;
  });

  ensureDir(outJson);
  ensureDir(outTxt);
  fs.writeFileSync(outJson, JSON.stringify(emails, null, 2), 'utf8');
  fs.writeFileSync(outTxt, toTxt(emails), 'utf8');
}

main();