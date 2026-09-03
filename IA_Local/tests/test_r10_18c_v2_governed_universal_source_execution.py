from pathlib import Path
import hashlib
import sys
import tempfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"

if str(S) not in sys.path:
    sys.path.insert(0, str(S))

from enterprise_source_execution import (
    execute_uploaded_file_source_with_reader,
)


def check(name, cond):
    if not cond:
        print("FAIL", name)
        raise AssertionError(name)
    print("PASS", name)


print()
print("=== R10.18C V2 GOVERNED UNIVERSAL SOURCE EXECUTION ===")

with tempfile.TemporaryDirectory() as td:
    root = Path(td)

    source = root / "demo.csv"
    source.write_text(
        "Cliente,Venta\nA,10\nB,20\n",
        encoding="utf-8",
    )

    expected = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()

    def reader(path):
        df = pd.read_csv(path)

        return df, {
            "archivo": path.name,
            "extension": ".csv",
            "hojas": ["CSV"],
            "hoja_analizada": "CSV",
            "motor_excel": None,
            "hojas_info": [],
        }

    opened = execute_uploaded_file_source_with_reader(
        path=source,
        workspace_root=root,
        reader=reader,
    )

    check(
        "opened",
        opened.get("status") == "OPENED",
    )

    check(
        "rows",
        len(opened.get("dataframe")) == 2,
    )

    prov = opened.get("provenance") or {}

    check(
        "fingerprint_present",
        len(
            str(
                prov.get("fingerprint_sha256")
                or ""
            )
        ) == 64,
    )

    check(
        "fingerprint_matches",
        prov.get("fingerprint_sha256")
        == expected,
    )

    check(
        "reader_mode",
        prov.get("reader_mode")
        == "universal_governed_reader",
    )

    check(
        "governance",
        bool(
            (
                opened.get("governance")
                or {}
            ).get(
                "universal_reader_governed"
            )
        ),
    )

    outside = root.parent / "r10_18c_outside.csv"

    outside.write_text(
        "A\n1\n",
        encoding="utf-8",
    )

    try:
        blocked = execute_uploaded_file_source_with_reader(
            path=outside,
            workspace_root=root,
            reader=reader,
        )

        check(
            "outside_workspace_blocked",
            blocked.get("status")
            == "BLOCKED",
        )

    finally:
        outside.unlink(
            missing_ok=True
        )


universal = (
    S / "analizador_universal.py"
).read_text(
    encoding="utf-8",
    errors="replace",
)

check(
    "no_direct_bypass",
    "original, meta = load_tabular(path, prompt)"
    not in universal,
)

check(
    "uses_governed_wrapper",
    "execute_uploaded_file_source_with_reader("
    in universal,
)

check(
    "publishes_source_execution",
    'meta["source_execution"] = '
    'public_source_execution_metadata(source_execution)'
    in universal,
)

check(
    "fingerprint_flows_to_manifest",
    "_source_fingerprint_from_meta(meta)"
    in universal,
)

print()
print(
    "PASS R10.18C V2 GOVERNED UNIVERSAL SOURCE EXECUTION"
)
