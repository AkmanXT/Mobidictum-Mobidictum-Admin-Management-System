import fs from 'fs';

interface SentEntry { to: string; studio: string }
interface FollowupMessage {
  to: string[];
  cc: string[];
  subject: string;
  text: string;
  html: string;
  metadata: Record<string, unknown>;
}

function readCsv(path: string): Record<string, string>[] {
  const raw = fs.readFileSync(path, 'utf8');
  const [headerLine, ...lines] = raw.split(/\r?\n/).filter(Boolean);
  const headers = headerLine.split(',');
  return lines.map((line) => {
    const parts: string[] = [];
    let cur = '';
    let inQuotes = false;
    for (const ch of line) {
      if (ch === '"') { inQuotes = !inQuotes; cur += ch; }
      else if (ch === ',' && !inQuotes) { parts.push(cur); cur = ''; }
      else { cur += ch; }
    }
    parts.push(cur);
    const obj: Record<string, string> = {};
    headers.forEach((h, i) => {
      obj[h.trim()] = (parts[i] || '').replace(/^"|"$/g, '').replace(/""/g, '"');
    });
    return obj;
  });
}

function properCase(s: string): string { return s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : s; }
function titleCaseWords(s: string): string {
  return (s || '')
    .split(/\s+/)
    .map(word => word ? (word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()) : word)
    .join(' ');
}
function normalizeEventDates(s: string): string {
  let out = (s || '').trim();
  out = out.replace(/\b21\s*22\s*October,?\s*Istanbul\b/i, '21–22 October, Istanbul');
  out = out.replace(/,\s*Istanbul\s*,\s*Istanbul\b/i, ', Istanbul');
  return out;
}

function main() {
  const sentReportPath = process.argv.includes('--sentReport') ? process.argv[process.argv.indexOf('--sentReport') + 1] : 'logs/sent_report.json';
  const codesCsv = process.argv.includes('--codesCsv') ? process.argv[process.argv.indexOf('--codesCsv') + 1] : 'logs/outreach_codes.csv';
  const outJson = process.argv.includes('--outJson') ? process.argv[process.argv.indexOf('--outJson') + 1] : 'temp/outbox_followups.json';
  const outTxt = process.argv.includes('--outTxt') ? process.argv[process.argv.indexOf('--outTxt') + 1] : 'temp/outbox_followups.txt';
  const ccArg = process.argv.includes('--cc') ? process.argv[process.argv.indexOf('--cc') + 1] : 'serdar@mobidictum.com,ehsan@mobidictum.com';
  const eventDates = normalizeEventDates(process.argv.includes('--eventDates') ? process.argv[process.argv.indexOf('--eventDates') + 1] : '21–22 October, Istanbul');
  const discountsUrl = process.argv.includes('--discountsUrl') ? process.argv[process.argv.indexOf('--discountsUrl') + 1] : 'https://fienta.com/mobidictum-conference-2025';
  const hotelsUrl = process.argv.includes('--hotelsUrl') ? process.argv[process.argv.indexOf('--hotelsUrl') + 1] : 'https://bit.ly/mobidictum-conference-2025';

  const cc = ccArg.split(',').map(s => s.trim()).filter(Boolean);
  const report = JSON.parse(fs.readFileSync(sentReportPath, 'utf8')) as { sent: SentEntry[] };
  const codes = readCsv(codesCsv);

  // Group codes by recipient email and capture form names
  const emailToCodes = new Map<string, string[]>();
  const emailToName = new Map<string, string>();
  for (const row of codes) {
    const email = String(row.email || '').toLowerCase();
    const code = String(row.code || '').trim();
    const name = String(row.name || '').trim();
    if (!email || !code) continue;
    const list = emailToCodes.get(email) || [];
    list.push(code);
    emailToCodes.set(email, list);
    if (name && !emailToName.has(email)) emailToName.set(email, name);
  }

  const messages: FollowupMessage[] = [];
  for (const s of report.sent) {
    const to = s.to;
    const codesList = emailToCodes.get(to.toLowerCase()) || [];
    const isMulti = codesList.length > 1;
    const subject = `Re: Correction — 40% discount for ${s.studio}`;
    const fromFormName = emailToName.get(to.toLowerCase());
    const fullName = fromFormName ? titleCaseWords(fromFormName) : properCase((to.split('@')[0] || '').split(/[._+-]/)[0] || 'there');
    const nameGuess = fullName.split(/\s+/)[0] || fullName;
    const codesLines = isMulti ? codesList.map(c => `${c} — 40% off (1 ticket)`).join('\n') : `Code: ${codesList[0] || ''} — 40% off (1 ticket)`;

    const intro = isMulti
      ? `Thank you for applying through the Game Studio Discount form. Our earlier message may have caused some confusion. The codes below are exclusive 40% discount codes for Mobidictum Conference 2025 (${eventDates}).`
      : `Thank you for applying through the Game Studio Discount form. Our earlier message may have caused some confusion. The code below is an exclusive 40% discount code for Mobidictum Conference 2025 (${eventDates}).`;

    const text = [
      `Hello ${nameGuess},`,
      '',
      intro,
      '',
      codesLines,
      '',
      `Redeem here: ${discountsUrl}`,
      '',
      `These ${isMulti ? 'codes' : 'code'} apply to any ticket type and ${isMulti ? 'are' : 'is'} reserved for ${s.studio}. This benefit comes from your application to the Game Studio Discount program, which we are expanding to improve access for more studios.`,
      '',
      `We look forward to welcoming the ${s.studio} team in Istanbul.`,
      '',
      'Best regards,',
      '',
      'Mobidictum Conference Team',
    ].join('\n');

    const htmlCodes = isMulti
      ? codesList.map(c => `${c} — 40% off (1 ticket)`).join('<br/>')
      : `Code: ${codesList[0] || ''} — 40% off (1 ticket)`;
    const html = `Hello ${nameGuess},<br/><br/>${intro}<br/><br/>${htmlCodes}<br/><br/>Redeem here: <a href=\"${discountsUrl}\">${discountsUrl}</a><br/><br/>These ${isMulti ? 'codes' : 'code'} apply to any ticket type and ${isMulti ? 'are' : 'is'} reserved for ${s.studio}. This benefit comes from your application to the Game Studio Discount program, which we are expanding to improve access for more studios.<br/><br/>We look forward to welcoming the ${s.studio} team in Istanbul.<br/><br/>Best regards,<br/><br/>Mobidictum Conference Team`;

    messages.push({
      to: [to],
      cc,
      subject,
      text,
      html,
      metadata: { followup: true, studio: s.studio, codes_count: codesList.length }
    });
  }

  fs.mkdirSync('temp', { recursive: true });
  fs.writeFileSync(outJson, JSON.stringify(messages, null, 2), 'utf8');
  const txt = messages.map(m => [`TO: ${m.to.join(', ')}`, `CC: ${m.cc.join(', ')}`, `SUBJECT: ${m.subject}`, '', m.text, ''.padEnd(60,'-')].join('\n')).join('\n');
  fs.writeFileSync(outTxt, txt, 'utf8');
  console.log('followups', messages.length, 'written to', outJson);
}

main();


