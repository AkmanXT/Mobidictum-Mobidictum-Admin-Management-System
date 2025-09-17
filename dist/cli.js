"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const config_1 = require("./config");
const logger_1 = require("./logger");
const csv_1 = require("./csv");
const fienta_1 = require("./fienta");
const xlsx_1 = require("./xlsx");
const fs_1 = __importDefault(require("fs"));
const path_1 = __importDefault(require("path"));
async function main() {
    const config = (0, config_1.loadConfig)();
    logger_1.logger.info({ config: { ...config, fientaPassword: '***' } }, 'Configuration loaded');
    // Optional: update existing codes' discount percent and description from a CSV
    const updIdx = process.argv.indexOf('--updateDiscountPercent');
    const updateDiscountPercent = updIdx !== -1 && updIdx + 1 < process.argv.length ? Number(process.argv[updIdx + 1]) : undefined;
    let records = [];
    // If a pairs CSV is provided, use it directly (header: old,new)
    if (config.pairsCsvPath) {
        const pairsRaw = await (0, csv_1.readCsv)(config.pairsCsvPath, ',');
        const toRename = pairsRaw
            .map((r) => ({ old: String(r.old || ''), new: String(r.new || '') }))
            .filter((p) => p.old && p.new)
            .slice(0, config.renameLimit ?? pairsRaw.length);
        logger_1.logger.info({ sample: toRename.slice(0, 10), total: toRename.length }, 'Pairs CSV loaded');
        const client = new fienta_1.FientaClient(config);
        try {
            if (config.reportOnly) {
                const ts = new Date().toISOString().replace(/[:.]/g, '-');
                const dir = config.logsDir || 'logs';
                if (!fs_1.default.existsSync(dir))
                    fs_1.default.mkdirSync(dir, { recursive: true });
                const reportPath = path_1.default.join(dir, `report-${ts}.csv`);
                fs_1.default.writeFileSync(reportPath, 'old,new\n' + toRename.map((p) => `${p.old},${p.new}`).join('\n') + '\n', 'utf8');
                logger_1.logger.info({ reportPath }, 'Report written');
                return;
            }
            if (config.dryRun) {
                logger_1.logger.info('DRY RUN enabled - not launching browser.');
                return;
            }
            await client.start();
            await client.login();
            // Audit log file for this run
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            const dir = config.logsDir || 'logs';
            if (!fs_1.default.existsSync(dir))
                fs_1.default.mkdirSync(dir, { recursive: true });
            const logPath = path_1.default.join(dir, `renames-${ts}.csv`);
            fs_1.default.writeFileSync(logPath, 'old,new,status,message\n', 'utf8');
            try {
                await client.renameExistingCodes(toRename);
                for (const p of toRename)
                    fs_1.default.appendFileSync(logPath, `${p.old},${p.new},ok,\n`);
                logger_1.logger.info({ logPath }, 'Run log written');
            }
            catch (e) {
                for (const p of toRename)
                    fs_1.default.appendFileSync(logPath, `${p.old},${p.new},error,${(e && e.message) || ''}\n`);
                throw e;
            }
        }
        finally {
            await client.stop();
        }
        return;
    }
    // Diff mode: if both diff XLSX provided, generate applied changes CSV and exit
    if (config.diffOldXlsxPath && config.diffNewXlsxPath) {
        const oldRows = (0, xlsx_1.readXlsx)(config.diffOldXlsxPath);
        const newRows = (0, xlsx_1.readXlsx)(config.diffNewXlsxPath);
        const pick = (row) => String((config.codeColumn && (0, xlsx_1.extractColumn)(row, [config.codeColumn])) ||
            (0, xlsx_1.extractColumn)(row, ['discount_codes', 'code', 'name', 'coupon', 'ticket_code']) ||
            '');
        const oldCodes = oldRows.map(pick);
        const newCodes = newRows.map(pick);
        // Simple positional diff, plus set-based fallback
        const applied = [];
        const len = Math.min(oldCodes.length, newCodes.length);
        for (let i = 0; i < len; i += 1) {
            if (oldCodes[i] !== newCodes[i]) {
                applied.push({ before: oldCodes[i], after: newCodes[i] });
            }
        }
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        const dir = config.logsDir || 'logs';
        if (!fs_1.default.existsSync(dir))
            fs_1.default.mkdirSync(dir, { recursive: true });
        const out = path_1.default.join(dir, `applied-diff-${ts}.csv`);
        const csv = 'before,after\n' + applied.map((r) => `${r.before},${r.after}`).join('\n') + '\n';
        fs_1.default.writeFileSync(out, csv, 'utf8');
        logger_1.logger.info({ out, count: applied.length }, 'Applied changes report written');
        return;
    }
    if (config.sourceXlsxPath) {
        const rows = (0, xlsx_1.readXlsx)(config.sourceXlsxPath);
        const headers = rows.__headers__;
        if (headers?.length) {
            logger_1.logger.info({ headers }, 'XLSX normalized headers');
        }
        records = rows.map((row) => {
            const code = String((config.codeColumn && (0, xlsx_1.extractColumn)(row, [config.codeColumn])) ||
                (0, xlsx_1.extractColumn)(row, ['code', 'name', 'coupon', 'ticket_code']) ||
                '');
            const created = String((config.createdColumn && (0, xlsx_1.extractColumn)(row, [config.createdColumn])) ||
                (0, xlsx_1.extractColumn)(row, ['created', 'created_at', 'date']) ||
                '');
            return { code, created };
        });
        logger_1.logger.info({ count: records.length }, 'XLSX loaded');
    }
    else if (config.csvPath) {
        records = await (0, csv_1.readCsv)(config.csvPath);
        logger_1.logger.info({ count: records.length }, 'CSV loaded');
    }
    else {
        throw new Error('Provide data via --xlsx path/to/file.xlsx or --csv path/to/file.csv');
    }
    const client = new fienta_1.FientaClient(config);
    try {
        // If updateDiscountPercent is provided, update existing codes (no renaming/creation)
        if (updateDiscountPercent !== undefined) {
            if (config.dryRun) {
                logger_1.logger.info('DRY RUN enabled - not launching browser. Would update discounts.');
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
                ? records.filter((r) => (r.created || '').includes(config.createdAtIncludes))
                : records;
            if (config.skipRows) {
                filtered = filtered.slice(config.skipRows);
            }
            if (config.codeRegex) {
                const re = new RegExp(config.codeRegex);
                filtered = filtered.filter((r) => re.test(r.code || ''));
            }
            if (config.skipAlreadyPrefixed) {
                const prefix = config.renamePrefix || config.renameListStartsWith;
                if (prefix) {
                    filtered = filtered.filter((r) => !(r.code || '').startsWith(prefix));
                }
            }
            const limit = config.renameLimit ?? filtered.length;
            let toRename = [];
            if (config.renameListCsvPath) {
                const list = await (0, csv_1.readCsv)(config.renameListCsvPath, config.renameListDelimiter);
                let listCodes = list.map((r) => String(r[config.renameListColumn || 'code'] || '')).filter(Boolean);
                if (config.renameListStartsWith)
                    listCodes = listCodes.filter((c) => c.startsWith(config.renameListStartsWith));
                if (config.renameListSkip)
                    listCodes = listCodes.slice(config.renameListSkip);
                const slice = listCodes.slice(0, limit);
                toRename = filtered.slice(0, slice.length).map((r, idx) => ({ old: r.code, new: slice[idx] }));
            }
            else {
                const start = (config.renameStart ?? 1) - 1;
                const pad = config.renamePadLength ?? 2;
                toRename = filtered.slice(0, limit).map((r, idx) => ({
                    old: r.code,
                    new: `${config.renamePrefix}${String(idx + 1 + start).padStart(pad, '0')}`,
                }));
            }
            // Skip items already matching the target name
            const normalize = (s) => (s || '').trim();
            toRename = toRename.filter((p) => normalize(p.old) !== normalize(p.new));
            logger_1.logger.info({ sample: toRename.slice(0, 10), total: toRename.length }, 'Rename plan');
            if (config.reportOnly) {
                const ts = new Date().toISOString().replace(/[:.]/g, '-');
                const dir = config.logsDir || 'logs';
                if (!fs_1.default.existsSync(dir))
                    fs_1.default.mkdirSync(dir, { recursive: true });
                const reportPath = path_1.default.join(dir, `report-${ts}.csv`);
                const header = 'old,new\n';
                const body = toRename.map((p) => `${p.old},${p.new}`).join('\n') + '\n';
                fs_1.default.writeFileSync(reportPath, header + body, 'utf8');
                logger_1.logger.info({ reportPath }, 'Report written');
                return;
            }
            if (config.dryRun) {
                logger_1.logger.info('DRY RUN enabled - not launching browser.');
                return;
            }
            await client.start();
            await client.login();
            // Write log file with results
            const ts = new Date().toISOString().replace(/[:.]/g, '-');
            const dir = config.logsDir || 'logs';
            if (!fs_1.default.existsSync(dir))
                fs_1.default.mkdirSync(dir, { recursive: true });
            const logPath = path_1.default.join(dir, `renames-${ts}.csv`);
            fs_1.default.writeFileSync(logPath, 'old,new,status,message\n', 'utf8');
            // Wrap rename with logging
            const chunks = toRename;
            const clientRename = client.renameExistingCodes.bind(client);
            try {
                await clientRename(chunks.map((p) => ({ ...p })));
                for (const p of chunks)
                    fs_1.default.appendFileSync(logPath, `${p.old},${p.new},ok,\n`);
            }
            catch (e) {
                for (const p of chunks)
                    fs_1.default.appendFileSync(logPath, `${p.old},${p.new},error,${(e && e.message) || ''}\n`);
                throw e;
            }
        }
        else {
            if (config.dryRun) {
                logger_1.logger.info('DRY RUN enabled - not launching browser.');
                return;
            }
            await client.start();
            await client.login();
            await client.createOrCustomizeCodes(records);
        }
    }
    finally {
        await client.stop();
    }
}
main().catch((err) => {
    logger_1.logger.error(err, 'Fatal error');
    process.exit(1);
});
