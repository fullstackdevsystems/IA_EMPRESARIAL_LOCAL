import tempfile
from pathlib import Path

from enterprise_ai.database import Database
from enterprise_ai.knowledge_governance import KnowledgeGovernance
from enterprise_ai.security import Principal


def run():
    with tempfile.TemporaryDirectory() as td:
        db=Database(Path(td)/"enterprise.db")
        kg=KnowledgeGovernance(db)
        a=Principal("EMPRESA_A","admin","admin")
        b=Principal("EMPRESA_B","admin","admin")

        r1=kg.propose_rule(a,name="UTILIDAD_REAL",expression="Venta - Costo",area="Ventas",valid_from="2025-01-01",valid_to="2025-12-31")
        assert r1["status"]=="PROPUESTO"
        kg.validate_rule(a,r1["id"])
        assert kg.applicable_rules(a,area="Ventas",on_date="2025-06-01")[0]["expression"]=="Venta - Costo"
        assert kg.applicable_rules(a,area="Ventas",on_date="2026-06-01")==[]
        assert kg.list_rules(b)==[]

        r2=kg.propose_rule(a,name="UTILIDAD_REAL",expression="Venta - Costo - Flete",area="Ventas",valid_from="2025-06-01",valid_to="2025-12-31")
        assert len(kg.detect_rule_conflicts(a,r2["id"]))==1
        try:
            kg.validate_rule(a,r2["id"])
        except ValueError as exc:
            assert "CONFLICTO" in str(exc)
        else:
            raise AssertionError("debio bloquear conflicto")
        kg.validate_rule(a,r2["id"],replace_conflicts=True)
        assert kg.get_rule(a,r1["id"],include_nonvalidated=True)["status"]=="OBSOLETO"

        s1=kg.propose_semantic_definition(a,physical_name="Cve_Clie",semantic_name="cliente_id",data_type="ID",area="Ventas")
        kg.validate_semantic_definition(a,s1["id"])
        assert kg.resolve_semantic(a,"Cve_Clie")["semantic_name"]=="cliente_id"
        assert kg.resolve_semantic(b,"Cve_Clie") is None

        s2=kg.propose_semantic_definition(a,physical_name="Cve_Clie",semantic_name="proveedor_id")
        assert len(kg.detect_semantic_conflicts(a,s2["id"]))==1
        kg.reject_semantic_definition(a,s2["id"])
        assert kg.get_semantic_definition(a,s2["id"],include_nonvalidated=True)["status"]=="RECHAZADO"

        prov=kg.provenance(a,"business_rule",r2["id"])
        assert prov["current"]["status"]=="VALIDADO" and len(prov["history"])>=2

    print("PASS persistence_schema")
    print("PASS company_isolation")
    print("PASS temporal_validity")
    print("PASS rule_conflict_detection")
    print("PASS semantic_dictionary_conflict")
    print("PASS provenance_history")
    print("6/6 PASS R10.3 KNOWLEDGE GOVERNANCE")

if __name__ == "__main__":
    run()
