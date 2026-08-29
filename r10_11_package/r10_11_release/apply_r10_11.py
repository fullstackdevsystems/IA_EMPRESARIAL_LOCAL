from __future__ import annotations

from pathlib import Path
import re
import shutil
import sys

VERSION = "8.5.5-r10.11-large-data"


def patch_structured(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "try_execute_large_query" not in text:
        anchor = "        df, sheet = self._load(dataset)\n"
        replacement = (
            "        # R10.11: para CSV grandes, ejecutar agregaciones exactas por chunks antes de cargar todo a RAM.\n"
            "        try:\n"
            "            from .performance import try_execute_large_query\n"
            "            fast_result = try_execute_large_query(\n"
            "                dataset, plan, principal=principal, prompt=prompt, analytics=self.analytics, precedence=self.precedence\n"
            "            )\n"
            "            if fast_result is not None:\n"
            "                try:\n"
            "                    trace_step(\n"
            "                        fast_result.get('trace_id'), 'large_data_execution',\n"
            "                        {'engine':'python/pandas-chunked','exact':True,'source':fast_result.get('source',{}),'performance':fast_result.get('performance',{})}\n"
            "                    )\n"
            "                except Exception:\n"
            "                    pass\n"
            "                return fast_result\n"
            "        except Exception:\n"
            "            # Compatibilidad: si la optimizacion no aplica, conserva la ruta productiva existente.\n"
            "            pass\n"
            "        df, sheet = self._load(dataset)\n"
        )
        if anchor not in text:
            raise RuntimeError("No se encontro ancla _load en structured_data.py")
        text = text.replace(anchor, replacement, 1)
    path.write_text(text, encoding="utf-8")


def patch_api(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "/api/enterprise/performance" not in text:
        anchor = '    @router.get("/api/enterprise/audit")\n'
        block = '''    @router.get("/api/enterprise/performance")\n    def enterprise_performance(principal: Principal = Depends(admin_dependency)):\n        from .performance import optional_engines\n        return {\n            "ok": True,\n            "version": "8.5.5-r10.11-large-data",\n            "engines": optional_engines(),\n            "policy": {\n                "large_csv": "streaming exacto por chunks",\n                "profiling": "muestra controlada permitida",\n                "business_metrics": "siempre exactas",\n                "governed_rules": "fallback a evaluador completo para conservar semantica",\n            },\n        }\n\n'''
        if anchor not in text:
            raise RuntimeError("No se encontro ancla audit en api.py")
        text = text.replace(anchor, block + anchor, 1)
    text = text.replace('"version": "8.5.5-r10.10-unified-admin"', f'"version": "{VERSION}"')
    path.write_text(text, encoding="utf-8")


def patch_version(root: Path) -> None:
    (root / "VERSION.txt").write_text(VERSION + "\n", encoding="utf-8")


def main(root_arg: str) -> int:
    root = Path(root_arg).resolve()
    ent = root / "scripts" / "enterprise_ai"
    if not ent.exists():
        raise SystemExit(f"Raiz IA_Local invalida: {root}")
    src = Path(__file__).resolve().parent / "performance.py"
    shutil.copy2(src, ent / "performance.py")
    patch_structured(ent / "structured_data.py")
    patch_api(ent / "api.py")
    patch_version(root)
    print("R10.11 patch OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
