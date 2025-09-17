import { loadConfig } from './config';
import { logger } from './logger';
import { readCsv } from './csv';
import { FientaClient } from './fienta';
import { readXlsx, extractColumn } from './xlsx';
import fs from 'fs';
import path from 'path';

async function main(): Promise<void> {
  const config = loadConfig();
  logger.info({ config: { ...config, fientaPassword: '***' } }, 'Configuration loaded');

  // Optional: update existing codes' discount percent and description from a CSV
  const updIdx = process.argv.indexOf('--updateDiscountPercent');
  const updateDiscountPercent = updIdx !== -1 && updIdx + 1 < process.argv.length ? Number(process.argv[updIdx + 1]) : undefined;

  let records: Array<Record<string, string>> = [];
  // If a pairs CSV is provided, use it directly (header: old,new)
  if (config.pairsCsvPath) {
    const pairsRaw = await readCsv(config.pairsCsvPath, ',');
    const toRename = pairsRaw
      .map((r) => ({ old: String(r.old || ''), new: String(r.new || '') }))
      .filter((p) => p.old && p.new)
      .slice(0, config.renameLimit ?? pairsRaw.length);
    logger.info({ sample: toRename.slice(0, 10), total: toRename.length }, 'Pairs CSV loaded');
    const client = new FientaClient(config);
    try {
      if (config.reportOnly) {
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        const dir = config.logsDir || 'logs';
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const reportPath = path.join(dir, `report-${ts}.csv`);
        fs.writeFileSync(reportPath, 'old,new\n' + toRename.map((p) => `${p.old},${p.new}`).join('\n') + '\n', 'utf8');
        logger.info({ reportPath }, 'Report written');
        return;
      }
      if (config.dryRun) {
        logger.info('DRY RUN enabled - not launching browser.');
        return;
      }
      await client.start();
      await client.login();
      // Audit log file for this run
      const ts = new Date().toISOString().replace(/[:.]/g, '-');
      const dir = config.logsDir || 'logs';
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      const logPath = path.join(dir, `renames-${ts}.csv`);
      fs.writeFileSync(logPath, 'old,new,status,message\n', 'utf8');

      try {
        await client.renameExistingCodes(toRename);
        for (const p of toRename) fs.appendFileSync(logPath, `${p.old},${p.new},ok,\n`);
        logger.info({ logPath }, 'Run log written');
      } catch (e: any) {
        for (const p of toRename) fs.appendFileSync(logPath, `${p.old},${p.new},error,${(e && e.message) || ''}\n`);
        throw e;
      }
    } finally {
      await client.stop();
    }
    return;
  }
  // Diff mode: if both diff XLSX provided, generate applied changes CSV and exit
  if (config.diffOldXlsxPath && config.diffNewXlsxPath) {
    const oldRows = readXlsx(config.diffOldXlsxPath);
    const newRows = readXlsx(config.diffNewXlsxPath);
    const pick = (row: any) => String(
      (config.codeColumn && extractColumn<string>(row, [config.codeColumn])) ||
        extractColumn<string>(row, ['discount_codes', 'code', 'name', 'coupon', 'ticket_code']) ||
        '',
    );
    const oldCodes = oldRows.map(pick);
    const newCodes = newRows.map(pick);
    // Simple positional diff, plus set-based fallback
    const applied: Array<{ before: string; after: string }> = [];
    const len = Math.min(oldCodes.length, newCodes.length);
    for (let i = 0; i < len; i += 1) {
      if (oldCodes[i] !== newCodes[i]) {
        applied.push({ before: oldCodes[i], after: newCodes[i] });
      }
    }
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const dir = config.logsDir || 'logs';
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    const out = path.join(dir, `applied-diff-${ts}.csv`);
    const csv = 'before,after\n' + applied.map((r) => `${r.before},${r.after}`).join('\n') + '\n';
    fs.writeFileSync(out, csv, 'utf8');
    logger.info({ out, count: applied.length }, 'Applied changes report written');
    return;
  }
  if (config.sourceXlsxPath) {
    const rows = readXlsx(config.sourceXlsxPath);
    const headers = (rows as any).__headers__ as string[] | undefined;
    if (headers?.length) {
      logger.info({ headers }, 'XLSX normalized headers');
    }
    records = rows.map((row) => {
      const code = String(
        (config.codeColumn && extractColumn<string>(row, [config.codeColumn])) ||
          extractColumn<string>(row, ['code', 'name', 'coupon', 'ticket_code']) ||
          '',
      );
      const created = String(
        (config.createdColumn && extractColumn<string>(row, [config.createdColumn])) ||
          extractColumn<string>(row, ['created', 'created_at', 'date']) ||
          '',
      );
      return { code, created };
    });
    logger.info({ count: records.length }, 'XLSX loaded');
  } else if (config.csvPath) {
    records = await readCsv(config.csvPath);
    logger.info({ count: records.length }, 'CSV loaded');
  } else {
    throw new Error('Provide data via --xlsx path/to/file.xlsx or --csv path/to/file.csv');
  }

  const client = new FientaClient(config);
  try {
    // If updateDiscountPercent is provided, update existing codes (no renaming/creation)
    if (updateDiscountPercent !== undefined) {
      if (config.dryRun) {
        logger.info('DRY RUN enabled - not launching browser. Would update discounts.');
        return;
      }
      await client.start();
      await client.login();
      await client.updateExistingCodes(records, updateDiscountPercent);
      return;
    }
    if (config.renamePrefix || config.renameListCsvPath) {
      // Filter by createdAt substring match if provided
      let filtered = config.createdAtIncludes
        ? records.filter((r) => (r.created || '').includes(config.createdAtIncludes as string))
        : records;

      if (config.skipRows) {
        filtered = filtered.slice(config.skipRows);
      }

      if (config.codeRegex) {
        const re = new RegExp(config.codeRegex);
        filtered = filtered.filter((r) => re.test(r.code || ''));
      }

      if (config.skipAlreadyPrefixed) {
        const prefix = (config.renamePrefix as string) || (config.renameListStartsWith as string);
        if (prefix) {
          filtered = filtered.filter((r) => !(r.code || '').startsWith(prefix));
        }
      }
      const limit = config.renameLimit ?? filtered.length;
      let toRename: Array<{ old: string; new: string }> = [];
      if (config.renameListCsvPath) {
        const list = await readCsv(config.renameListCsvPath, config.renameListDelimiter);
        let listCodes = list.map((r) => String(r[config.renameListColumn || 'code'] || '')).filter(Boolean);
        if (config.renameListStartsWith) listCodes = listCodes.filter((c) => c.startsWith(config.renameListStartsWith as string));
        if (config.renameListSkip) listCodes = listCodes.slice(config.renameListSkip);
        const slice = listCodes.slice(0, limit);
        toRename = filtered.slice(0, slice.length).map((r, idx) => ({ old: r.code, new: slice[idx] }));
      } else {
        const start = (config.renameStart ?? 1) - 1;
        const pad = config.renamePadLength ?? 2;
        toRename = filtered.slice(0, limit).map((r, idx) => ({
          old: r.code,
          new: `${config.renamePrefix}${String(idx + 1 + start).padStart(pad, '0')}`,
        }));
      }

      // Skip items already matching the target name
      const normalize = (s: string) => (s || '').trim();
      toRename = toRename.filter((p) => normalize(p.old) !== normalize(p.new));

      logger.info({ sample: toRename.slice(0, 10), total: toRename.length }, 'Rename plan');

      if (config.reportOnly) {
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        const dir = config.logsDir || 'logs';
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const reportPath = path.join(dir, `report-${ts}.csv`);
        const header = 'old,new\n';
        const body = toRename.map((p) => `${p.old},${p.new}`).join('\n') + '\n';
        fs.writeFileSync(reportPath, header + body, 'utf8');
        logger.info({ reportPath }, 'Report written');
        return;
      }
      if (config.dryRun) {
        logger.info('DRY RUN enabled - not launching browser.');
        return;
      }
      await client.start();
      await client.login();
      // Write log file with results
      const ts = new Date().toISOString().replace(/[:.]/g, '-');
      const dir = config.logsDir || 'logs';
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      const logPath = path.join(dir, `renames-${ts}.csv`);
      fs.writeFileSync(logPath, 'old,new,status,message\n', 'utf8');

      // Wrap rename with logging
      const chunks = toRename;
      const clientRename = client.renameExistingCodes.bind(client);
      try {
        await clientRename(
          chunks.map((p) => ({ ...p })),
        );
        for (const p of chunks) fs.appendFileSync(logPath, `${p.old},${p.new},ok,\n`);
      } catch (e: any) {
        for (const p of chunks) fs.appendFileSync(logPath, `${p.old},${p.new},error,${(e && e.message) || ''}\n`);
        throw e;
      }
    } else {
      if (config.dryRun) {
        logger.info('DRY RUN enabled - not launching browser.');
        return;
      }
      await client.start();
      await client.login();
      await client.createOrCustomizeCodes(records);
    }
  } finally {
    await client.stop();
  }
}

main().catch((err) => {
  logger.error(err, 'Fatal error');
  process.exit(1);
});


