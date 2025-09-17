import fs from 'fs';
import path from 'path';
import { readCsv as readCsvGeneric } from '../csv';

function parseArgs(argv: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (let i = 0; i < argv.length; i += 1) {
    const t = argv[i];
    if (!t.startsWith('--')) continue;
    const [k, v] = t.slice(2).split('=');
    if (v !== undefined) out[k] = v;
    else if (argv[i + 1] && !argv[i + 1].startsWith('--')) { out[k] = argv[i + 1]; i += 1; }
    else out[k] = 'true';
  }
  return out;
}

function isCorrectWithPrefix(code: string, prefix: string): boolean {
  const p = prefix.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
  const re = new RegExp(`^${p}-\\d{3}-[A-Z0-9]{2,3}$`, 'i');
  return re.test((code || '').trim());
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const currentCsv = args.current; // comma-delimited, has Code column
  const trListCsv = args.list; // semicolon-delimited, has code column
  const outPath = args.out || path.join('logs', 'preview_basic_first201.csv');
  const limit = Number(args.limit || '201');
  const codeColumn = args.codeColumn || 'Code';
  const typeColumn = args.typeColumn || 'Type';
  const filterType = args.filterType; // e.g., Professional
  const listStartsWith = args.listStartsWith || 'TRBASIC-';
  const takeLast = String(args.takeLast || 'false').toLowerCase() === 'true';
  const createdColumn = args.createdColumn || 'Created at';
  const sortCreated = (args.sortCreated || '').toLowerCase(); // 'asc' | 'desc'

  if (!currentCsv || !trListCsv) {
    throw new Error('Usage: tsx src/tools/preview_pairs.ts --current <current.csv> --list <mapping.csv> [--out logs/preview.csv] [--limit N] [--codeColumn Code] [--typeColumn Type] [--filterType Professional] [--listStartsWith TRBASIC-]');
  }

  const currentRows = await readCsvGeneric(currentCsv, ',');
  let rowsFiltered = filterType
    ? currentRows.filter((r) => String((r as any)[typeColumn] || '').toLowerCase() === filterType.toLowerCase())
    : currentRows;
  if (filterType && rowsFiltered.length === 0) {
    const altCol = 'Applies to ticket types';
    rowsFiltered = currentRows.filter((r) => String((r as any)[altCol] || '').toLowerCase().includes(filterType.toLowerCase()))
  }
  if (sortCreated === 'asc' || sortCreated === 'desc') {
    rowsFiltered = rowsFiltered.slice().sort((a, b) => {
      const da = new Date(String((a as any)[createdColumn] || '')).getTime() || 0;
      const db = new Date(String((b as any)[createdColumn] || '')).getTime() || 0;
      return sortCreated === 'asc' ? da - db : db - da;
    });
  }
  const first = takeLast ? rowsFiltered.slice(-limit) : rowsFiltered.slice(0, limit);
  const currentCodes = first.map((r) => String((r as any)[codeColumn] || (r as any)['code'] || '')).filter(Boolean);

  const trRows = await readCsvGeneric(trListCsv, ';');
  let trTargets = trRows.map((r) => String((r as any)['code'] || '')).filter((c) => c.startsWith(listStartsWith));

  // remove TR targets already present
  const presentSet = new Set(currentCodes.filter((c) => isCorrectWithPrefix(c, listStartsWith.replace(/-$/, ''))));
  trTargets = trTargets.filter((t) => !presentSet.has(t));

  const pairs: Array<{ old: string; new: string }> = [];
  let idx = 0;
  for (const old of currentCodes) {
    if (isCorrectWithPrefix(old, listStartsWith.replace(/-$/, ''))) continue; // already OK
    if (idx >= trTargets.length) break;
    pairs.push({ old, new: trTargets[idx] });
    idx += 1;
  }

  if (!fs.existsSync(path.dirname(outPath))) fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const header = 'old,new\n';
  const body = pairs.map((p) => `${p.old},${p.new}`).join('\n') + '\n';
  fs.writeFileSync(outPath, header + body, 'utf8');
  // eslint-disable-next-line no-console
  console.log(`Preview written: ${outPath} (pairs: ${pairs.length})`);
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});


