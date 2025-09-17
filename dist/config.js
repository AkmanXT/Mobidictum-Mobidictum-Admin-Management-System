"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.loadConfig = loadConfig;
const dotenv_1 = __importDefault(require("dotenv"));
const path_1 = __importDefault(require("path"));
const logger_1 = require("./logger");
dotenv_1.default.config();
function parseArgs(argv) {
    const args = {};
    for (let i = 0; i < argv.length; i += 1) {
        const token = argv[i];
        if (!token.startsWith('--'))
            continue;
        const [keyRaw, maybeValue] = token.slice(2).split('=');
        const key = keyRaw.trim();
        let value = maybeValue;
        if (value === undefined) {
            const next = argv[i + 1];
            if (next && !next.startsWith('--')) {
                value = next;
                i += 1;
            }
            else {
                value = true;
            }
        }
        args[key] = value;
    }
    return args;
}
function loadConfig() {
    const args = parseArgs(process.argv.slice(2));
    const fientaEmail = args.email || process.env.FIENTA_EMAIL || '';
    const fientaPassword = args.password || process.env.FIENTA_PASSWORD || '';
    const fientaBaseUrl = args.baseUrl || process.env.FIENTA_BASE_URL || 'https://fienta.com';
    const csvPathRaw = args.csv || process.env.CSV_PATH || '';
    const headless = String(args.headless ?? process.env.HEADLESS ?? 'true').toLowerCase() !== 'false';
    const dryRun = String(args.dryRun ?? process.env.DRY_RUN ?? 'true').toLowerCase() !== 'false';
    const renamePrefix = args.renamePrefix || process.env.RENAME_PREFIX;
    const renameLimit = Number(args.renameLimit ?? process.env.RENAME_LIMIT ?? '') || undefined;
    const createdAtIncludes = args.createdAt || process.env.CREATED_AT_INCLUDES;
    const sourceXlsxPath = args.xlsx || process.env.SOURCE_XLSX_PATH;
    const renamePadLength = Number(args.renamePadLength ?? process.env.RENAME_PAD_LENGTH ?? '') || undefined;
    const renameStart = Number(args.renameStart ?? process.env.RENAME_START ?? '') || undefined;
    const codeColumn = args.codeColumn || process.env.CODE_COLUMN;
    const createdColumn = args.createdColumn || process.env.CREATED_COLUMN;
    const skipRows = Number(args.skipRows ?? process.env.SKIP_ROWS ?? '') || undefined;
    const codeRegex = args.codeRegex || process.env.CODE_REGEX;
    const skipAlreadyPrefixed = String(args.skipAlreadyPrefixed ?? process.env.SKIP_ALREADY_PREFIXED ?? 'true').toLowerCase() !== 'false';
    const discountsUrl = args.discountsUrl || process.env.DISCOUNTS_URL;
    const storageStatePath = args.storageState || process.env.STORAGE_STATE_PATH || 'auth/state.json';
    const manualLogin = String(args.manualLogin ?? process.env.MANUAL_LOGIN ?? 'true').toLowerCase() !== 'false';
    const loginTimeoutMs = Number(args.loginTimeoutMs ?? process.env.LOGIN_TIMEOUT_MS ?? '180000') || 180000;
    const renameListCsvPath = args.listCsv || process.env.RENAME_LIST_CSV_PATH;
    const renameListDelimiter = args.listDelimiter || process.env.RENAME_LIST_DELIMITER || ',';
    const renameListColumn = args.listColumn || process.env.RENAME_LIST_COLUMN || 'code';
    const renameListStartsWith = args.listStartsWith || process.env.RENAME_LIST_STARTS_WITH;
    const renameListSkip = Number(args.listSkip ?? process.env.RENAME_LIST_SKIP ?? '') || undefined;
    const reportOnly = String(args.reportOnly ?? process.env.REPORT_ONLY ?? 'false').toLowerCase() === 'true';
    const logsDir = args.logsDir || process.env.LOGS_DIR || 'logs';
    const diffOldXlsxPath = args.diffOld || process.env.DIFF_OLD_XLSX_PATH;
    const diffNewXlsxPath = args.diffNew || process.env.DIFF_NEW_XLSX_PATH;
    const pairsCsvPath = args.pairsCsv || process.env.PAIRS_CSV_PATH;
    const limitPerOrder = Number(args.limitPerOrder ?? process.env.LIMIT_PER_ORDER ?? '') || undefined;
    const limitPerTicket = Number(args.limitPerTicket ?? process.env.LIMIT_PER_TICKET ?? '') || undefined;
    const onlyUpdateLimit = String(args.onlyUpdateLimit ?? process.env.ONLY_UPDATE_LIMIT ?? 'false').toLowerCase() === 'true';
    if (!fientaEmail || !fientaPassword) {
        logger_1.logger.warn('Fienta credentials are missing. Provide --email/--password or set FIENTA_EMAIL/FIENTA_PASSWORD.');
    }
    if (!csvPathRaw) {
        logger_1.logger.warn('CSV path is missing. Provide --csv or set CSV_PATH.');
    }
    const csvPath = csvPathRaw ? path_1.default.resolve(process.cwd(), csvPathRaw) : '';
    return {
        fientaEmail,
        fientaPassword,
        fientaBaseUrl,
        csvPath,
        headless,
        dryRun,
        renamePrefix,
        renameLimit,
        createdAtIncludes,
        sourceXlsxPath,
        renamePadLength,
        renameStart,
        codeColumn,
        createdColumn,
        skipRows,
        codeRegex,
        skipAlreadyPrefixed,
        discountsUrl,
        storageStatePath,
        manualLogin,
        loginTimeoutMs,
        renameListCsvPath,
        renameListDelimiter,
        renameListColumn,
        renameListStartsWith,
        renameListSkip,
        reportOnly,
        logsDir,
        diffOldXlsxPath,
        diffNewXlsxPath,
        pairsCsvPath,
        limitPerOrder,
        limitPerTicket,
        onlyUpdateLimit,
    };
}
