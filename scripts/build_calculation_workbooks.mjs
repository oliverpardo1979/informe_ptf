import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const processedDir = path.join(root, "data", "processed");
const rawDir = path.join(root, "data", "raw");
const outputDir = path.join(root, "outputs", "ptf_pesos_vbp_20260727");
const previewDir = path.join(outputDir, "previews");
await fs.mkdir(previewDir, { recursive: true });

const MAGENTA = "#C00055";
const MAGENTA_DARK = "#8F003F";
const GRAY_DARK = "#4B5563";
const GRAY_MID = "#D1D5DB";
const GRAY_LIGHT = "#F3F4F6";
const GRAY_ALT = "#E5E7EB";
const TEXT = "#1F2937";
const INPUT_BLUE = "#1F4E78";
const FORMULA_GREEN = "#375623";
const WHITE = "#FFFFFF";
const RED_LIGHT = "#FDE8E7";
const GREEN_LIGHT = "#E2F0D9";
const ORANGE_LIGHT = "#FFF2CC";

const sourceUrls = {
  ptf:
    "https://www.dane.gov.co/files/operaciones/PTF/anex-PTF-Productividad-2025.xlsx",
  methodology:
    "https://www.dane.gov.co/files/investigaciones/boletines/pib/productividad/doc-metodologico-PTF-productividad-total-factores-2021.pdf",
  couEarly:
    "https://www.dane.gov.co/files/investigaciones/boletines/pib/cuentas-nal-anuales/oferta-utilizacion-precios-corrientes-2005-2013.xlsx",
  couLate:
    "https://www.dane.gov.co/files/operaciones/PIB/anex-CuentasNalANuales-OfertaUtilizacionPreciosCorrientes-2024p.xlsx",
  repository: "https://github.com/oliverpardo1979/informe_ptf",
};

const parseCsv = (text) => {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  const input = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < input.length; index += 1) {
    const character = input[index];
    if (quoted) {
      if (character === '"' && input[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        field += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  const [header, ...data] = rows.filter(
    (candidate) => candidate.length > 1 || candidate[0] !== "",
  );
  return data.map((values) =>
    Object.fromEntries(header.map((name, index) => [name, values[index] ?? ""])),
  );
};

const readCsv = async (filename) =>
  parseCsv(await fs.readFile(path.join(processedDir, filename), "utf8"));

const asNumber = (value) => (value === "" ? null : Number(value));
const vaRows = (await readCsv("ptf_valor_agregado_total_anual.csv")).map(
  (row) => ({
    ...row,
    year: Number(row.year),
    gross_value_added: Number(row.gross_value_added),
    labor: Number(row.labor),
    capital: Number(row.capital),
    factors: Number(row.factors),
    ptf: Number(row.ptf),
  }),
);
const activityRows = (await readCsv("ptf_actividad_anual.csv")).map((row) => ({
  ...row,
  year: Number(row.year),
  ptf: Number(row.ptf),
}));
const totalRows = (await readCsv("ptf_total_economia_anual.csv")).map((row) => ({
  ...row,
  year: Number(row.year),
  production: Number(row.production),
  factors: Number(row.factors),
  ptf: Number(row.ptf),
}));
const weightRows = (await readCsv("ptf_pesos_validacion_vbp.csv")).map(
  (row) => ({
    ...row,
    year: Number(row.year),
    gross_output_share: Number(row.gross_output_share),
    tornqvist_weight_from_published_gross_output: asNumber(
      row.tornqvist_weight_from_published_gross_output,
    ),
    implicit_exact_weight: Number(row.implicit_exact_weight),
    difference_percentage_points: asNumber(
      row.difference_percentage_points,
    ),
    sector_ptf: Number(row.sector_ptf),
    contribution: Number(row.contribution),
  }),
);
const grossOutputRows = (
  await readCsv("ptf_vbp_nominal_por_actividad.csv")
).map((row) => ({
  ...row,
  year: Number(row.year),
  gross_output_nominal_billion_cop: Number(
    row.gross_output_nominal_billion_cop,
  ),
}));
const validationSummary = (
  await readCsv("ptf_pesos_validacion_resumen.csv")
)[0];

const activityOrder = [
  "Agricultura",
  "Minería",
  "Manufactura",
  "Electricidad, gas y agua",
  "Construcción",
  "Comercio, hoteles y restaurantes",
  "Transporte y comunicaciones",
  "Finanzas e inmobiliarias",
  "Servicios sociales",
];
const displayLabel = new Map([
  ["Agricultura", "Agropecuario"],
  ["Minería", "Minería"],
  ["Manufactura", "Manufactura"],
  ["Electricidad, gas y agua", "Servicios públicos"],
  ["Construcción", "Construcción"],
  ["Comercio, hoteles y restaurantes", "Comercio y hotelería"],
  ["Transporte y comunicaciones", "Transporte y comunicaciones"],
  ["Finanzas e inmobiliarias", "Finanzas"],
  ["Servicios sociales", "Servicios sociales y personales"],
  ["Total de la economía", "Total de la economía"],
]);
const activityLongRunOrder = [
  "Minería",
  "Finanzas e inmobiliarias",
  "Construcción",
  "Electricidad, gas y agua",
  "Manufactura",
  "Transporte y comunicaciones",
  "Servicios sociales",
  "Agricultura",
  "Comercio, hoteles y restaurantes",
  "Total de la economía",
];
const outputLookup = new Map(
  grossOutputRows.map((row) => [
    `${row.year}|${row.activity}`,
    row.gross_output_nominal_billion_cop,
  ]),
);
const rateLookup = new Map(
  activityRows.map((row) => [`${row.year}|${row.activity}`, row.ptf]),
);
const totalLookup = new Map(totalRows.map((row) => [row.year, row]));

const columnName = (index) => {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
};

const setColumnWidths = (sheet, widths, rowCount = 250) => {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, rowCount, 1).format.columnWidthPx = width;
  });
};

const styleTitle = (sheet, range, title) => {
  sheet.mergeCells(range);
  const topLeft = range.split(":")[0];
  sheet.getRange(topLeft).values = [[title]];
  sheet.getRange(range).format = {
    fill: MAGENTA,
    font: { name: "Aptos", size: 16, bold: true, color: WHITE },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeightPx = 34;
};

const styleSubtitle = (sheet, range, subtitle) => {
  sheet.mergeCells(range);
  const topLeft = range.split(":")[0];
  sheet.getRange(topLeft).values = [[subtitle]];
  sheet.getRange(range).format = {
    fill: GRAY_LIGHT,
    font: { name: "Aptos", size: 10, italic: true, color: TEXT },
    wrapText: true,
    verticalAlignment: "center",
  };
  sheet.getRange(range).format.rowHeightPx = 30;
};

const styleHeader = (range) => {
  range.format = {
    fill: GRAY_DARK,
    font: { name: "Aptos", size: 9, bold: true, color: WHITE },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: GRAY_MID },
  };
  range.format.rowHeightPx = 34;
};

const styleBody = (range) => {
  range.format.font.name = "Aptos";
  range.format.font.size = 9;
  range.format.font.color = TEXT;
  range.format.verticalAlignment = "center";
  range.format.borders = {
    insideHorizontal: { style: "thin", color: GRAY_MID },
    edgeBottom: { style: "thin", color: GRAY_MID },
  };
};

const bandRows = (sheet, firstRow, lastRow, firstCol, colCount) => {
  for (let row = firstRow; row <= lastRow; row += 1) {
    if ((row - firstRow) % 2 === 1) {
      sheet
        .getRangeByIndexes(row - 1, firstCol - 1, 1, colCount)
        .format.fill.color = GRAY_LIGHT;
    }
  }
};

const addGuideSheet = (workbook, sourceFileLabel) => {
  const sheet = workbook.worksheets.add("CJC Guía");
  sheet.showGridLines = false;
  styleTitle(
    sheet,
    "A1:H1",
    "Cálculos y validación del informe sobre Productividad Total de los Factores",
  );
  styleSubtitle(
    sheet,
    "A2:H2",
    `Hojas agregadas por el CJC a ${sourceFileLabel}. Los cuadros originales del DANE no fueron modificados.`,
  );

  sheet.getRange("A4:B4").values = [["Resultado de la auditoría", "Conclusión"]];
  styleHeader(sheet.getRange("A4:B4"));
  sheet.getRange("A5:B9").values = [
    [
      "Ponderador correcto",
      "Promedio Törnqvist de la participación de cada actividad en el valor bruto de producción (VBP) nominal.",
    ],
    [
      "Fórmula",
      "w(i,t) = 0,5 × [VBP(i,t−1)/VBP(t−1) + VBP(i,t)/VBP(t)].",
    ],
    [
      "Validación 2006–2024",
      `171 comparaciones. Diferencia máxima frente al peso implícito exacto: ${(
        Number(
          validationSummary.maximum_absolute_difference_percentage_points,
        ) || 0
      ).toFixed(5)} puntos porcentuales.`,
    ],
    [
      "Año 2005",
      "El COU público Base 2015 comienza en 2005; por eso el peso directo de 2005 requeriría el VBP nominal de 2004. Para ese año se conserva el peso implícito exacto.",
    ],
    [
      "Decisión de cálculo",
      "Las contribuciones usan los pesos implícitos de alta precisión porque reproducen exactamente los trece componentes del total del DANE. Los VBP publicados están redondeados y se usan como validación independiente.",
    ],
  ];
  styleBody(sheet.getRange("A5:B9"));
  sheet.getRange("B5:B9").format.wrapText = true;
  sheet.getRange("A5:A9").format.font.bold = true;

  sheet.getRange("A11:B11").values = [["Advertencia documental", "Lectura"]];
  styleHeader(sheet.getRange("A11:B11"));
  sheet.getRange("A12:B12").values = [
    [
      "Nota al pie del anexo PTF",
      "Aunque el anexo menciona la composición del valor agregado, la comparación con los cuadros oferta-utilización no respalda esos pesos. Los pesos que reproducen el total coinciden con las participaciones del VBP nominal.",
    ],
  ];
  sheet.getRange("A12:B12").format.fill.color = ORANGE_LIGHT;
  sheet.getRange("A12:B12").format.wrapText = true;
  styleBody(sheet.getRange("A12:B12"));
  sheet.getRange("A12:B12").format.rowHeightPx = 50;

  sheet.getRange("A14:B14").values = [["Fuente", "Enlace"]];
  styleHeader(sheet.getRange("A14:B14"));
  sheet.getRange("A15:B19").values = [
    ["Anexo PTF 2025 del DANE", sourceUrls.ptf],
    ["Nota metodológica de la PTF", sourceUrls.methodology],
    ["COU a precios corrientes 2005–2013", sourceUrls.couEarly],
    ["COU a precios corrientes 2014–2024", sourceUrls.couLate],
    ["Repositorio del informe", sourceUrls.repository],
  ];
  styleBody(sheet.getRange("A15:B19"));
  sheet.getRange("B15:B19").format.wrapText = true;

  sheet.getRange("D4:H4").values = [
    ["Hoja", "Contenido", "Periodo", "Uso principal", "Colores"],
  ];
  styleHeader(sheet.getRange("D4:H4"));
  sheet.getRange("D5:H10").values = [
    [
      "CJC VA total",
      "PTF y descomposición del total bajo valor agregado",
      "2005–2025",
      "Figuras 1 y 2; contrafactual de PTF +1 pp",
      "Azul: dato DANE; verde: fórmula",
    ],
    [
      "CJC PTF actividad",
      "Tasas e índices encadenados de nueve actividades y del total",
      "2004–2024",
      "Figuras 3 y 4",
      "Azul: dato DANE; verde: fórmula",
    ],
    [
      "CJC Pesos VBP",
      "VBP nominal, participaciones, pesos y contribuciones anuales",
      "2005–2024",
      "Auditoría de ponderadores",
      "Rojo/verde: signo de contribución",
    ],
    [
      "CJC Contribuciones",
      "Contribuciones acumuladas y anualizadas; cascada",
      "2005–2024",
      "Figuras 5 y 6",
      "Negativo/positivo",
    ],
    [
      "CJC Figuras",
      "Mapa de cada figura a su rango de cálculo",
      "—",
      "Trazabilidad",
      "—",
    ],
    [
      "Archivo de productividad laboral",
      "Las hojas CJC de PTF se agregan también al segundo anexo para que ambos archivos entregados conserven la misma carpeta de cálculos.",
      "—",
      "Referencia; no cambia la fuente estadística de las figuras PTF",
      "—",
    ],
  ];
  styleBody(sheet.getRange("D5:H10"));
  sheet.getRange("D5:H10").format.wrapText = true;
  bandRows(sheet, 5, 10, 4, 5);

  sheet.getRange("D12:E14").values = [
    ["Convención", "Formato"],
    ["Dato copiado de una fuente", "Fuente azul"],
    ["Celda calculada", "Fuente verde"],
  ];
  styleHeader(sheet.getRange("D12:E12"));
  styleBody(sheet.getRange("D13:E14"));
  sheet.getRange("E13").format.font.color = INPUT_BLUE;
  sheet.getRange("E14").format.font.color = FORMULA_GREEN;

  setColumnWidths(sheet, [190, 600, 24, 180, 260, 110, 250, 160], 30);
  sheet.freezePanes.freezeRows(2);
  return sheet;
};

const addValueAddedSheet = (workbook) => {
  const sheet = workbook.worksheets.add("CJC VA total");
  sheet.showGridLines = false;
  styleTitle(
    sheet,
    "A1:R1",
    "PTF y crecimiento del total de la economía: enfoque de valor agregado",
  );
  styleSubtitle(
    sheet,
    "A2:R2",
    "Tasas logarítmicas del DANE. Los índices parten de 100 en 2004 y se encadenan con EXP(tasa/100).",
  );

  const headers = [
    "Año",
    "Crecimiento VAB (%)",
    "Trabajo (pp)",
    "Capital (pp)",
    "Factores (pp)",
    "PTF (pp)",
    "Índice VAB observado",
    "Índice PTF observado",
    "Índice VAB si PTF +1 pp",
    "Brecha vs. observado (%)",
  ];
  sheet.getRange("A5:J5").values = [headers];
  styleHeader(sheet.getRange("A5:J5"));
  sheet.getRange("A6:F26").values = vaRows.map((row) => [
    row.year,
    row.gross_value_added,
    row.labor,
    row.capital,
    row.factors,
    row.ptf,
  ]);
  sheet.getRange("A6:F26").format.font.color = INPUT_BLUE;
  for (let index = 0; index < vaRows.length; index += 1) {
    const row = index + 6;
    const previous = row - 1;
    sheet.getRange(`G${row}`).formulas = [
      [
        index === 0
          ? `=100*EXP(B${row}/100)`
          : `=G${previous}*EXP(B${row}/100)`,
      ],
    ];
    sheet.getRange(`H${row}`).formulas = [
      [
        index === 0
          ? `=100*EXP(F${row}/100)`
          : `=H${previous}*EXP(F${row}/100)`,
      ],
    ];
    sheet.getRange(`I${row}`).formulas = [
      [
        index === 0
          ? `=100*EXP((B${row}+1)/100)`
          : `=I${previous}*EXP((B${row}+1)/100)`,
      ],
    ];
    sheet.getRange(`J${row}`).formulas = [[`=I${row}/G${row}-1`]];
  }
  styleBody(sheet.getRange("A6:J26"));
  bandRows(sheet, 6, 26, 1, 10);
  sheet.getRange("B6:F26").format.numberFormat = "0.00";
  sheet.getRange("G6:I26").format.numberFormat = "0.00";
  sheet.getRange("J6:J26").format.numberFormat = "0.00%";
  sheet.getRange("G6:J26").format.font.color = FORMULA_GREEN;

  sheet.getRange("L5:M5").values = [["Indicador", "Resultado"]];
  styleHeader(sheet.getRange("L5:M5"));
  sheet.getRange("L6:L14").values = [
    ["Crecimiento anualizado VAB (%)"],
    ["Contribución anualizada trabajo (pp)"],
    ["Contribución anualizada capital (pp)"],
    ["Contribución anualizada factores (pp)"],
    ["Crecimiento anualizado PTF (%)"],
    ["Crecimiento acumulado VAB (%)"],
    ["Crecimiento acumulado PTF (%)"],
    ["Crecimiento VAB contrafactual (%)"],
    ["Brecha de nivel en 2025 (%)"],
  ];
  sheet.getRange("M6:M14").formulas = [
    ["=AVERAGE(B6:B26)"],
    ["=AVERAGE(C6:C26)"],
    ["=AVERAGE(D6:D26)"],
    ["=AVERAGE(E6:E26)"],
    ["=AVERAGE(F6:F26)"],
    ["=G26/100-1"],
    ["=H26/100-1"],
    ["=M6+1"],
    ["=J26"],
  ];
  styleBody(sheet.getRange("L6:M14"));
  sheet.getRange("M6:M10").format.numberFormat = "0.00";
  sheet.getRange("M11:M12").format.numberFormat = "0.00%";
  sheet.getRange("M13").format.numberFormat = "0.00";
  sheet.getRange("M14").format.numberFormat = "0.00%";
  sheet.getRange("M6:M14").format.font.color = FORMULA_GREEN;

  sheet.getRange("O5:R5").values = [
    ["Paso de la cascada", "Tipo", "Aporte/nivel (pp)", "Resultado (%)"],
  ];
  styleHeader(sheet.getRange("O5:R5"));
  sheet.getRange("O6:P10").values = [
    ["Trabajo", "Aumento"],
    ["Capital", "Aumento"],
    ["Crecimiento sin PTF", "Total"],
    ["PTF", "Disminución"],
    ["Crecimiento observado", "Total"],
  ];
  sheet.getRange("Q6:Q10").formulas = [
    ["=M7"],
    ["=M8"],
    ["=M9"],
    ["=M10"],
    ["=M6"],
  ];
  sheet.getRange("R6:R10").formulas = [
    ["=Q6"],
    ["=R6+Q7"],
    ["=Q8"],
    ["=R8+Q9"],
    ["=Q10"],
  ];
  styleBody(sheet.getRange("O6:R10"));
  sheet.getRange("Q6:R10").format.numberFormat = "0.00";
  sheet.getRange("Q6:R10").format.font.color = FORMULA_GREEN;
  sheet.getRange("O8:R8").format.fill.color = GRAY_ALT;
  sheet.getRange("O10:R10").format.fill.color = MAGENTA;
  sheet.getRange("O10:R10").format.font.color = WHITE;
  sheet.getRange("O10:R10").format.font.bold = true;

  setColumnWidths(
    sheet,
    [
      70, 120, 95, 95, 95, 90, 120, 120, 135, 125, 20, 280, 120, 20, 200,
      100, 120, 120,
    ],
    35,
  );
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(1);
  return sheet;
};

const addActivitySheet = (workbook) => {
  const sheet = workbook.worksheets.add("CJC PTF actividad");
  sheet.showGridLines = false;
  styleTitle(
    sheet,
    "A1:Q1",
    "Evolución de la PTF por actividad económica: enfoque de producción",
  );
  styleSubtitle(
    sheet,
    "A2:Q2",
    "Las 20 tasas del DANE conectan el índice de 2004 con el de 2024. El total de la economía se presenta en la última columna.",
  );

  const rateActivities = [...activityOrder, "Total de la economía"];
  sheet.getRange("A5:K5").values = [
    ["Año", ...rateActivities.map((activity) => displayLabel.get(activity))],
  ];
  styleHeader(sheet.getRange("A5:K5"));
  const rateValues = [];
  for (let year = 2005; year <= 2024; year += 1) {
    rateValues.push([
      year,
      ...activityOrder.map((activity) => rateLookup.get(`${year}|${activity}`)),
      totalLookup.get(year).ptf,
    ]);
  }
  sheet.getRange("A6:K25").values = rateValues;
  sheet.getRange("A6:K25").format.font.color = INPUT_BLUE;
  sheet.getRange("B6:K25").format.numberFormat = "0.00";
  styleBody(sheet.getRange("A6:K25"));
  bandRows(sheet, 6, 25, 1, 11);
  sheet.getRange("B6:K25").conditionalFormats.add("cellIs", {
    operator: "lessThan",
    formula: 0,
    format: { fill: RED_LIGHT, font: { color: "#9C0006" } },
  });
  sheet.getRange("B6:K25").conditionalFormats.add("cellIs", {
    operator: "greaterThan",
    formula: 0,
    format: { fill: GREEN_LIGHT, font: { color: "#006100" } },
  });

  sheet.getRange("A29:K29").values = [
    ["Año", ...rateActivities.map((activity) => displayLabel.get(activity))],
  ];
  styleHeader(sheet.getRange("A29:K29"));
  sheet.getRange("A30:K30").values = [[2004, ...new Array(10).fill(100)]];
  for (let index = 0; index < 20; index += 1) {
    const row = index + 31;
    const previous = row - 1;
    const rateRow = index + 6;
    sheet.getRange(`A${row}`).values = [[2005 + index]];
    for (let column = 1; column <= 10; column += 1) {
      const letter = columnName(column);
      sheet.getRange(`${letter}${row}`).formulas = [
        [`=${letter}${previous}*EXP(${letter}${rateRow}/100)`],
      ];
    }
  }
  styleBody(sheet.getRange("A30:K50"));
  bandRows(sheet, 30, 50, 1, 11);
  sheet.getRange("B30:K50").format.numberFormat = "0.00";
  sheet.getRange("B31:K50").format.font.color = FORMULA_GREEN;

  const summaryRowByActivity = new Map();
  sheet.getRange("M5:Q5").values = [
    [
      "Actividad",
      "Crecimiento acumulado (%)",
      "Tasa anualizada (%)",
      "Años con PTF positiva",
      "Índice 2024",
    ],
  ];
  styleHeader(sheet.getRange("M5:Q5"));
  for (let index = 0; index < activityLongRunOrder.length; index += 1) {
    const activity = activityLongRunOrder[index];
    const row = index + 6;
    summaryRowByActivity.set(activity, row);
    const column = rateActivities.indexOf(activity) + 1;
    const letter = columnName(column);
    sheet.getRange(`M${row}`).values = [[displayLabel.get(activity)]];
    sheet.getRange(`N${row}:Q${row}`).formulas = [
      [
        `=${letter}$50/100-1`,
        `=AVERAGE(${letter}$6:${letter}$25)`,
        `=COUNTIF(${letter}$6:${letter}$25,">0")`,
        `=${letter}$50`,
      ],
    ];
  }
  styleBody(sheet.getRange("M6:Q15"));
  bandRows(sheet, 6, 15, 13, 5);
  sheet.getRange("N6:N15").format.numberFormat = "0.00%";
  sheet.getRange("O6:O15").format.numberFormat = "0.00";
  sheet.getRange("P6:P15").format.numberFormat = "0";
  sheet.getRange("Q6:Q15").format.numberFormat = "0.00";
  sheet.getRange("N6:Q15").format.font.color = FORMULA_GREEN;
  sheet.getRange("M15:Q15").format.fill.color = MAGENTA;
  sheet.getRange("M15:Q15").format.font.color = WHITE;
  sheet.getRange("M15:Q15").format.font.bold = true;

  setColumnWidths(
    sheet,
    [70, 105, 85, 95, 105, 100, 120, 145, 90, 155, 120, 20, 205, 145, 120, 110, 95],
    60,
  );
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(1);
  return { sheet, summaryRowByActivity };
};

const addWeightsSheet = (workbook) => {
  const sheet = workbook.worksheets.add("CJC Pesos VBP");
  sheet.showGridLines = false;
  styleTitle(
    sheet,
    "A1:M1",
    "Ponderadores Törnqvist y contribuciones anuales por actividad",
  );
  styleSubtitle(
    sheet,
    "A2:M2",
    "El peso directo usa el promedio de las participaciones del VBP nominal en t−1 y t. El peso implícito reproduce exactamente los totales publicados por el DANE.",
  );
  sheet.getRange("A5:I5").values = [
    [
      "Año",
      "Actividad",
      "VBP nominal (miles de millones de pesos)",
      "Participación VBP (%)",
      "Peso Törnqvist directo (%)",
      "Peso implícito exacto (%)",
      "Diferencia (p. p.)",
      "PTF de la actividad (%)",
      "Contribución a la PTF total (pp)",
    ],
  ];
  styleHeader(sheet.getRange("A5:I5"));

  const orderedWeights = [...weightRows].sort(
    (left, right) =>
      left.year - right.year ||
      activityOrder.indexOf(left.activity) -
        activityOrder.indexOf(right.activity),
  );
  sheet.getRange("A6:C185").values = orderedWeights.map((row) => [
    row.year,
    displayLabel.get(row.activity),
    outputLookup.get(`${row.year}|${row.activity}`),
  ]);
  sheet.getRange("F6:F185").values = orderedWeights.map((row) => [
    row.implicit_exact_weight,
  ]);
  sheet.getRange("H6:H185").values = orderedWeights.map((row) => [
    row.sector_ptf,
  ]);
  sheet.getRange("A6:C185").format.font.color = INPUT_BLUE;
  sheet.getRange("F6:F185").format.font.color = INPUT_BLUE;
  sheet.getRange("H6:H185").format.font.color = INPUT_BLUE;

  for (let index = 0; index < orderedWeights.length; index += 1) {
    const row = index + 6;
    sheet.getRange(`D${row}`).formulas = [
      [`=C${row}/SUMIF($A$6:$A$185,A${row},$C$6:$C$185)`],
    ];
    if (orderedWeights[index].year > 2005) {
      sheet.getRange(`E${row}`).formulas = [
        [`=(D${row}+D${row - 9})/2`],
      ];
      sheet.getRange(`G${row}`).formulas = [[`=(F${row}-E${row})*100`]];
    }
    sheet.getRange(`I${row}`).formulas = [[`=F${row}*H${row}`]];
  }
  styleBody(sheet.getRange("A6:I185"));
  bandRows(sheet, 6, 185, 1, 9);
  sheet.getRange("C6:C185").format.numberFormat = "#,##0";
  sheet.getRange("D6:F185").format.numberFormat = "0.00%";
  sheet.getRange("G6:G185").format.numberFormat = "0.00000";
  sheet.getRange("H6:I185").format.numberFormat = "0.00";
  sheet.getRange("D6:E185").format.font.color = FORMULA_GREEN;
  sheet.getRange("G6:G185").format.font.color = FORMULA_GREEN;
  sheet.getRange("I6:I185").format.font.color = FORMULA_GREEN;
  sheet.getRange("I6:I185").conditionalFormats.add("cellIs", {
    operator: "lessThan",
    formula: 0,
    format: { fill: RED_LIGHT, font: { color: "#9C0006" } },
  });
  sheet.getRange("I6:I185").conditionalFormats.add("cellIs", {
    operator: "greaterThan",
    formula: 0,
    format: { fill: GREEN_LIGHT, font: { color: "#006100" } },
  });

  sheet.getRange("K5:L5").values = [["Indicador de validación", "Resultado"]];
  styleHeader(sheet.getRange("K5:L5"));
  sheet.getRange("K6:K12").values = [
    ["Periodo con VBP directo"],
    ["Comparaciones"],
    ["Diferencia máxima (p. p.)"],
    ["RMSE de la diferencia en participación"],
    ["Suma de pesos implícitos por año"],
    ["Tratamiento de 2005"],
    ["Fuente de contribución"],
  ];
  sheet.getRange("L6:L12").values = [
    ["2006–2024"],
    [Number(validationSummary.observations)],
    [
      Number(
        validationSummary.maximum_absolute_difference_percentage_points,
      ),
    ],
    [Number(validationSummary.root_mean_squared_difference_share)],
    ["100%"],
    ["Peso implícito exacto; no hay VBP Base 2015 público para 2004"],
    ["Peso implícito × PTF de la actividad"],
  ];
  styleBody(sheet.getRange("K6:L12"));
  sheet.getRange("L8").format.numberFormat = "0.00000";
  sheet.getRange("L9").format.numberFormat = "0.0000000";
  sheet.getRange("L11:L12").format.wrapText = true;
  sheet.getRange("K6:K12").format.font.bold = true;

  sheet.getRange("K14:M14").values = [
    ["Actividad", "Peso implícito promedio (%)", "Contribución promedio (pp)"],
  ];
  styleHeader(sheet.getRange("K14:M14"));
  for (let index = 0; index < activityOrder.length; index += 1) {
    const row = index + 15;
    sheet.getRange(`K${row}`).values = [[displayLabel.get(activityOrder[index])]];
    sheet.getRange(`L${row}:M${row}`).formulas = [
      [
        `=AVERAGEIF($B$6:$B$185,K${row},$F$6:$F$185)`,
        `=AVERAGEIF($B$6:$B$185,K${row},$I$6:$I$185)`,
      ],
    ];
  }
  styleBody(sheet.getRange("K15:M23"));
  bandRows(sheet, 15, 23, 11, 3);
  sheet.getRange("L15:L23").format.numberFormat = "0.00%";
  sheet.getRange("M15:M23").format.numberFormat = "0.00";
  sheet.getRange("L15:M23").format.font.color = FORMULA_GREEN;

  setColumnWidths(
    sheet,
    [65, 205, 150, 110, 115, 115, 105, 110, 125, 20, 250, 220, 125],
    200,
  );
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(2);
  return sheet;
};

const addContributionSheet = (
  workbook,
  activitySummaryRowByActivity,
) => {
  const sheet = workbook.worksheets.add("CJC Contribuciones");
  sheet.showGridLines = false;
  styleTitle(
    sheet,
    "A1:Q1",
    "Contribuciones de las actividades a la PTF y al crecimiento de la producción",
  );
  styleSubtitle(
    sheet,
    "A2:Q2",
    "La contribución anual es el peso implícito exacto multiplicado por la tasa de crecimiento de la PTF de cada actividad. Las nueve contribuciones suman la PTF total.",
  );

  sheet.getRange("A5:G5").values = [
    [
      "Actividad",
      "Peso promedio (%)",
      "Crecimiento acumulado PTF (%)",
      "Tasa anualizada PTF (%)",
      "Contribución acumulada (pp)",
      "Contribución anualizada (pp)",
      "Signo",
    ],
  ];
  styleHeader(sheet.getRange("A5:G5"));

  const contributionOrder = [...activityOrder, "Total de la economía"];
  const contributionRowByActivity = new Map();
  for (let index = 0; index < contributionOrder.length; index += 1) {
    const activity = contributionOrder[index];
    const row = index + 6;
    contributionRowByActivity.set(activity, row);
    sheet.getRange(`A${row}`).values = [[displayLabel.get(activity)]];
    const activitySummaryRow = activitySummaryRowByActivity.get(activity);
    if (activity === "Total de la economía") {
      sheet.getRange(`B${row}:G${row}`).formulas = [
        [
          "=1",
          `='CJC PTF actividad'!N${activitySummaryRow}`,
          `='CJC PTF actividad'!O${activitySummaryRow}`,
          `=SUM(E6:E14)`,
          `=SUM(F6:F14)`,
          `=IF(F${row}<0,"Negativa","Positiva")`,
        ],
      ];
    } else {
      sheet.getRange(`B${row}:G${row}`).formulas = [
        [
          `=AVERAGEIF('CJC Pesos VBP'!$B$6:$B$185,A${row},'CJC Pesos VBP'!$F$6:$F$185)`,
          `='CJC PTF actividad'!N${activitySummaryRow}`,
          `='CJC PTF actividad'!O${activitySummaryRow}`,
          `=SUMIF('CJC Pesos VBP'!$B$6:$B$185,A${row},'CJC Pesos VBP'!$I$6:$I$185)`,
          `=AVERAGEIF('CJC Pesos VBP'!$B$6:$B$185,A${row},'CJC Pesos VBP'!$I$6:$I$185)`,
          `=IF(F${row}<0,"Negativa","Positiva")`,
        ],
      ];
    }
  }
  styleBody(sheet.getRange("A6:G15"));
  bandRows(sheet, 6, 15, 1, 7);
  sheet.getRange("B6:B15").format.numberFormat = "0.00%";
  sheet.getRange("C6:C15").format.numberFormat = "0.00%";
  sheet.getRange("D6:F15").format.numberFormat = "0.00";
  sheet.getRange("B6:G15").format.font.color = FORMULA_GREEN;
  sheet.getRange("A15:G15").format.fill.color = MAGENTA;
  sheet.getRange("A15:G15").format.font.color = WHITE;
  sheet.getRange("A15:G15").format.font.bold = true;
  sheet.getRange("G6:G15").conditionalFormats.add("containsText", {
    text: "Negativa",
    format: { fill: RED_LIGHT, font: { color: "#9C0006", bold: true } },
  });
  sheet.getRange("G6:G15").conditionalFormats.add("containsText", {
    text: "Positiva",
    format: { fill: GREEN_LIGHT, font: { color: "#006100", bold: true } },
  });

  sheet.getRange("I5:L5").values = [
    ["Paso de la cascada", "Tipo", "Aporte/nivel (pp)", "Resultado (%)"],
  ];
  styleHeader(sheet.getRange("I5:L5"));
  const positive = [
    "Agricultura",
    "Comercio, hoteles y restaurantes",
    "Transporte y comunicaciones",
    "Servicios sociales",
  ];
  const negative = [
    "Electricidad, gas y agua",
    "Construcción",
    "Manufactura",
    "Minería",
    "Finanzas e inmobiliarias",
  ];
  const waterfallLabels = [
    ["Crecimiento sin PTF", "Total"],
    ...positive.map((activity) => [displayLabel.get(activity), "Aumento"]),
    ["Contrafactual sin PTF negativa", "Total"],
    ...negative.map((activity) => [displayLabel.get(activity), "Disminución"]),
    ["Crecimiento observado", "Total"],
  ];
  sheet.getRange("I6:J17").values = waterfallLabels;
  sheet.getRange("K6").formulas = [["=AVERAGE(P6:P25)"]];
  sheet.getRange("L6").formulas = [["=K6"]];
  let row = 7;
  for (const activity of positive) {
    const sourceRow = contributionRowByActivity.get(activity);
    sheet.getRange(`K${row}`).formulas = [[`=F${sourceRow}`]];
    sheet.getRange(`L${row}`).formulas = [[`=L${row - 1}+K${row}`]];
    row += 1;
  }
  sheet.getRange(`K${row}`).formulas = [[`=L${row - 1}`]];
  sheet.getRange(`L${row}`).formulas = [[`=K${row}`]];
  row += 1;
  for (const activity of negative) {
    const sourceRow = contributionRowByActivity.get(activity);
    sheet.getRange(`K${row}`).formulas = [[`=F${sourceRow}`]];
    sheet.getRange(`L${row}`).formulas = [[`=L${row - 1}+K${row}`]];
    row += 1;
  }
  sheet.getRange(`K${row}`).formulas = [["=AVERAGE(O6:O25)"]];
  sheet.getRange(`L${row}`).formulas = [[`=K${row}`]];
  styleBody(sheet.getRange("I6:L17"));
  sheet.getRange("K6:L17").format.numberFormat = "0.00";
  sheet.getRange("K6:L17").format.font.color = FORMULA_GREEN;
  sheet.getRange("I11:L11").format.fill.color = GRAY_ALT;
  sheet.getRange("I11:L11").format.font.bold = true;
  sheet.getRange("I17:L17").format.fill.color = MAGENTA;
  sheet.getRange("I17:L17").format.font.color = WHITE;
  sheet.getRange("I17:L17").format.font.bold = true;

  sheet.getRange("N5:Q5").values = [
    ["Año", "Producción total (%)", "Contribución factores (pp)", "PTF total (%)"],
  ];
  styleHeader(sheet.getRange("N5:Q5"));
  sheet.getRange("N6:Q25").values = totalRows.map((item) => [
    item.year,
    item.production,
    item.factors,
    item.ptf,
  ]);
  styleBody(sheet.getRange("N6:Q25"));
  bandRows(sheet, 6, 25, 14, 4);
  sheet.getRange("N6:Q25").format.font.color = INPUT_BLUE;
  sheet.getRange("O6:Q25").format.numberFormat = "0.00";

  setColumnWidths(
    sheet,
    [205, 110, 135, 120, 125, 125, 80, 20, 215, 95, 115, 110, 20, 65, 120, 130, 105],
    35,
  );
  sheet.freezePanes.freezeRows(5);
  sheet.freezePanes.freezeColumns(1);
  return sheet;
};

const addFigureSheet = (workbook) => {
  const sheet = workbook.worksheets.add("CJC Figuras");
  sheet.showGridLines = false;
  styleTitle(sheet, "A1:F1", "Trazabilidad de las figuras del informe");
  styleSubtitle(
    sheet,
    "A2:F2",
    "Cada fila identifica el rango que contiene los datos o cálculos usados para construir la figura.",
  );
  sheet.getRange("A5:F5").values = [
    ["Figura", "Contenido", "Hoja", "Rango", "Cálculo central", "Periodo"],
  ];
  styleHeader(sheet.getRange("A5:F5"));
  sheet.getRange("A6:F11").values = [
    [
      "Figura 1",
      "Tasa anual de crecimiento de la PTF del total bajo valor agregado",
      "CJC VA total",
      "A5:F26",
      "Serie anual del DANE; columna F",
      "2005–2025",
    ],
    [
      "Figura 2",
      "Cascada de la descomposición del crecimiento del valor agregado",
      "CJC VA total",
      "O5:R10",
      "Promedios de trabajo, capital, factores, PTF y VAB",
      "2005–2025",
    ],
    [
      "Figura 3",
      "Mapa de tasas anuales de PTF por actividad",
      "CJC PTF actividad",
      "A5:K25",
      "20 tasas por actividad y total",
      "2005–2024",
    ],
    [
      "Figura 4",
      "Crecimiento acumulado y tasa anualizada por actividad",
      "CJC PTF actividad",
      "M5:Q15",
      "Índice encadenado y promedio de tasas logarítmicas",
      "2004–2024",
    ],
    [
      "Figura 5",
      "Contribuciones acumuladas y anualizadas a la PTF total",
      "CJC Contribuciones",
      "A5:G15",
      "Peso anual × PTF anual; suma y promedio por actividad",
      "2005–2024",
    ],
    [
      "Figura 6",
      "Cascada desde el crecimiento sin PTF hasta el observado",
      "CJC Contribuciones",
      "I5:L17",
      "Factores + contribuciones positivas + contribuciones negativas",
      "2005–2024",
    ],
  ];
  styleBody(sheet.getRange("A6:F11"));
  bandRows(sheet, 6, 11, 1, 6);
  sheet.getRange("A6:F11").format.wrapText = true;
  setColumnWidths(sheet, [85, 360, 160, 100, 360, 100], 20);
  sheet.freezePanes.freezeRows(5);
  return sheet;
};

const addCalculationSheets = (workbook, sourceFileLabel) => {
  const guide = addGuideSheet(workbook, sourceFileLabel);
  const valueAdded = addValueAddedSheet(workbook);
  const { sheet: activity, summaryRowByActivity } = addActivitySheet(workbook);
  const weights = addWeightsSheet(workbook);
  const contributions = addContributionSheet(
    workbook,
    summaryRowByActivity,
  );
  const figures = addFigureSheet(workbook);
  return [guide, valueAdded, activity, weights, contributions, figures];
};

const sources = [
  {
    key: "ptf",
    source: path.join(rawDir, "anex-PTF-Productividad-2025.xlsx"),
    label: "anex-PTF-Productividad-2025.xlsx",
    output: path.join(
      outputDir,
      "anex-PTF-Productividad-2025_con_calculos_CJC.xlsx",
    ),
  },
  {
    key: "laboral",
    source: path.join(rawDir, "anex-PTF-ProductividadLaboral-2025.xlsx"),
    label: "anex-PTF-ProductividadLaboral-2025.xlsx",
    output: path.join(
      outputDir,
      "anex-PTF-ProductividadLaboral-2025_con_calculos_CJC.xlsx",
    ),
  },
];

for (const source of sources) {
  const workbook = await SpreadsheetFile.importXlsx(
    await FileBlob.load(source.source),
  );
  const addedSheets = addCalculationSheets(workbook, source.label);

  for (const sheet of addedSheets) {
    const preview = await workbook.render({
      sheetName: sheet.name,
      autoCrop: "all",
      scale: 1,
      format: "png",
    });
    await fs.writeFile(
      path.join(
        previewDir,
        `${source.key}_${sheet.name.replaceAll(" ", "_")}.png`,
      ),
      new Uint8Array(await preview.arrayBuffer()),
    );
  }

  const formulaCheck = await workbook.inspect({
    kind: "formula",
    sheetId: "CJC Pesos VBP",
    range: "D5:I30",
    maxChars: 8000,
    options: { maxResults: 200 },
  });
  console.log(`FORMULAS ${source.key}`);
  console.log(formulaCheck.ndjson);

  const contributionCheck = await workbook.inspect({
    kind: "region",
    sheetId: "CJC Contribuciones",
    range: "A5:Q25",
    maxChars: 16000,
    tableMaxRows: 30,
    tableMaxCols: 18,
    tableMaxCellChars: 120,
  });
  console.log(`CONTRIBUTIONS ${source.key}`);
  console.log(contributionCheck.ndjson);

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 200 },
    summary: `Escaneo final de errores ${source.key}`,
  });
  console.log(`ERRORS ${source.key}`);
  console.log(errors.ndjson);

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(source.output);
  console.log(source.output);
}
