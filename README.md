# Productividad Total de los Factores por actividad económica

Informe del Centro Javeriano de Competitividad sobre la evolución de la
Productividad Total de los Factores en Colombia entre 2005 y 2024. El análisis
encadena las variaciones anuales del enfoque de producción y descompone la PTF
del total de la economía entre nueve actividades económicas.

## Reproducibilidad

La fuente primaria se conserva en
`data/raw/anex-PTF-Productividad-2025.xlsx`. Para reconstruir las bases
procesadas, los cuadros y las figuras:

```powershell
node scripts/extract_ptf_workbook.mjs
python scripts/build_ptf_data.py
python scripts/build_ptf_paper_figures.py
```

El primer script extrae las series de las nueve actividades y del total de la
economía bajo el enfoque de producción, así como la serie agregada del enfoque
de valor agregado. También recupera las ponderaciones anuales de Törnqvist,
verifica que reproduzcan las trece columnas publicadas por el DANE y calcula la
contribución de cada actividad a la PTF total. El segundo script construye los
indicadores de largo plazo, calcula los contrafactuales y genera los cuadros y
figuras del informe. El tercer script genera las figuras en inglés utilizadas
por el paper.

Los cálculos sectoriales usan los cuadros anuales del enfoque de producción y
el bloque macroeconómico usa el Cuadro 1 del enfoque de valor agregado. El
cambio entre los niveles de 2004 y 2024 se construye con las 20 tasas
logarítmicas correspondientes a 2005--2024. La observación rotulada 2005 mide
el crecimiento entre 2004 y 2005 y se incluye como el primer año.

Los documentos principales son:

- `main.tex`: informe técnico.
- `paper.tex`: paper académico en inglés, preparado para Overleaf.
- `comunicado_prensa_ptf.tex`: comunicado de prensa.

El PDF compilado del paper se conserva en
`Paper/Pardo_Orozco_SectoralTFP_Colombia.pdf`.
