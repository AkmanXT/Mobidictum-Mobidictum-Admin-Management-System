## Fienta Code Manager

Tools to manage Fienta discount codes via Playwright browser automation.

### Prerequisites
- Node 18+
- npm

### Install
```bash
npm install
```

### Build (optional)
```bash
npm run build
```

### Common usage
- Create codes from CSV:
```bash
npm run dev -- --csv data/fienta_discount_codes_TR_randomized.csv --email your@email --password "***" --headless=false --dryRun=false
```

- Create codes from XLSX:
```bash
npm run dev -- --xlsx "data/discounts_...xlsx" --email your@email --password "***" --headless=false --dryRun=false
```

- Rename existing codes with a prefix:
```bash
npm run dev -- --csv data/your.csv --renamePrefix MOB- --renamePadLength 3 --renameStart 1 --email your@email --password "***" --headless=false --dryRun=false
```

- Rename using a mapping CSV (`old,new`):
```bash
npm run dev -- --pairsCsv logs/outreach_pairs.csv --email your@email --password "***" --dryRun=false
```

- Update discount percent for existing codes:
```bash
npm run dev -- --csv data/your.csv --updateDiscountPercent 40 --dryRun=false
```

- Generate applied-diff report between two XLSX exports:
```bash
npm run dev -- --diffOld data/old.xlsx --diffNew data/new.xlsx
```

### Flags (selection)
- Credentials: `--email`, `--password`
- Data inputs: `--csv`, `--xlsx`, `--codeColumn`, `--createdColumn`
- Behavior: `--dryRun`, `--headless`, `--manualLogin`, `--storageState auth/state.json`
- Rename: `--renamePrefix`, `--renameLimit`, `--renamePadLength`, `--renameStart`, `--codeRegex`, `--skipRows`, `--skipAlreadyPrefixed`
- From list: `--listCsv`, `--listDelimiter`, `--listColumn`, `--listStartsWith`, `--listSkip`
- Limits: `--limitPerOrder`, `--limitPerTicket`, `--onlyUpdateLimit`
- Output: `--logsDir`

### Notes
- The automation stores session in `auth/state.json` if available to skip repeat logins.
- Logs and reports are written under `logs/` with timestamps.

### Archived email/Gmail tools
Legacy outreach scripts were moved to `archive/email_outreach/` for reference. They are not required for Fienta code management.


