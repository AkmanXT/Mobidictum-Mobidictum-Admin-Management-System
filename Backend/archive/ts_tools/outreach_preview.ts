import fs from 'fs';
import path from 'path';

type OutreachAction = 'send_new_code' | 'reject' | 'review';

interface OutreachContact {
  name: string;
  email: string;
  studio: string;
  tickets: number | null;
  notes: string;
  action: OutreachAction;
  codeSuggestion: string | null;
  limitPerOrder: number | null;
  limitPerTicket: number | null;
}

function ensureDir(filePath: string): void {
  const dir = path.dirname(path.resolve(filePath));
  fs.mkdirSync(dir, { recursive: true });
}

function isEmail(line: string): boolean {
  return /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(line.trim());
}

function parseTickets(line: string): number | null {
  const m = line.toLowerCase().match(/(\d+)\s*ticket/);
  if (m) return parseInt(m[1], 10);
  return null;
}

function cleanNotes(lines: string[]): string {
  return lines
    .filter(l => {
      const t = l.trim();
      if (!t) return false;
      if (/\b(\d{1,2}:\d{2}\s*(am|pm))\b/i.test(t)) return false; // time stamps
      if (/Edited/i.test(t)) return false;
      if (/^Ehsan\s+Bagheri/i.test(t)) return false;
      return true;
    })
    .join(' ')
    .trim();
}

function slugFromStudio(studio: string): string {
  if (!studio) return 'NOSTUDIO';
  const cleaned = studio
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '') // remove diacritics
    .replace(/&/g, ' and ')
    .replace(/[^a-zA-Z0-9]+/g, ' ') // keep alnum
    .trim()
    .split(/\s+/)
    .map(w => w.toUpperCase())
    .filter(Boolean);
  const joined = cleaned.join('');
  return joined.slice(0, 16) || 'NOSTUDIO';
}

function randomToken(length: number): string {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let out = '';
  for (let i = 0; i < length; i++) out += alphabet[Math.floor(Math.random() * alphabet.length)];
  return out;
}

function decideAction(notes: string): OutreachAction {
  const n = notes.toLowerCase();
  if (n.includes('reject')) return 'reject';
  if (n.includes('not sure')) return 'review';
  if (n.includes('app developer') && n.includes('otherwise reject')) return 'review';
  if (n.includes('should send a new code')) return 'send_new_code';
  if (n.includes('send them a new one')) return 'send_new_code';
  return 'review';
}

function parseSourceText(text: string): OutreachContact[] {
  const rawLines = text.split(/\r?\n/);
  // Build a trimmed list but keep original for name casing
  const lines = rawLines.map(l => l.replace(/\s+$/,'')); // remove trailing spaces only

  // Find all indices of lines that contain an email
  const emailIndices: number[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (isEmail(lines[i])) emailIndices.push(i);
  }

  const contacts: OutreachContact[] = [];
  for (let e = 0; e < emailIndices.length; e++) {
    const emailIdx = emailIndices[e];
    const nextEmailIdx = e + 1 < emailIndices.length ? emailIndices[e + 1] : lines.length;

    const email = lines[emailIdx].trim();

    // Name: nearest non-empty, non-metadata line above email
    let name = '';
    for (let i = emailIdx - 1; i >= 0; i--) {
      const t = lines[i].trim();
      if (!t) continue;
      if (/\b(\d{1,2}:\d{2}\s*(am|pm))\b/i.test(t)) continue;
      if (/Edited/i.test(t)) continue;
      if (/^Ehsan\s+Bagheri/i.test(t)) continue;
      name = t;
      break;
    }

    // Studio: first non-empty non-email non-ticket line after email
    let studio = '';
    for (let i = emailIdx + 1; i < nextEmailIdx; i++) {
      const t = lines[i].trim();
      if (!t) continue;
      if (isEmail(t)) break; // safety
      if (parseTickets(t) !== null) break;
      studio = t;
      break;
    }

    // Tickets: first ticket line after email
    let tickets: number | null = null;
    let ticketsIdx = -1;
    for (let i = emailIdx + 1; i < nextEmailIdx; i++) {
      const t = parseTickets(lines[i]);
      if (t !== null) {
        tickets = t;
        ticketsIdx = i;
        break;
      }
    }

    // Notes: from after tickets (or email) up to before next email
    const notesStart = ticketsIdx !== -1 ? ticketsIdx + 1 : emailIdx + 1;
    const noteSlice = lines.slice(notesStart, nextEmailIdx).map(l => l.trim());
    const notes = cleanNotes(noteSlice);

    const action = decideAction(notes);
    let codeSuggestion: string | null = null;
    let limitPerOrder: number | null = null;
    let limitPerTicket: number | null = null;

    if (action === 'send_new_code') {
      const slug = slugFromStudio(studio);
      const qty = (tickets ?? 1);
      codeSuggestion = `${slug}-${String(qty).padStart(2, '0')}-${randomToken(3)}`;
      limitPerOrder = 1;
      limitPerTicket = qty;
    }

    contacts.push({
      name,
      email,
      studio,
      tickets,
      notes,
      action,
      codeSuggestion,
      limitPerOrder,
      limitPerTicket,
    });
  }

  return contacts;
}

function toCsv(contacts: OutreachContact[]): string {
  const header = [
    'name',
    'email',
    'studio',
    'tickets',
    'action',
    'code_suggestion',
    'limit_per_order',
    'limit_per_ticket',
    'notes',
  ];
  const rows = contacts.map(c => [
    c.name,
    c.email,
    c.studio,
    c.tickets ?? '',
    c.action,
    c.codeSuggestion ?? '',
    c.limitPerOrder ?? '',
    c.limitPerTicket ?? '',
    c.notes.replace(/\s+/g, ' ').trim(),
  ]);
  const escape = (v: unknown) => {
    const s = String(v);
    if (s.includes(',') || s.includes('"') || /\s\n/.test(s)) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  };
  return [header.map(escape).join(','), ...rows.map(r => r.map(escape).join(','))].join('\n');
}

function toTxt(contacts: OutreachContact[]): string {
  return contacts
    .map(c => [
      `${c.name} <${c.email}>`,
      `Studio: ${c.studio}`,
      `Tickets: ${c.tickets ?? ''}`,
      `Action: ${c.action}`,
      c.codeSuggestion ? `Code: ${c.codeSuggestion} (order=${c.limitPerOrder}, ticket=${c.limitPerTicket})` : 'Code: -',
      c.notes ? `Notes: ${c.notes}` : 'Notes: -',
      ''.padEnd(40, '-')
    ].join('\n'))
    .join('\n');
}

function readArg(name: string, fallback?: string): string | undefined {
  const idx = process.argv.findIndex(a => a === `--${name}`);
  if (idx !== -1 && idx + 1 < process.argv.length) return process.argv[idx + 1];
  return fallback;
}

function main() {
  const sourcePath = readArg('source', 'email_outreach/source.txt')!;
  const outCsv = readArg('outCsv', 'logs/outreach_preview.csv')!;
  const outTxt = readArg('outTxt', 'logs/outreach_preview.txt')!;

  const text = fs.readFileSync(sourcePath, 'utf8');
  const contacts = parseSourceText(text);

  ensureDir(outCsv);
  ensureDir(outTxt);
  fs.writeFileSync(outCsv, toCsv(contacts), 'utf8');
  fs.writeFileSync(outTxt, toTxt(contacts), 'utf8');

  // Also emit a pairs-like CSV for immediate code operations if needed later
  const actionable = contacts.filter(c => c.action === 'send_new_code' && c.codeSuggestion);
  if (actionable.length) {
    const pairsPath = readArg('outPairs', 'logs/outreach_pairs.csv')!;
    ensureDir(pairsPath);
    const header = 'new_code,limitPerOrder,limitPerTicket,name,email,studio';
    const rows = actionable.map(c => [
      c.codeSuggestion!,
      String(c.limitPerOrder ?? ''),
      String(c.limitPerTicket ?? ''),
      c.name,
      c.email,
      c.studio,
    ].map(v => {
      const s = String(v);
      return s.includes(',') ? `"${s.replace(/"/g, '""')}"` : s;
    }).join(','));
    fs.writeFileSync(pairsPath, [header, ...rows].join('\n'), 'utf8');
  }
}

main();


