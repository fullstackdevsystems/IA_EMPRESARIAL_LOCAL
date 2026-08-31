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
print("=== R10.13D.7.1.1 BAR VISIBILITY ===")

check(
    "bar_fill_exists",
    ".r13b-bar-fill{" in rt,
)

check(
    "bar_fill_display_block",
    ".r13b-bar-fill{\n    display:block;" in rt,
)

check(
    "bar_fill_has_height",
    "height:100%;" in rt,
)

check(
    "bar_fill_has_gradient",
    "background:linear-gradient(90deg,#0a93a4,#19b8c4);" in rt,
)

check(
    "bars_card_preserved",
    "function barsCard(" in rt,
)

check(
    "dimension_chart_preserved",
    "chartOperator==='dimension_bar_chart'" in rt,
)

check(
    "chart_html_preserved",
    "${chartHtml}" in rt,
)

print()
print("PASS R10.13D.7.1.1 VISIBLE DIMENSION BARS")
