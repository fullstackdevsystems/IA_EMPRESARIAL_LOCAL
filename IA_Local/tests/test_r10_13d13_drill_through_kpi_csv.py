from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dynamic_renderer import runtime_markup


def check(name, cond):
    if not cond:
        print(f"FAIL {name}")
        raise AssertionError(name)
    print(f"PASS {name}")


rt = runtime_markup()

print()
print("=== R10.13D.13 DRILL-THROUGH KPI SUMMARY AND CSV EXPORT ===")

check(
    "d12_modal_preserved",
    "r13bDrillThroughModal" in rt
    and "function openDrillThrough(" in rt,
)

check(
    "canonical_metric_summary",
    "function drillThroughMetricSummary(" in rt
    and "businessMetricDefinitions()" in rt
    and "aggregateMetric(" in rt,
)

check(
    "summary_uses_contextual_rows",
    "drillThroughMetricSummary(" in rt
    and "contextualRows" in rt,
)

check(
    "kpi_summary_markup",
    "r13b-drill-through-kpis" in rt
    and "r13b-drill-through-kpi" in rt,
)

check(
    "canonical_formatting",
    "fmt(" in rt
    and "metric.format" in rt,
)

check(
    "export_button",
    "data-r13b-drill-through-export" in rt
    and "Exportar CSV" in rt,
)

check(
    "export_state",
    "drillThroughCurrentRows" in rt
    and "drillThroughCurrentCols" in rt
    and "drillThroughCurrentLabel" in rt,
)

check(
    "csv_escape",
    "function csvCell(" in rt
    and "replace(" in rt
    and "'\"\"'" in rt,
)

# dynamic_renderer.py contiene "\\ufeff" dentro de una cadena Python.
# Al ejecutar runtime_markup(), Python lo materializa como "\ufeff" literal
# o conserva la secuencia escapada segÃºn cÃ³mo haya quedado serializado.
# Ambas representaciones son funcionalmente vÃ¡lidas para el BOM UTF-8.
check(
    "csv_utf8_bom",
    ("\\ufeff" in rt)
    or ("\ufeff" in rt),
)

check(
    "csv_blob_download",
    "new Blob(" in rt
    and "URL.createObjectURL(" in rt
    and "detalle_contextual_" in rt,
)

check(
    "export_exact_context_rows",
    "drillThroughCurrentRows=" in rt
    and "contextualRows.slice()" in rt,
)

check(
    "empty_context_disables_export_data",
    "drillThroughCurrentRows=[];" in rt
    and "drillThroughCurrentCols=[];" in rt,
)

check(
    "d11_multifilter_preserved",
    "function renderDrillFilterBar()" in rt
    and "data-r13b-clear-all-drills" in rt,
)

check(
    "d10_filter_preserved",
    "node.onclick=applyDrill;" in rt,
)

check(
    "d8_d9_controls_preserved",
    "data-r13b-dimension-metric" in rt
    and "data-r13b-dimension-topn" in rt
    and "data-r13b-dimension-order" in rt
    and "data-r13b-dimension-view" in rt,
)

check(
    "no_dimension_id_dispatch",
    "id.startsWith('analysis:dimension_')" not in rt,
)

print()
print("PASS R10.13D.13 DRILL-THROUGH KPI SUMMARY AND CSV EXPORT")

