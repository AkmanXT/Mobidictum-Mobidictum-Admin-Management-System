import dotenv from 'dotenv';
import path from 'path';
import { logger } from './logger';

dotenv.config();

type ParsedArgs = Record<string, string | boolean>;

function parseArgs(argv: string[]): ParsedArgs {
  const args: ParsedArgs = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) continue;
    const [keyRaw, maybeValue] = token.slice(2).split('=');
    const key = keyRaw.trim();
    let value: string | boolean | undefined = maybeValue;
    if (value === undefined) {
      const next = argv[i + 1];
      if (next && !next.startsWith('--')) {
        value = next;
        i += 1;
      } else {
        value = true;
      }
    }
    args[key] = value;
  }
  return args;
}

export type AppConfig = {
  fientaEmail: string;
  fientaPassword: string;
  fientaBaseUrl: string;
  csvPath: string;
  headless: boolean;
  dryRun: boolean;
  // rename options
  renamePrefix?: string;
  renameLimit?: number;
  createdAtIncludes?: string;
  sourceXlsxPath?: string;
  renamePadLength?: number;
  renameStart?: number;
  codeColumn?: string;
  createdColumn?: string;
  skipRows?: number;
  codeRegex?: string;
  skipAlreadyPrefixed?: boolean;
  discountsUrl?: string;
  storageStatePath?: string;
  manualLogin?: boolean;
  loginTimeoutMs?: number;
  // rename list (CSV) options
  renameListCsvPath?: string;
  renameListDelimiter?: string;
  renameListColumn?: string;
  renameListStartsWith?: string;
  renameListSkip?: number;
  // reporting/logging
  reportOnly?: boolean;
  logsDir?: string;
  diffOldXlsxPath?: string;
  diffNewXlsxPath?: string;
  pairsCsvPath?: string;
  // per-order limit option
  limitPerOrder?: number;
  // per-ticket limit option
  limitPerTicket?: number;
  // only update limit, do not touch code field
  onlyUpdateLimit?: boolean;
};

export function loadConfig(): AppConfig {
  const args = parseArgs(process.argv.slice(2));

  const fientaEmail = (args.email as string) || process.env.FIENTA_EMAIL || '';
  const fientaPassword = (args.password as string) || process.env.FIENTA_PASSWORD || '';
  const fientaBaseUrl = (args.baseUrl as string) || process.env.FIENTA_BASE_URL || 'https://fienta.com';
  const csvPathRaw = (args.csv as string) || process.env.CSV_PATH || '';
  const headless = String(args.headless ?? process.env.HEADLESS ?? 'true').toLowerCase() !== 'false';
  const dryRun = String(args.dryRun ?? process.env.DRY_RUN ?? 'true').toLowerCase() !== 'false';
  const renamePrefix = (args.renamePrefix as string) || process.env.RENAME_PREFIX;
  const renameLimit = Number(args.renameLimit ?? process.env.RENAME_LIMIT ?? '') || undefined;
  const createdAtIncludes = (args.createdAt as string) || process.env.CREATED_AT_INCLUDES;
  const sourceXlsxPath = (args.xlsx as string) || process.env.SOURCE_XLSX_PATH;
  const renamePadLength = Number(args.renamePadLength ?? process.env.RENAME_PAD_LENGTH ?? '') || undefined;
  const renameStart = Number(args.renameStart ?? process.env.RENAME_START ?? '') || undefined;
  const codeColumn = (args.codeColumn as string) || process.env.CODE_COLUMN;
  const createdColumn = (args.createdColumn as string) || process.env.CREATED_COLUMN;
  const skipRows = Number(args.skipRows ?? process.env.SKIP_ROWS ?? '') || undefined;
  const codeRegex = (args.codeRegex as string) || process.env.CODE_REGEX;
  const skipAlreadyPrefixed = String(args.skipAlreadyPrefixed ?? process.env.SKIP_ALREADY_PREFIXED ?? 'true').toLowerCase() !== 'false';
  const discountsUrl = (args.discountsUrl as string) || process.env.DISCOUNTS_URL;
  const storageStatePath = (args.storageState as string) || process.env.STORAGE_STATE_PATH || 'auth/state.json';
  const manualLogin = String(args.manualLogin ?? process.env.MANUAL_LOGIN ?? 'true').toLowerCase() !== 'false';
  const loginTimeoutMs = Number(args.loginTimeoutMs ?? process.env.LOGIN_TIMEOUT_MS ?? '180000') || 180000;
  const renameListCsvPath = (args.listCsv as string) || process.env.RENAME_LIST_CSV_PATH;
  const renameListDelimiter = (args.listDelimiter as string) || process.env.RENAME_LIST_DELIMITER || ',';
  const renameListColumn = (args.listColumn as string) || process.env.RENAME_LIST_COLUMN || 'code';
  const renameListStartsWith = (args.listStartsWith as string) || process.env.RENAME_LIST_STARTS_WITH;
  const renameListSkip = Number(args.listSkip ?? process.env.RENAME_LIST_SKIP ?? '') || undefined;
  const reportOnly = String(args.reportOnly ?? process.env.REPORT_ONLY ?? 'false').toLowerCase() === 'true';
  const logsDir = (args.logsDir as string) || process.env.LOGS_DIR || 'logs';
  const diffOldXlsxPath = (args.diffOld as string) || process.env.DIFF_OLD_XLSX_PATH;
  const diffNewXlsxPath = (args.diffNew as string) || process.env.DIFF_NEW_XLSX_PATH;
  const pairsCsvPath = (args.pairsCsv as string) || process.env.PAIRS_CSV_PATH;
  const limitPerOrder = Number(args.limitPerOrder ?? process.env.LIMIT_PER_ORDER ?? '') || undefined;
  const limitPerTicket = Number(args.limitPerTicket ?? process.env.LIMIT_PER_TICKET ?? '') || undefined;
  const onlyUpdateLimit = String(args.onlyUpdateLimit ?? process.env.ONLY_UPDATE_LIMIT ?? 'false').toLowerCase() === 'true';

  if (!fientaEmail || !fientaPassword) {
    logger.warn('Fienta credentials are missing. Provide --email/--password or set FIENTA_EMAIL/FIENTA_PASSWORD.');
  }

  if (!csvPathRaw) {
    logger.warn('CSV path is missing. Provide --csv or set CSV_PATH.');
  }

  const csvPath = csvPathRaw ? path.resolve(process.cwd(), csvPathRaw) : '';

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


