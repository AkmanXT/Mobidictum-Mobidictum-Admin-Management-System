import fs from 'fs';
import { parse } from 'csv-parse';

export type CodeRecord = Record<string, string>;

export async function readCsv(filePath: string, delimiter: string = ','): Promise<CodeRecord[]> {
  return new Promise((resolve, reject) => {
    const records: CodeRecord[] = [];
    fs.createReadStream(filePath)
      .pipe(
        parse({
          columns: true,
          skip_empty_lines: true,
          trim: true,
          delimiter,
        }),
      )
      .on('data', (row: CodeRecord) => records.push(row))
      .on('end', () => resolve(records))
      .on('error', (err) => reject(err));
  });
}


