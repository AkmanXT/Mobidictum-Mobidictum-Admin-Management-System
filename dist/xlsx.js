"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.readXlsx = readXlsx;
exports.extractColumn = extractColumn;
const path_1 = __importDefault(require("path"));
const fs_1 = __importDefault(require("fs"));
const XLSX = __importStar(require("xlsx"));
function normalizeHeader(key) {
    return key.trim().toLowerCase().replace(/\s+/g, '_');
}
function readXlsx(filePath) {
    const resolved = path_1.default.resolve(process.cwd(), filePath);
    if (!fs_1.default.existsSync(resolved)) {
        throw new Error(`XLSX not found: ${resolved}`);
    }
    const wb = XLSX.readFile(resolved);
    const sheetName = wb.SheetNames[0];
    const ws = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(ws, { raw: false });
    const normalizedRows = rows.map((row) => {
        const normalized = {};
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
function extractColumn(row, candidates) {
    for (const c of candidates) {
        const key = normalizeHeader(c);
        if (key in row)
            return row[key];
    }
    // try exact keys already normalized
    for (const c of candidates) {
        if (c in row)
            return row[c];
    }
    return undefined;
}
