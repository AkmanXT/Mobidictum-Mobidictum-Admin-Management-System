import path from 'path';
import fs from 'fs';
import * as XLSX from 'xlsx';

export type XlsxRecord = Record<string, unknown>;

function normalizeHeader(key: string): string {
  return key.trim().toLowerCase().replace(/\s+/g, '_');
}

export function readXlsx(filePath: string): XlsxRecord[] {
  const resolved = path.resolve(process.cwd(), filePath);
  if (!fs.existsSync(resolved)) {
    throw new Error(`XLSX not found: ${resolved}`);
  }
  const wb = XLSX.readFile(resolved);
  const sheetName = wb.SheetNames[0];
  const ws = wb.Sheets[sheetName];
  const rows: Record<string, unknown>[] = XLSX.utils.sheet_to_json(ws, { raw: false });
  const normalizedRows = rows.map((row) => {
    const normalized: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(row)) {
      normalized[normalizeHeader(k)] = v;
    }
    return normalized;
  });
  // attach headers list on the array object for logging (non-enumerable to avoid serialization spam)
  const headers = Object.keys(normalizedRows[0] ?? {});
  Object.defineProperty(normalizedRows, '__headers__', {
    value: headers,
    enumerable: false,
    configurable: true,
  });
  return normalizedRows;
}

export function extractColumn<T = string>(row: XlsxRecord, candidates: string[]): T | undefined {
  for (const c of candidates) {
    const key = normalizeHeader(c);
    if (key in row) return row[key] as T;
  }
  // try exact keys already normalized
  for (const c of candidates) {
    if (c in row) return row[c] as T;
  }
  return undefined;
}


