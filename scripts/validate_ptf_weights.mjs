import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const rawDir = path.join(root, "data", "raw");
const processedDir = path.join(root, "data", "processed");

// Correspondencia entre las 61 agrupaciones CIIU Rev. 4 de los cuadros
// oferta-utilización y los nueve agregados KLEMS en CIIU Rev. 3/3.1.
// La recuperación de materiales (columna 43) pertenece a manufactura en
// CIIU Rev. 3; la evacuación de aguas residuales y los desechos (columna 42)
// pertenecen a servicios sociales, comunales y personales.
const productionColumns = new Map([
  ["Agricultura", [5, 6, 7, 8, 9]],
  ["Minería", [10, 11, 12, 13, 14]],
  [
    "Manufactura",
    [...Array.from({ length: 24 }, (_, index) => index + 15), 43],
  ],
  ["Electricidad, gas y agua", [39, 40, 41]],
  ["Construcción", [44, 45, 46]],
  ["Comercio, hoteles y restaurantes", [47, 48, 54]],
  ["Transporte y comunicaciones", [49, 50, 51, 52, 53, 55]],
  ["Finanzas e inmobiliarias", [56, 57, 58, 59]],
  ["Servicios sociales", [42, 60, 61, 62, 63, 64, 65]],
]);

const activityOrder = [...productionColumns.keys()];
const grossOutputRows = [];
const grossOutputShares = new Map();

for (const [firstYear, lastYear, filename] of [
  [2005, 2013, "dane_cou_precios_corrientes_2005_2013.xlsx"],
  [2014, 2024, "dane_cou_precios_corrientes_2014_2024.xlsx"],
]) {
  const workbook = await SpreadsheetFile.importXlsx(
    await FileBlob.load(path.join(rawDir, filename)),
  );
  for (let year = firstYear; year <= lastYear; year += 1) {
    const sheetNumber = 2 * (year - firstYear) + 2;
    const values = workbook.worksheets
      .getItem(`Cuadro ${sheetNumber}`)
      .getUsedRange(true).values;
    const productionRow = values.find(
      (row) => String(row[1] ?? "").trim() === "Total producción",
    );
    if (!productionRow) {
      throw new Error(`No se encontró la fila Total producción para ${year}`);
    }

    const levels = new Map();
    for (const [activity, columns] of productionColumns) {
      levels.set(
        activity,
        columns.reduce((sum, column) => sum + Number(productionRow[column]), 0),
      );
    }
    const total = [...levels.values()].reduce((sum, value) => sum + value, 0);
    const shares = new Map();
    for (const activity of activityOrder) {
      const grossOutput = levels.get(activity);
      const share = grossOutput / total;
      shares.set(activity, share);
      grossOutputRows.push({
        year,
        activity,
        gross_output_nominal_billion_cop: grossOutput,
        gross_output_share: share,
      });
    }
    grossOutputShares.set(year, shares);
  }
}

const implicitCsv = await fs.readFile(
  path.join(processedDir, "ptf_pesos_contribuciones_anual.csv"),
  "utf8",
);
const implicitRows = [];
for (const line of implicitCsv
  .replace(/^\uFEFF/, "")
  .trim()
  .split(/\r?\n/)
  .slice(1)) {
  const match = line.match(
    /^(\d{4}),(?:"([^"]+)"|([^,]+)),([^,]+),([^,]+),([^,]+)$/,
  );
  if (!match) throw new Error(`Fila inesperada: ${line}`);
  implicitRows.push({
    year: Number(match[1]),
    activity: match[2] ?? match[3],
    implicit_weight: Number(match[4]),
    sector_ptf: Number(match[5]),
    contribution: Number(match[6]),
  });
}

let maximumAbsoluteDifference = 0;
let squaredDifference = 0;
let validationObservations = 0;
const validationRows = [];
for (const row of implicitRows) {
  const share = grossOutputShares.get(row.year).get(row.activity);
  const directWeight =
    row.year === 2005
      ? ""
      : (grossOutputShares.get(row.year - 1).get(row.activity) + share) / 2;
  const difference =
    directWeight === "" ? "" : row.implicit_weight - directWeight;
  if (difference !== "") {
    maximumAbsoluteDifference = Math.max(
      maximumAbsoluteDifference,
      Math.abs(difference),
    );
    squaredDifference += difference ** 2;
    validationObservations += 1;
  }
  validationRows.push({
    year: row.year,
    activity: row.activity,
    gross_output_share: share,
    tornqvist_weight_from_published_gross_output: directWeight,
    implicit_exact_weight: row.implicit_weight,
    difference_percentage_points: difference === "" ? "" : difference * 100,
    sector_ptf: row.sector_ptf,
    contribution: row.contribution,
  });
}

const rootMeanSquaredDifference = Math.sqrt(
  squaredDifference / validationObservations,
);
if (
  validationObservations !== 171 ||
  maximumAbsoluteDifference > 5e-6 ||
  rootMeanSquaredDifference > 1e-6
) {
  throw new Error(
    "Los pesos implícitos no coinciden con las participaciones de la " +
      `producción nominal: n=${validationObservations}, ` +
      `máximo=${maximumAbsoluteDifference}, rmse=${rootMeanSquaredDifference}`,
  );
}

const escapeCsv = (value) => {
  const text = String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
};
const writeCsv = async (filename, header, rows) => {
  const csv = [
    header.join(","),
    ...rows.map((row) =>
      header.map((field) => escapeCsv(row[field])).join(","),
    ),
  ].join("\n");
  await fs.writeFile(
    path.join(processedDir, filename),
    `\uFEFF${csv}\n`,
    "utf8",
  );
};

await writeCsv(
  "ptf_vbp_nominal_por_actividad.csv",
  [
    "year",
    "activity",
    "gross_output_nominal_billion_cop",
    "gross_output_share",
  ],
  grossOutputRows,
);
await writeCsv(
  "ptf_pesos_validacion_vbp.csv",
  [
    "year",
    "activity",
    "gross_output_share",
    "tornqvist_weight_from_published_gross_output",
    "implicit_exact_weight",
    "difference_percentage_points",
    "sector_ptf",
    "contribution",
  ],
  validationRows,
);
await writeCsv(
  "ptf_pesos_validacion_resumen.csv",
  [
    "first_year",
    "last_year",
    "observations",
    "maximum_absolute_difference_share",
    "maximum_absolute_difference_percentage_points",
    "root_mean_squared_difference_share",
  ],
  [
    {
      first_year: 2006,
      last_year: 2024,
      observations: validationObservations,
      maximum_absolute_difference_share: maximumAbsoluteDifference,
      maximum_absolute_difference_percentage_points:
        maximumAbsoluteDifference * 100,
      root_mean_squared_difference_share: rootMeanSquaredDifference,
    },
  ],
);

console.log(
  JSON.stringify(
    {
      observations: validationObservations,
      maximumAbsoluteDifferenceShare: maximumAbsoluteDifference,
      maximumAbsoluteDifferencePercentagePoints:
        maximumAbsoluteDifference * 100,
      rootMeanSquaredDifferenceShare: rootMeanSquaredDifference,
      note:
        "El peso directo de 2005 no se calcula porque la serie pública " +
        "Base 2015 de producción nominal comienza en 2005.",
    },
    null,
    2,
  ),
);
