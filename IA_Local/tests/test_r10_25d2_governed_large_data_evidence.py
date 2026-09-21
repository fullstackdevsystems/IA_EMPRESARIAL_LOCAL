import copy

from IA_Local.scripts.enterprise_ai.service import EnterpriseAIService


def test_small_evidence_is_preserved():
    rows = [
        {"period": "2026-01", "revenue": 100.0},
        {"period": "2026-02", "revenue": 200.0},
    ]

    source = copy.deepcopy(rows)

    result = EnterpriseAIService._govern_large_evidence(
        rows,
        max_rows=2000,
    )

    assert result["rows"] == rows
    assert result["total_rows"] == 2
    assert result["returned_rows"] == 2
    assert result["truncated"] is False
    assert result["source"] == "executed_results"
    assert result["authority"] == "governed_large_data_evidence"
    assert rows == source


def test_large_evidence_is_deterministically_bounded():
    rows = [
        {"id": index, "revenue": float(index)}
        for index in range(10)
    ]

    result = EnterpriseAIService._govern_large_evidence(
        rows,
        max_rows=3,
    )

    assert result["total_rows"] == 10
    assert result["returned_rows"] == 3
    assert result["truncated"] is True
    assert result["rows"] == rows[:3]


def test_source_evidence_is_immutable():
    rows = [
        {"id": 1, "values": [10, 20]},
        {"id": 2, "values": [30, 40]},
    ]

    source = copy.deepcopy(rows)

    result = EnterpriseAIService._govern_large_evidence(
        rows,
        max_rows=1,
    )

    result["rows"][0]["values"].append(999)

    assert rows == source
