import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const inputPath = path.join(
  root,
  "data",
  "raw",
  "anex-PTF-Productividad-2025.xlsx",
);
const outputPath = path.join(
  root,
  "data",
  "processed",
  "ptf_total_economia_anual.csv",
);

const fields = [
  "production",
  "labor_composition",
  "hours",
  "labor",
  "capital_tic",
  "capital_non_tic",
  "capital",
  "energy",
  "materials",
  "services",
  "intermediate",
  "factors",
  "ptf",
];

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const observations = [];

for (let year = 2005; year <= 2024; year += 1) {
  const sheet = workbook.worksheets.getItem(`Cuadro ${year - 2001}`);
  const values = sheet.getUsedRange(true).values;
  const totalRow = values.find((row) => {
    const label = typeof row[1] === "string" ? row[1].trim() : "";
    return label.startsWith("Total de la econom");
  });
  if (!totalRow || typeof totalRow[14] !== "number") {
    throw new Error(`No se encontró el total de la economía para ${year}`);
  }
  const observation = { year, activity: "Total de la economía" };
  fields.forEach((field, index) => {
    observation[field] = Number(totalRow[index + 2]);
  });
  observations.push(observation);
}

const header = ["year", "activity", ...fields];
const escapeCsv = (value) => {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const csv = [
  header.join(","),
  ...observations.map((row) =>
    header.map((field) => escapeCsv(row[field])).join(","),
  ),
].join("\n");

await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.writeFile(outputPath, `\uFEFF${csv}\n`, "utf8");

const maxIdentityError = Math.max(
  ...observations.map((d) => Math.abs(d.production - d.factors - d.ptf)),
);
console.log(
  `Total economía: ${observations.length} observaciones; error máximo de identidad=${maxIdentityError}`,
);
