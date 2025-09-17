import fs from 'fs';
import path from 'path';
import { readXlsx, extractColumn } from '../xlsx';

function parseArgs(argv: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (let i = 0; i < argv.length; i += 1) {
    const t = argv[i];
    if (!t.startsWith('--')) continue;
    const [k, v] = t.slice(2).split('=');
    if (v !== undefined) out[k] = v;
    else if (argv[i + 1] && !argv[i + 1].startsWith('--')) {
      out[k] = argv[i + 1];
      i += 1;
    } else out[k] = 'true';
  }
  return out;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const input = args.in || args.input;
  if (!input) throw new Error('Usage: tsx src/tools/xlsx_to_csv.ts --in <path.xlsx> [--out <path.csv>] [--column discount_codes]');
  const output = args.out || args.output || path.join(path.dirname(input), path.basename(input, path.extname(input)) + '.csv');
  const column = args.column || 'discount_codes';

  const rows = readXlsx(input);
  const codes = rows
    .map((r) => String(extractColumn<string>(r, [column]) || ''))
    .filter((c) => c && c.trim().length > 0);

  // Write single-column CSV with no header for simplicity
  fs.writeFileSync(output, codes.join('\n') + '\n', 'utf8');
  // eslint-disable-next-line no-console
  console.log(`Converted ${codes.length} rows → ${output}`);
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  process.exit(1);
});


