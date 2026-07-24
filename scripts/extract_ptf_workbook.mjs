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
const outputDir = path.join(root, "data", "processed");

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

// Estas ocho columnas son algebraicamente independientes. Junto con la
// restricción de que los pesos suman uno, identifican los nueve pesos anuales.
const independentFields = [
  "production",
  "labor_composition",
  "hours",
  "capital_tic",
  "capital_non_tic",
  "energy",
  "materials",
  "services",
];

const activityNames = new Map([
  ["Agricultura, ganadería, caza, silvicultura y pesca", "Agricultura"],
  ["Minería y extracción", "Minería"],
  ["Industrias manufactureras", "Manufactura"],
  ["Electricidad, gas y agua", "Electricidad, gas y agua"],
  ["Construcción", "Construcción"],
  ["Comercio, hoteles y restaurantes", "Comercio, hoteles y restaurantes"],
  [
    "Transporte, almacenamiento y comunicaciones",
    "Transporte y comunicaciones",
  ],
  [
    "Intermediación financiera, actividades inmobiliarias, empresariales y de alquiler",
    "Finanzas e inmobiliarias",
  ],
  [
    "Actividades de servicios sociales, comunales y personales",
    "Servicios sociales",
  ],
]);

const cleanLabel = (value) =>
  typeof value === "string" ? value.trim().replaceAll("\u00A0", "") : "";

const solveLinearSystem = (matrix, vector) => {
  const n = vector.length;
  const augmented = matrix.map((row, index) => [...row, vector[index]]);
  for (let pivot = 0; pivot < n; pivot += 1) {
    let best = pivot;
    for (let row = pivot + 1; row < n; row += 1) {
      if (Math.abs(augmented[row][pivot]) > Math.abs(augmented[best][pivot])) {
        best = row;
      }
    }
    if (Math.abs(augmented[best][pivot]) < 1e-12) {
      throw new Error(`Sistema singular en la columna ${pivot}`);
    }
    [augmented[pivot], augmented[best]] = [
      augmented[best],
      augmented[pivot],
    ];
    const divisor = augmented[pivot][pivot];
    for (let col = pivot; col <= n; col += 1) {
      augmented[pivot][col] /= divisor;
    }
    for (let row = 0; row < n; row += 1) {
      if (row === pivot) continue;
      const factor = augmented[row][pivot];
      for (let col = pivot; col <= n; col += 1) {
        augmented[row][col] -= factor * augmented[pivot][col];
      }
    }
  }
  return augmented.map((row) => row[n]);
};

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
  await fs.writeFile(path.join(outputDir, filename), `\uFEFF${csv}\n`, "utf8");
};

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const sectorObservations = [];
const totalObservations = [];

for (let year = 2005; year <= 2024; year += 1) {
  const sheet = workbook.worksheets.getItem(`Cuadro ${year - 2001}`);
  const values = sheet.getUsedRange(true).values;
  for (const row of values) {
    const label = cleanLabel(row[1]);
    if (!activityNames.has(label) && label !== "Total de la economía") continue;
    if (typeof row[2] !== "number") continue;
    const observation = {
      year,
      activity_full: label,
      activity:
        label === "Total de la economía"
          ? "Total de la economía"
          : activityNames.get(label),
    };
    fields.forEach((field, index) => {
      observation[field] = Number(row[index + 2]);
    });
    if (label === "Total de la economía") {
      totalObservations.push(observation);
    } else {
      sectorObservations.push(observation);
    }
  }
}

if (sectorObservations.length !== 180 || totalObservations.length !== 20) {
  throw new Error(
    `Cobertura inesperada: ${sectorObservations.length} filas sectoriales y ` +
      `${totalObservations.length} filas del total`,
  );
}

const activityOrder = [...activityNames.values()];
const weightRows = [];
const indexRows = [];
const periodDefinitions = [
  [2006, 2010],
  [2011, 2015],
  [2016, 2019],
  [2020, 2024],
];

let maxReconciliationError = 0;
for (let year = 2006; year <= 2024; year += 1) {
  const sectors = activityOrder.map((activity) =>
    sectorObservations.find(
      (row) => row.year === year && row.activity === activity,
    ),
  );
  const total = totalObservations.find((row) => row.year === year);
  const matrix = independentFields.map((field) =>
    sectors.map((row) => row[field]),
  );
  matrix.push(new Array(activityOrder.length).fill(1));
  const vector = independentFields.map((field) => total[field]);
  vector.push(1);
  const weights = solveLinearSystem(matrix, vector);

  const sumWeights = weights.reduce((sum, value) => sum + value, 0);
  if (
    Math.abs(sumWeights - 1) > 1e-10 ||
    Math.min(...weights) < -1e-10 ||
    Math.max(...weights) > 1 + 1e-10
  ) {
    throw new Error(`Pesos inválidos en ${year}: ${weights.join(", ")}`);
  }

  for (const field of fields) {
    const reconstructed = sectors.reduce(
      (sum, row, index) => sum + weights[index] * row[field],
      0,
    );
    maxReconciliationError = Math.max(
      maxReconciliationError,
      Math.abs(reconstructed - total[field]),
    );
  }

  sectors.forEach((row, index) => {
    weightRows.push({
      year,
      activity: row.activity,
      weight: weights[index],
      sector_ptf: row.ptf,
      contribution: weights[index] * row.ptf,
    });
  });
}

if (maxReconciliationError > 1e-9) {
  throw new Error(
    `La agregación no reconcilia con el total: ${maxReconciliationError}`,
  );
}

for (const activity of [...activityOrder, "Total de la economía"]) {
  let index = 100;
  indexRows.push({ year: 2005, activity, ptf: "", index });
  for (let year = 2006; year <= 2024; year += 1) {
    const ptf =
      activity === "Total de la economía"
        ? totalObservations.find((row) => row.year === year).ptf
        : sectorObservations.find(
            (row) => row.year === year && row.activity === activity,
          ).ptf;
    index *= Math.exp(ptf / 100);
    indexRows.push({ year, activity, ptf, index });
  }
}

const mean = (values) =>
  values.reduce((sum, value) => sum + value, 0) / values.length;

const longRunRows = activityOrder.map((activity) => {
  const rows = weightRows.filter((row) => row.activity === activity);
  const index2024 = indexRows.find(
    (row) => row.activity === activity && row.year === 2024,
  ).index;
  return {
    activity,
    average_weight: mean(rows.map((row) => row.weight)),
    average_sector_ptf: mean(rows.map((row) => row.sector_ptf)),
    average_contribution: mean(rows.map((row) => row.contribution)),
    cumulative_log_contribution: rows.reduce(
      (sum, row) => sum + row.contribution,
      0,
    ),
    ptf_index_2024: index2024,
  };
});

const totalRows = totalObservations.filter(
  (row) => row.year >= 2006 && row.year <= 2024,
);
const totalIndex2024 = indexRows.find(
  (row) => row.activity === "Total de la economía" && row.year === 2024,
).index;
longRunRows.push({
  activity: "Total de la economía",
  average_weight: 1,
  average_sector_ptf: mean(totalRows.map((row) => row.ptf)),
  average_contribution: mean(totalRows.map((row) => row.ptf)),
  cumulative_log_contribution: totalRows.reduce(
    (sum, row) => sum + row.ptf,
    0,
  ),
  ptf_index_2024: totalIndex2024,
});

const periodRows = [];
for (const [start, end] of periodDefinitions) {
  for (const activity of activityOrder) {
    const rows = weightRows.filter(
      (row) =>
        row.activity === activity && row.year >= start && row.year <= end,
    );
    periodRows.push({
      period: `${start}-${end}`,
      start,
      end,
      activity,
      average_weight: mean(rows.map((row) => row.weight)),
      average_sector_ptf: mean(rows.map((row) => row.sector_ptf)),
      average_contribution: mean(rows.map((row) => row.contribution)),
    });
  }
}

await fs.mkdir(outputDir, { recursive: true });
await writeCsv(
  "ptf_actividad_anual.csv",
  ["year", "activity_full", "activity", ...fields],
  sectorObservations,
);
await writeCsv(
  "ptf_total_economia_anual.csv",
  ["year", "activity_full", "activity", ...fields],
  totalObservations,
);
await writeCsv(
  "ptf_pesos_contribuciones_anual.csv",
  ["year", "activity", "weight", "sector_ptf", "contribution"],
  weightRows,
);
await writeCsv(
  "ptf_contribucion_largo_plazo.csv",
  [
    "activity",
    "average_weight",
    "average_sector_ptf",
    "average_contribution",
    "cumulative_log_contribution",
    "ptf_index_2024",
  ],
  longRunRows,
);
await writeCsv(
  "ptf_contribucion_subperiodos.csv",
  [
    "period",
    "start",
    "end",
    "activity",
    "average_weight",
    "average_sector_ptf",
    "average_contribution",
  ],
  periodRows,
);
await writeCsv(
  "ptf_indices_encadenados.csv",
  ["year", "activity", "ptf", "index"],
  indexRows,
);

console.log(
  `Extracción completa: ${sectorObservations.length} filas sectoriales, ` +
    `${totalObservations.length} filas del total y error máximo de ` +
    `reconciliación=${maxReconciliationError}`,
);
