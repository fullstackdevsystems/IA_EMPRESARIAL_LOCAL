"""Deterministic GA.2 checks for the customer-facing package policy."""
from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "MANIFEST_SHA256.json"


class CommercialHygieneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The root manifest is a frozen release authority.
        # Tests may inspect it but must never regenerate it
        # from a mutable development worktree.
        cls.paths = {
            item["path"]
            for item in json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
        }

    def test_customer_manifest_excludes_development_and_token_utilities(self):
        forbidden = (
            "IA_Local/MOSTRAR_TOKEN_LOCAL.bat",
            "IA_Local/LEEME_PRIMERO.txt",
            "IA_Local/README_INSTALACION.txt",
            "IA_Local/GUIA_PRUEBAS_MEMORIA_RAG_V8.md",
            "IA_Local/ARQUITECTURA_MEMORIA_RAG_V8.md",
            "IA_Local/PROMPT_ANALISIS_MELAZA.txt",
            "IA_Local/PROMPT_PRUEBA_EXCEL.txt",
            "IA_Local/scripts/run_enterprise_tests.py",
            "IA_Local/scripts/prueba_regresion_v7.py",
        )
        self.assertTrue(self.paths.isdisjoint(forbidden))
        self.assertFalse(any(path.startswith("IA_Local/tests/") for path in self.paths))

    def test_customer_manifest_is_deterministic_runtime_allowlist(self):
        required = {
            "INSTALAR_IA_EMPRESARIAL_LOCAL.bat",
            "InstalarLimpio.ps1",
            "InstallerR1020C1.ps1",
            "OperarIA.ps1",
            "LEEME_INSTALACION_LIMPIA.txt",
            "IA_Local/scripts/analizador_universal.py",
            "IA_Local/scripts/enterprise_ai/admin_console.py",
        }
        self.assertTrue(required.issubset(self.paths))
        self.assertTrue(
            all(
                path.startswith(("IA_Local/scripts/", "IA_Local/config/", "IA_Local/data/", "IA_Local/logs/", "IA_Local/workspace/"))
                or path in required
                or path in {"RELEASE_METADATA.json", "ValidarInstalador.ps1", "IA_Local/VERSION.txt", "IA_Local/requirements-local.txt", "IA_Local/requirements-optional.txt"}
                for path in self.paths
            )
        )

    def test_customer_visible_identity_has_no_internal_phase_label(self):
        html = (ROOT / "IA_Local" / "scripts" / "enterprise_ai" / "admin_console.py").read_text(encoding="utf-8")
        self.assertNotIn("R10.10 Administración Unificada", html)
        self.assertNotIn(">Enterprise Control Plane<", html)
        self.assertIn("Administración de plataforma", html)

    def test_distributed_installation_note_has_no_legacy_r7_contract(self):
        text = (ROOT / "LEEME_INSTALACION_LIMPIA.txt").read_text(encoding="utf-8")
        for forbidden in ("V8.5.5 R7", "C:\\IA_Local", "Python 3.11", "Open WebUI"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
