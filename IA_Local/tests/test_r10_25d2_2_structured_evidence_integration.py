import copy
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from enterprise_ai.context_engine import ContextEngine
from enterprise_ai.evidence_governance import govern_large_evidence
from enterprise_ai.service import EnterpriseAIService


class EmptyMemory:
    def search(self, *args, **kwargs):
        return []


class EmptyDocuments:
    def search(self, *args, **kwargs):
        return []


class StructuredStub:
    def __init__(self, payload):
        self.payload = payload

    def query(self, *args, **kwargs):
        return self.payload


def principal():
    return SimpleNamespace(company_id="tenant-a", user_id="user-a")


def test_shared_authority_preserves_d2_1_contract_and_source_immutability():
    rows = [{"id": 1, "nested": [10]}, {"id": 2, "nested": [20]}]
    original = copy.deepcopy(rows)

    governed = govern_large_evidence(rows, max_rows=1)
    wrapped = EnterpriseAIService._govern_large_evidence(rows, max_rows=1)

    assert governed == wrapped
    assert governed["contract"] == "r10.25d2"
    assert governed["total_rows"] == 2
    assert governed["returned_rows"] == 1
    assert governed["truncated"] is True
    assert governed["authority"] == "governed_large_data_evidence"
    assert governed["llm_truncation_authority"] is False

    governed["rows"][0]["nested"].append(99)
    assert rows == original


def test_context_engine_governs_only_materialized_table_evidence():
    table = [{"group": f"G{i}", "value": i} for i in range(30)]
    structured = {
        "insufficient": False,
        "table": table,
        "metric": "sales",
        "operation": "top",
        "source": {"type": "dataset", "file": "ventas.csv"},
        "plan": {"operation": "top"},
    }
    original = copy.deepcopy(structured)

    engine = ContextEngine(
        EmptyMemory(),
        EmptyDocuments(),
        StructuredStub(structured),
        {
            "max_memories": 6,
            "memory_min_score": 0.20,
            "max_document_chunks": 8,
            "document_min_score": 0.18,
            "max_context_chars": 100000,
            "max_structured_evidence_rows": 20,
        },
    )

    built = engine.build(principal(), "ventas por producto")

    assert built.structured == original
    assert structured == original
    assert len(built.structured["table"]) == 30

    assert "RESULTADO TABULAR GOBERNADO" in built.evidence_text
    assert "filas=20/30" in built.evidence_text
    assert "truncado=True" in built.evidence_text
    assert "autoridad=governed_large_data_evidence" in built.evidence_text

    assert "'group': 'G19'" in built.evidence_text
    assert "'group': 'G20'" not in built.evidence_text


def test_context_engine_does_not_change_scalar_calculation_results():
    structured = {
        "insufficient": False,
        "value": 987654.32,
        "metric": "sales",
        "operation": "sum",
        "rows_used": 500000,
        "source": {
            "type": "dataset",
            "file": "ventas.csv",
            "calculation": "python/pandas",
        },
        "plan": {"operation": "sum"},
    }

    engine = ContextEngine(
        EmptyMemory(),
        EmptyDocuments(),
        StructuredStub(structured),
        {"max_context_chars": 100000},
    )

    built = engine.build(principal(), "ventas totales")

    assert built.structured == structured
    assert built.structured["value"] == 987654.32
    assert built.structured["rows_used"] == 500000
    assert "987654.32" in built.evidence_text
    assert "RESULTADO TABULAR GOBERNADO" not in built.evidence_text
