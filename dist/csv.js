"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.readCsv = readCsv;
const fs_1 = __importDefault(require("fs"));
const csv_parse_1 = require("csv-parse");
async function readCsv(filePath, delimiter = ',') {
    return new Promise((resolve, reject) => {
        const records = [];
        fs_1.default.createReadStream(filePath)
            .pipe((0, csv_parse_1.parse)({
            columns: true,
            skip_empty_lines: true,
            trim: true,
            delimiter,
        }))
            .on('data', (row) => records.push(row))
            .on('end', () => resolve(records))
            .on('error', (err) => reject(err));
    });
}
