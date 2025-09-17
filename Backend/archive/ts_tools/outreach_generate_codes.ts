import fs from 'fs';
import path from 'path';

type OutreachAction = 'send_new_code' | 'reject' | 'review';

interface PreviewRow {
  name: string;
  email: string;
  studio: string;
  tickets: number | null;
  action: OutreachAction;
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

  return rows.map(r => {
    // naive CSV split (our generator uses simple commas; quotes are rare here)
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

    const get = (name: string): string => {
      const raw = parts[idx(name)] ?? '';
      return raw.replace(/^"|"$/g, '').replace(/""/g, '"');
    };
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
    };
  });
}

function slugFromStudio(studio: string): string {
  if (!studio) return 'NOSTUDIO';
  const cleaned = studio
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, ' and ')
    .replace(/[^a-zA-Z0-9]+/g, ' ')
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

function readArg(name: string, fallback?: string): string | undefined {
  const idx = process.argv.findIndex(a => a === `--${name}`);
  if (idx !== -1 && idx + 1 < process.argv.length) return process.argv[idx + 1];
  return fallback;
}

function main() {
  const previewCsv = readArg('previewCsv', 'logs/outreach_preview.csv')!;
  const outCodesCsv = readArg('outCodesCsv', 'logs/outreach_codes.csv')!;

  const rows = readCsv(previewCsv).filter(r => r.action === 'send_new_code');

  const lines: string[] = [];
  lines.push('email,name,studio,ticket_index,code,order_limit,ticket_limit');

  for (const r of rows) {
    const qty = Math.max(1, r.tickets ?? 1);
    const slug = slugFromStudio(r.studio);
    for (let i = 1; i <= qty; i++) {
      const code = `${slug}-${String(i).padStart(2, '0')}-${randomToken(3)}`;
      lines.push([
        r.email,
        r.name,
        r.studio,
        String(i),
        code,
        '1',
        '1',
      ].map(v => {
        const s = String(v);
        return s.includes(',') ? `"${s.replace(/"/g, '""')}"` : s;
      }).join(','));
    }
  }

  ensureDir(outCodesCsv);
  fs.writeFileSync(outCodesCsv, lines.join('\n'), 'utf8');
}

main();


