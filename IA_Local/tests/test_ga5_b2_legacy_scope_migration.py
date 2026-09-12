"""Deterministic GA.5-B2 coverage for the explicit legacy-scope upgrade tool."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from enterprise_ai.database import Database
from enterprise_ai.documents import DocumentService
from enterprise_ai.structured_data import StructuredDataService
from enterprise_ai.security import Principal
from enterprise_deliverable_registry import GovernedDeliverableRegistry
from enterprise_identity import EnterpriseIdentityStore
from enterprise_knowledge_store import EnterpriseKnowledgeStore
from enterprise_legacy_scope_migration import LegacyScopeMigrationError, LegacyScopeMigrator
from enterprise_sql_gateway import EnterpriseSqlConnectionStore
from enterprise_tenant_registry import EnterpriseTenantRegistry
from enterprise_ai.vector_store import SQLiteVectorStore, QdrantVectorStore


SOURCE = {"company_id": "empresa-local", "user_id": "admin-local", "business_unit": None, "branch": None}
TARGET = {"company_id": "tenant-a", "user_id": "target-admin", "business_unit": None, "branch": None}
DOC_VECTORS = ("3a4d3d0c-40d4-5e1c-a35d-2d2d4e7e9071", "5f51c3b3-a0c1-5b9b-89e4-5d916a3dd4a2")


def manifest() -> dict:
    value = {"status": "READY", "request": {"prompt_sha256": "a" * 64, "requested_formats": ["html"]}, "source": {}, "governance": {"output_intent_enforced": True}}
    value["manifest_fingerprint_sha256"] = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return value


def fixture(root: Path, *, legacy: bool = True, registry: bool = False) -> tuple[LegacyScopeMigrator, Path]:
    reports = root / "workspace" / "Reportes"
    tenants = EnterpriseTenantRegistry(reports / ".tenants")
    tenants.create(tenant_id="tenant-a", name="Tenant A")
    identities = EnterpriseIdentityStore(reports / ".identity", tenants)
    identities.create_user(user_id="target-admin", username="target-admin", display_name="Target", password="long-password-123", tenant_id="tenant-a", roles=["SYSTEM_ADMIN"])
    if legacy:
        artifact = reports / "legacy.html"; artifact.parent.mkdir(parents=True, exist_ok=True); artifact.write_text("<h1>legacy</h1>", encoding="utf-8")
        GovernedDeliverableRegistry(reports).register(scope=SOURCE, run_id="legacy-run", manifest=manifest(), outputs={"html": "legacy.html"})
        EnterpriseKnowledgeStore(reports / ".knowledge").register_knowledge(scope=SOURCE, knowledge_id="legacy-note", knowledge_type="governed_note", title="Legacy", content="Contenido legado", source={"source": "fixture"}, provenance={"origin": "fixture"})
        EnterpriseSqlConnectionStore(reports / ".sql_connections").register(scope=SOURCE, connection_id="legacy-sql", server="safe-server", database="safe-db", auth_mode="SQL_AUTH", credential_ref="fixture-secret-reference", secret_reference="fixture-secret-reference", username="fixture-user", allowed_schemas=["dbo"], allowed_tables=["dbo.Table"])
        db = Database(root / "data" / "enterprise" / "enterprise_ai.sqlite3")
        db.execute("INSERT INTO memories(id,company_id,user_id,scope,category,content,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", ("legacy-memory", "empresa-local", "admin-local", "user", "fact", "legacy", "now", "now"))
        SQLiteVectorStore(root / "data" / "enterprise" / "vectors.sqlite3").upsert("memory", "legacy-vector", [1.0, 0.0], {"company_id": "empresa-local", "user_id": "admin-local", "scope": "user"})
        knowledge = root / "workspace" / "Conocimiento" / "empresa-local" / "legacy-document"
        knowledge.mkdir(parents=True, exist_ok=True)
        first = knowledge / "v1_sales.txt"; first.write_bytes(b"sales version one")
        second = knowledge / "v2_sales.txt"; second.write_bytes(b"sales version two")
        first_hash = hashlib.sha256(first.read_bytes()).hexdigest(); second_hash = hashlib.sha256(second.read_bytes()).hexdigest()
        db.execute("INSERT INTO documents(id,company_id,user_id,scope,name,stored_path,extension,mime_type,size_bytes,current_hash,current_version,status,active,added_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("legacy-document", "empresa-local", "admin-local", "user", "Sales", str(second), ".txt", "text/plain", second.stat().st_size, second_hash, 2, "ready", 1, "admin-local", "now", "now"))
        db.execute("INSERT INTO document_versions(id,document_id,version,file_hash,stored_path,indexed_at,chunk_count,metadata_json) VALUES(?,?,?,?,?,?,?,?)", ("legacy-v1", "legacy-document", 1, first_hash, str(first), "now", 1, json.dumps({"origin": "fixture"})))
        db.execute("INSERT INTO document_versions(id,document_id,version,file_hash,stored_path,indexed_at,chunk_count,metadata_json) VALUES(?,?,?,?,?,?,?,?)", ("legacy-v2", "legacy-document", 2, second_hash, str(second), "now", 2, json.dumps({"origin": "fixture"})))
        for ordinal, vector_id, text in ((0, DOC_VECTORS[0], "sales one"), (1, DOC_VECTORS[1], "sales two")):
            db.execute("INSERT INTO document_chunks(id,vector_id,document_id,version,ordinal,text_hash,content,page,sheet,section,row_range,injection_flag,active,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"legacy-chunk-{ordinal}", vector_id, "legacy-document", 2, ordinal, hashlib.sha256(text.encode()).hexdigest(), text, ordinal + 1, None, None, None, 0, 1, "{}", "now"))
            SQLiteVectorStore(root / "data" / "enterprise" / "vectors.sqlite3").upsert("document", vector_id, [float(ordinal), 1.0], {"company_id": "empresa-local", "user_id": "admin-local", "scope": "user", "document_id": "legacy-document"})
        qdrant = QdrantVectorStore(root / "data" / "enterprise" / "qdrant")
        try:
            qdrant.upsert("document", DOC_VECTORS[0], [0.0, 1.0], {"company_id": "empresa-local", "user_id": "admin-local", "scope": "user", "document_id": "legacy-document"})
            qdrant.upsert("document", DOC_VECTORS[1], [1.0, 1.0], {"company_id": "empresa-local", "user_id": "admin-local", "scope": "user", "document_id": "legacy-document"})
        finally:
            qdrant.close()
        dataset = root / "workspace" / "Conocimiento" / "empresa-local" / "legacy-dataset.csv"; dataset.write_bytes(b"amount,customer\n10,A\n")
        dataset_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
        db.execute("INSERT INTO datasets(id,company_id,user_id,scope,name,path,file_hash,sheet,columns_json,roles_json,metadata_json,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("legacy-dataset", "empresa-local", "admin-local", "user", "Sales dataset", str(dataset), dataset_hash, "CSV", json.dumps(["amount", "customer"]), json.dumps({"sales": "amount"}), json.dumps({"provenance": "fixture"}), 1, "now", "now"))
        for ordinal in (2, 3):
            document_id = f"legacy-document-{ordinal}"
            directory = root / "workspace" / "Conocimiento" / "empresa-local" / document_id; directory.mkdir(parents=True, exist_ok=True)
            physical = directory / f"v1_{ordinal}.txt"; physical.write_bytes(f"document-{ordinal}".encode())
            digest = hashlib.sha256(physical.read_bytes()).hexdigest(); vector_id = str(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL, document_id))
            db.execute("INSERT INTO documents(id,company_id,user_id,scope,name,stored_path,extension,mime_type,size_bytes,current_hash,current_version,status,active,added_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (document_id, "empresa-local", "admin-local", "user", f"Sales {ordinal}", str(physical), ".txt", "text/plain", physical.stat().st_size, digest, 1, "ready", 1, "admin-local", "now", "now"))
            db.execute("INSERT INTO document_versions(id,document_id,version,file_hash,stored_path,indexed_at,chunk_count,metadata_json) VALUES(?,?,?,?,?,?,?,?)", (f"legacy-v-{ordinal}", document_id, 1, digest, str(physical), "now", 1, json.dumps({"ordinal": ordinal})))
            db.execute("INSERT INTO document_chunks(id,vector_id,document_id,version,ordinal,text_hash,content,page,sheet,section,row_range,injection_flag,active,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"legacy-c-{ordinal}", vector_id, document_id, 1, 0, digest, f"content {ordinal}", 1, None, None, None, 0, 1, "{}", "now"))
            SQLiteVectorStore(root / "data" / "enterprise" / "vectors.sqlite3").upsert("document", vector_id, [float(ordinal), 1.0], {"company_id": "empresa-local", "user_id": "admin-local", "scope": "user", "document_id": document_id})
        for ordinal in (2, 3):
            physical = root / "workspace" / "Conocimiento" / "empresa-local" / f"legacy-dataset-{ordinal}.csv"; physical.write_bytes(f"metric_{ordinal},label\n{ordinal},X\n".encode())
            digest = hashlib.sha256(physical.read_bytes()).hexdigest()
            db.execute("INSERT INTO datasets(id,company_id,user_id,scope,name,path,file_hash,sheet,columns_json,roles_json,metadata_json,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"legacy-dataset-{ordinal}", "empresa-local", "admin-local", "user", f"Dataset {ordinal}", str(physical), digest, "CSV", json.dumps([f"metric_{ordinal}", "label"]), json.dumps({"sales": f"metric_{ordinal}"}), json.dumps({"provenance": f"fixture-{ordinal}", "permissions": "read"}), 1, "now", "now"))
    if registry:
        config = root / "config"; config.mkdir(parents=True, exist_ok=True)
        (config / "enterprise_sources.json").write_text(json.dumps({"schema_version": "r10.17a", "registry_id": "sources", "sources_version": "fixture", "sources": [{"source_id": "legacy-source", "kind": "sql_server", "status": "ENABLED", "name": "Legacy", "scope": {"company_id": "empresa-local"}, "locator": {"server": "safe-host", "database": "safe-db"}, "credential_ref": "fixture-secret-reference", "access": {"mode": "read_only"}}]}), encoding="utf-8")
        (config / "enterprise_queries.json").write_text(json.dumps({"schema_version": "r10.17e", "registry_id": "queries", "queries_version": "fixture", "queries": [{"query_id": "legacy-query", "source_id": "legacy-source", "status": "ENABLED", "sql": "SELECT id FROM dbo.Table", "row_limit": 10, "timeout_seconds": 30, "approved_by": "admin", "approved_at": "2026-01-01T00:00:00+00:00"}]}), encoding="utf-8")
    return LegacyScopeMigrator(root), reports


def assert_raises(code, fn):
    try:
        fn()
    except LegacyScopeMigrationError as exc:
        assert exc.code == code, exc.code
        return
    raise AssertionError("expected migration failure")


def tree_hashes(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob("*") if path.is_file()}


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        migrator, reports = fixture(root)
        before = tree_hashes(root)
        dry = migrator.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=True)
        after = tree_hashes(root)
        assert dry["status"] == "DRY_RUN" and before == after
        print("PASS dry_run_no_mutation")

        result = migrator.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False)
        assert result["migrated"]["deliverables"] == result["migrated"]["knowledge"] == result["migrated"]["sql_profiles"] == 1
        assert result["migrated"]["documents"] == result["migrated"]["datasets"] == 3
        assert "fixture-secret-reference" not in json.dumps(result) and "fixture-user" not in json.dumps(result)
        evidence = (reports / ".migration_audit" / result["evidence"]).read_text(encoding="utf-8")
        assert "fixture-secret-reference" not in evidence and "fixture-user" not in evidence
        print("PASS sanitized_auditable_evidence")
        target_deliverables = GovernedDeliverableRegistry(reports, tenant_registry=migrator.tenants)
        assert target_deliverables.get(TARGET, "legacy-run")["scope"] == TARGET
        assert GovernedDeliverableRegistry(reports).get(SOURCE, "legacy-run")["scope"] == SOURCE
        print("PASS deliverable_integrity_and_source_preserved")
        target_knowledge = EnterpriseKnowledgeStore(reports / ".knowledge", migrator.tenants)
        assert target_knowledge.get(TARGET, "legacy-note")["scope"] == TARGET
        assert EnterpriseKnowledgeStore(reports / ".knowledge").get(SOURCE, "legacy-note")["scope"] == SOURCE
        print("PASS knowledge_integrity_and_source_preserved")
        target_sql = EnterpriseSqlConnectionStore(reports / ".sql_connections", migrator.tenants)
        assert target_sql.get(TARGET, "legacy-sql")["scope"] == TARGET
        assert EnterpriseSqlConnectionStore(reports / ".sql_connections").get(SOURCE, "legacy-sql")["scope"] == SOURCE
        print("PASS sql_integrity_and_source_preserved")
        db = Database(root / "data" / "enterprise" / "enterprise_ai.sqlite3")
        assert db.one("SELECT company_id,user_id FROM memories WHERE id=?", ("legacy-memory",))["company_id"] == "empresa-local"
        assert db.one("SELECT 1 FROM memories WHERE company_id=?", ("tenant-a",)) is not None
        vector_con = sqlite3.connect(root / "data" / "enterprise" / "vectors.sqlite3")
        try:
            source_vector = vector_con.execute("SELECT company_id,user_id,payload_json FROM vectors WHERE vector_id='legacy-vector'").fetchone()
            vector = vector_con.execute("SELECT company_id,user_id,payload_json FROM vectors WHERE kind='memory' AND vector_id<> 'legacy-vector'").fetchone()
        finally:
            vector_con.close()
        assert source_vector[:2] == ("empresa-local", "admin-local") and vector[:2] == ("tenant-a", "target-admin") and "empresa-local" not in vector[2]
        print("PASS enterprise_ai_scoped_data_isolated")
        target_principal = Principal(company_id="tenant-a", user_id="target-admin", role="user")
        documents = DocumentService(None, db, None, None).list(target_principal)
        datasets = StructuredDataService(db).list(target_principal)
        assert len(documents) == 3 and len(datasets) == 3
        target_document = next(document for document in documents if document["name"] == "Sales")
        assert target_document["stored_path"].replace("\\", "/").find("/Conocimiento/tenant-a/") >= 0
        assert Path(target_document["stored_path"]).read_bytes() == b"sales version two"
        assert db.query("SELECT * FROM document_versions WHERE document_id=?", (target_document["id"],)) and len(db.query("SELECT * FROM document_chunks WHERE document_id=?", (target_document["id"],))) == 2
        target_chunk_vectors = [row["vector_id"] for row in db.query("SELECT vector_id FROM document_chunks WHERE document_id=?", (target_document["id"],))]
        vector_con = sqlite3.connect(root / "data" / "enterprise" / "vectors.sqlite3")
        try:
            assert all(vector_con.execute("SELECT 1 FROM vectors WHERE kind='document' AND vector_id=? AND company_id='tenant-a' AND user_id='target-admin'", (vector_id,)).fetchone() for vector_id in target_chunk_vectors)
            assert vector_con.execute("SELECT COUNT(*) FROM vectors WHERE kind='document' AND company_id='empresa-local' AND user_id='admin-local'").fetchone()[0] == 4
        finally:
            vector_con.close()
        target_dataset = next(dataset for dataset in datasets if dataset["name"] == "Sales dataset")
        assert target_dataset["columns"] == ["amount", "customer"] and target_dataset["roles"] == {"sales": "amount"} and target_dataset["metadata"] == {"provenance": "fixture"}
        assert Path(target_dataset["path"]).read_bytes() == b"amount,customer\n10,A\n"
        assert (root / "workspace" / "Conocimiento" / "empresa-local" / "legacy-document" / "v2_sales.txt").read_bytes() == b"sales version two"
        assert all(Path(document["stored_path"]).is_file() for document in documents) and all(Path(dataset["path"]).is_file() for dataset in datasets)
        print("PASS multi_document_dataset_migration_and_source_preserved")
        qdrant = QdrantVectorStore(root / "data" / "enterprise" / "qdrant")
        try:
            target_q = qdrant.search("document", [0.0, 1.0], target_principal, limit=8)
            source_q = qdrant.search("document", [0.0, 1.0], Principal(company_id="empresa-local", user_id="admin-local", role="user"), limit=8)
            other_q = qdrant.search("document", [0.0, 1.0], Principal(company_id="tenant-b", user_id="other-admin", role="user"), limit=8)
        finally:
            qdrant.close()
        assert len(target_q) == 2 and len(source_q) == 2 and other_q == []
        assert all(item["payload"]["document_id"] == target_document["id"] for item in target_q)
        print("PASS qdrant_persistent_scope_clone")
        assert migrator.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False)["migrated"]["deliverables"] == 0
        print("PASS idempotent_second_run")
        migrator.tenants.create(tenant_id="tenant-b", name="Tenant B")
        EnterpriseIdentityStore(reports / ".identity", migrator.tenants).create_user(user_id="other-admin", username="other-admin", display_name="Other", password="long-password-123", tenant_id="tenant-b", roles=["TENANT_ADMIN"])
        assert GovernedDeliverableRegistry(reports, tenant_registry=migrator.tenants).list({**TARGET, "company_id": "tenant-b", "user_id": "other-admin"}) == []
        assert_raises("MIGRATION_TARGET_IDENTITY_INVALID", lambda: migrator.migrate(source_scope=SOURCE, target_scope={**TARGET, "user_id": "other-admin"}, dry_run=True))
        print("PASS tenant_isolation_and_cross_tenant_target_rejected")

        conflict_root = root / "conflict"; conflict, conflict_reports = fixture(conflict_root)
        EnterpriseKnowledgeStore(conflict_reports / ".knowledge", conflict.tenants).register_knowledge(scope=TARGET, knowledge_id="legacy-note", knowledge_type="governed_note", title="Other", content="Other", source={"source": "fixture"}, provenance={"origin": "fixture"})
        assert_raises("MIGRATION_TARGET_CONFLICT", lambda: conflict.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False))
        assert not (conflict_reports / ".sql_connections" / "tenant-a" / "target-admin" / "_" / "_" / "legacy-sql.json").exists()
        print("PASS conflict_preflight_no_partial_write")

        path_conflict_root = root / "path-conflict"; path_conflict, _ = fixture(path_conflict_root)
        _, internal = path_conflict.plan(source_scope=SOURCE, target_scope=TARGET)
        target_file = Path(internal[2]["path_stores"]["documents"][0]["files"][0]["target"])
        target_file.parent.mkdir(parents=True, exist_ok=True); target_file.write_bytes(b"conflicting bytes")
        path_before = tree_hashes(path_conflict_root)
        assert_raises("MIGRATION_DOCUMENT_PATH_CONFLICT", lambda: path_conflict.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False))
        assert tree_hashes(path_conflict_root) == path_before
        print("PASS path_conflict_preflight_zero_writes")

        corrupt_root = root / "hash-corrupt"; corrupt, _ = fixture(corrupt_root)
        (corrupt_root / "workspace" / "Conocimiento" / "empresa-local" / "legacy-document" / "v1_sales.txt").write_bytes(b"tampered")
        corrupt_before = tree_hashes(corrupt_root)
        assert_raises("MIGRATION_DOCUMENT_HASH_INVALID", lambda: corrupt.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False))
        assert tree_hashes(corrupt_root) == corrupt_before
        print("PASS hash_corruption_preflight_zero_writes")

        for conflict_kind in ("vector", "payload"):
            q_conflict_root = root / f"qdrant-{conflict_kind}-conflict"; q_conflict, _ = fixture(q_conflict_root)
            _, q_internal = q_conflict.plan(source_scope=SOURCE, target_scope=TARGET)
            point = q_internal[3]["qdrant_points"][0]
            qdrant = QdrantVectorStore(q_conflict_root / "data" / "enterprise" / "qdrant")
            try:
                payload = dict(point["payload"])
                vector = list(point["vector"])
                if conflict_kind == "vector": vector[0] += 0.25
                else: payload["document_id"] = "unexpected-document"
                qdrant.client.upsert(point["collection"], points=[qdrant._PointStruct(id=point["target_id"], vector=vector, payload=payload)], wait=True)
            finally:
                qdrant.close()
            conflict_before = tree_hashes(q_conflict_root)
            assert_raises("MIGRATION_QDRANT_CONFLICT", lambda: q_conflict.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False))
            assert tree_hashes(q_conflict_root) == conflict_before
        print("PASS qdrant_conflicts_late_preflight_zero_writes")

        rollback_root = root / "rollback"; rollback, rollback_reports = fixture(rollback_root)
        rollback.fail_after_step = "knowledge"
        assert_raises("MIGRATION_ROLLED_BACK", lambda: rollback.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False))
        assert not (rollback_reports / ".registry" / "tenant-a").exists()
        assert not (rollback_reports / ".knowledge" / "tenant-a").exists()
        assert EnterpriseSqlConnectionStore(rollback_reports / ".sql_connections").get(SOURCE, "legacy-sql")
        print("PASS induced_failure_rollback")

        document_rollback_root = root / "document-rollback"; document_rollback, _ = fixture(document_rollback_root)
        document_before = tree_hashes(document_rollback_root)
        document_rollback.fail_after_step = "documents"
        assert_raises("MIGRATION_ROLLED_BACK", lambda: document_rollback.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False))
        assert tree_hashes(document_rollback_root) == document_before
        print("PASS physical_document_failure_global_rollback")

        audit_rollback_root = root / "audit-rollback"; audit_rollback, _ = fixture(audit_rollback_root)
        audit_before = tree_hashes(audit_rollback_root)
        audit_rollback._write_evidence = lambda _report: (_ for _ in ()).throw(OSError("audit unavailable"))
        assert_raises("MIGRATION_ROLLED_BACK", lambda: audit_rollback.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False))
        assert tree_hashes(audit_rollback_root) == audit_before
        print("PASS audit_failure_global_rollback")

        fresh, _ = fixture(root / "fresh", legacy=False)
        assert fresh.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False)["status"] == "MIGRATED"
        print("PASS fresh_install_noop")
        bad_target = {**TARGET, "user_id": "missing"}
        assert_raises("MIGRATION_TARGET_IDENTITY_INVALID", lambda: migrator.migrate(source_scope=SOURCE, target_scope=bad_target, dry_run=True))
        disabled_root = root / "disabled"; disabled, disabled_reports = fixture(disabled_root)
        disabled.identity.create_user(user_id="disabled-user", username="disabled-user", display_name="Disabled", password="long-password-123", tenant_id="tenant-a", roles=["VIEWER"])
        disabled.identity.set_status("disabled-user", "DISABLED")
        assert_raises("MIGRATION_TARGET_IDENTITY_INVALID", lambda: disabled.migrate(source_scope=SOURCE, target_scope={**TARGET, "user_id": "disabled-user"}, dry_run=True))
        disabled.tenants.set_status("tenant-a", "DISABLED")
        assert_raises("MIGRATION_TARGET_IDENTITY_INVALID", lambda: disabled.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=True))
        print("PASS target_identity_fail_closed")
        registry_root = root / "registry"; registry_migrator, _ = fixture(registry_root, registry=True)
        registry_result = registry_migrator.migrate(source_scope=SOURCE, target_scope=TARGET, dry_run=False, source_registry_source_scope={"company_id": "empresa-local"}, source_registry_target_scope={"company_id": "tenant-a"}, source_id_map={"legacy-source": "tenant-a-source"}, query_id_map={"legacy-query": "tenant-a-query"})
        sources = json.loads((registry_root / "config" / "enterprise_sources.json").read_text(encoding="utf-8"))["sources"]
        queries = json.loads((registry_root / "config" / "enterprise_queries.json").read_text(encoding="utf-8"))["queries"]
        assert len(sources) == 2 and any(x["source_id"] == "legacy-source" for x in sources) and any(x["source_id"] == "tenant-a-source" and x["scope"] == {"company_id": "tenant-a"} for x in sources)
        assert len(queries) == 2 and any(x["query_id"] == "tenant-a-query" and x["source_id"] == "tenant-a-source" for x in queries)
        assert "fixture-secret-reference" not in json.dumps(registry_result)
        print("PASS source_registry_and_query_binding_preserved")


        registry_kwargs = {
            "source_scope": SOURCE,
            "target_scope": TARGET,
            "source_registry_source_scope": {"company_id": "empresa-local"},
            "source_registry_target_scope": {"company_id": "tenant-a"},
            "source_id_map": {"legacy-source": "tenant-a-source"},
            "query_id_map": {"legacy-query": "tenant-a-query"},
        }

        registry_idempotent_root = root / "registry-idempotent"
        registry_idempotent, _ = fixture(
            registry_idempotent_root,
            registry=True,
        )
        registry_idempotent.migrate(
            **registry_kwargs,
            dry_run=False,
        )
        source_registry_path = (
            registry_idempotent_root
            / "config"
            / "enterprise_sources.json"
        )
        query_registry_path = (
            registry_idempotent_root
            / "config"
            / "enterprise_queries.json"
        )
        source_registry_before = source_registry_path.read_bytes()
        query_registry_before = query_registry_path.read_bytes()

        registry_plan, registry_internal = registry_idempotent.plan(
            **registry_kwargs,
        )
        assert registry_plan["status"] == "PLANNED"
        assert registry_internal[4]["sources"] is None
        assert registry_internal[4]["queries"] is None
        assert source_registry_path.read_bytes() == source_registry_before
        assert query_registry_path.read_bytes() == query_registry_before

        registry_second = registry_idempotent.migrate(
            **registry_kwargs,
            dry_run=False,
        )
        assert registry_second["migrated"]["deliverables"] == 0
        assert registry_second["migrated"]["knowledge"] == 0
        assert registry_second["migrated"]["sql_profiles"] == 0
        assert source_registry_path.read_bytes() == source_registry_before
        assert query_registry_path.read_bytes() == query_registry_before

        idempotent_sources = json.loads(
            source_registry_path.read_text(
                encoding="utf-8"
            )
        )["sources"]
        idempotent_queries = json.loads(
            query_registry_path.read_text(
                encoding="utf-8"
            )
        )["queries"]
        assert sum(
            1
            for item in idempotent_sources
            if item.get("source_id") == "tenant-a-source"
        ) == 1
        assert sum(
            1
            for item in idempotent_queries
            if item.get("query_id") == "tenant-a-query"
        ) == 1
        print("PASS source_query_same_mapping_idempotent")

        registry_query_only_root = root / "registry-query-only"
        registry_query_only, _ = fixture(
            registry_query_only_root,
            registry=True,
        )
        registry_query_only.migrate(
            **registry_kwargs,
            dry_run=False,
        )
        query_only_source_path = (
            registry_query_only_root
            / "config"
            / "enterprise_sources.json"
        )
        query_only_query_path = (
            registry_query_only_root
            / "config"
            / "enterprise_queries.json"
        )
        query_only_source_before = (
            query_only_source_path.read_bytes()
        )
        query_only_payload = json.loads(
            query_only_query_path.read_text(
                encoding="utf-8"
            )
        )
        query_only_payload["queries"] = [
            item
            for item in query_only_payload["queries"]
            if item.get("query_id") != "tenant-a-query"
        ]
        query_only_query_path.write_text(
            json.dumps(
                query_only_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )

        query_only_plan, query_only_internal = (
            registry_query_only.plan(
                **registry_kwargs,
            )
        )
        assert query_only_plan["status"] == "PLANNED"
        assert query_only_internal[4]["sources"] is None
        assert query_only_internal[4]["queries"] is not None

        registry_query_only.migrate(
            **registry_kwargs,
            dry_run=False,
        )
        assert (
            query_only_source_path.read_bytes()
            == query_only_source_before
        )
        repaired_queries = json.loads(
            query_only_query_path.read_text(
                encoding="utf-8"
            )
        )["queries"]
        assert sum(
            1
            for item in repaired_queries
            if item.get("query_id") == "tenant-a-query"
        ) == 1
        print("PASS source_equivalent_query_missing_is_repaired")

        source_conflict_root = root / "registry-source-id-conflict"
        source_conflict, _ = fixture(
            source_conflict_root,
            registry=True,
        )
        source_conflict.migrate(
            **registry_kwargs,
            dry_run=False,
        )
        source_conflict_path = (
            source_conflict_root
            / "config"
            / "enterprise_sources.json"
        )
        source_conflict_query_path = (
            source_conflict_root
            / "config"
            / "enterprise_queries.json"
        )
        source_conflict_payload = json.loads(
            source_conflict_path.read_text(
                encoding="utf-8"
            )
        )
        conflicting_source = next(
            item
            for item in source_conflict_payload["sources"]
            if item.get("source_id") == "tenant-a-source"
        )
        conflicting_source["name"] = "Conflicting target source"
        source_conflict_path.write_text(
            json.dumps(
                source_conflict_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        source_conflict_before = tree_hashes(
            source_conflict_root
        )
        assert_raises(
            "MIGRATION_SOURCE_REGISTRY_CONFLICT",
            lambda: source_conflict.plan(
                **registry_kwargs,
            ),
        )
        assert (
            tree_hashes(source_conflict_root)
            == source_conflict_before
        )
        assert source_conflict_query_path.is_file()
        print("PASS source_registry_id_conflict_zero_writes")

        query_conflict_root = root / "registry-query-id-conflict"
        query_conflict, _ = fixture(
            query_conflict_root,
            registry=True,
        )
        query_conflict.migrate(
            **registry_kwargs,
            dry_run=False,
        )
        query_conflict_source_path = (
            query_conflict_root
            / "config"
            / "enterprise_sources.json"
        )
        query_conflict_path = (
            query_conflict_root
            / "config"
            / "enterprise_queries.json"
        )
        query_conflict_payload = json.loads(
            query_conflict_path.read_text(
                encoding="utf-8"
            )
        )
        conflicting_query = next(
            item
            for item in query_conflict_payload["queries"]
            if item.get("query_id") == "tenant-a-query"
        )
        conflicting_query["row_limit"] = 11
        query_conflict_path.write_text(
            json.dumps(
                query_conflict_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        query_conflict_before = tree_hashes(
            query_conflict_root
        )
        assert_raises(
            "MIGRATION_SOURCE_REGISTRY_CONFLICT",
            lambda: query_conflict.plan(
                **registry_kwargs,
            ),
        )
        assert (
            tree_hashes(query_conflict_root)
            == query_conflict_before
        )
        assert query_conflict_source_path.is_file()
        print("PASS query_registry_id_conflict_zero_writes")

        # ------------------------------------------------------------
        # GA.5-B2 final ID-conflict + idempotent reporting regression
        # ------------------------------------------------------------

        assert registry_second["mutated"] is False
        assert registry_second["migrated"]["enterprise_ai_rows"] == 0
        assert registry_second["migrated"]["documents"] == 0
        assert registry_second["migrated"]["datasets"] == 0
        assert registry_second["migrated"]["vector_rows"] == 0
        assert registry_second["migrated"]["qdrant_points"] == 0

        registry_second_evidence = json.loads(
            (
                registry_idempotent_root
                / "workspace"
                / "Reportes"
                / ".migration_audit"
                / registry_second["evidence"]
            ).read_text(encoding="utf-8")
        )
        assert registry_second_evidence["mutated"] is False
        assert registry_second_evidence["migrated"]["enterprise_ai_rows"] == 0
        print("PASS idempotent_reporting_and_audit")

        deliverable_conflict_root = root / "deliverable-id-conflict"
        deliverable_conflict, deliverable_conflict_reports = fixture(
            deliverable_conflict_root
        )
        GovernedDeliverableRegistry(
            deliverable_conflict_reports,
            tenant_registry=deliverable_conflict.tenants,
        ).register(
            scope=TARGET,
            run_id="legacy-run",
            manifest=manifest(),
            outputs={"html": "legacy.html"},
            domain="conflicting-domain",
        )
        deliverable_conflict_before = tree_hashes(
            deliverable_conflict_root
        )
        assert_raises(
            "MIGRATION_TARGET_CONFLICT",
            lambda: deliverable_conflict.plan(
                source_scope=SOURCE,
                target_scope=TARGET,
            ),
        )
        assert (
            tree_hashes(deliverable_conflict_root)
            == deliverable_conflict_before
        )
        print("PASS deliverable_id_conflict_zero_writes")

        sql_conflict_root = root / "sql-profile-id-conflict"
        sql_conflict, sql_conflict_reports = fixture(
            sql_conflict_root
        )
        EnterpriseSqlConnectionStore(
            sql_conflict_reports / ".sql_connections",
            sql_conflict.tenants,
        ).register(
            scope=TARGET,
            connection_id="legacy-sql",
            server="different-server",
            database="safe-db",
            auth_mode="SQL_AUTH",
            credential_ref="fixture-secret-reference",
            secret_reference="fixture-secret-reference",
            username="fixture-user",
            allowed_schemas=["dbo"],
            allowed_tables=["dbo.Table"],
        )
        sql_conflict_before = tree_hashes(
            sql_conflict_root
        )
        assert_raises(
            "MIGRATION_TARGET_CONFLICT",
            lambda: sql_conflict.plan(
                source_scope=SOURCE,
                target_scope=TARGET,
            ),
        )
        assert (
            tree_hashes(sql_conflict_root)
            == sql_conflict_before
        )
        print("PASS sql_profile_id_conflict_zero_writes")

        document_conflict_root = root / "document-id-conflict"
        document_conflict, _ = fixture(
            document_conflict_root
        )
        _, document_internal = document_conflict.plan(
            source_scope=SOURCE,
            target_scope=TARGET,
        )
        document_candidate = dict(
            document_internal[2]["path_stores"]["documents"][0]["target"]
        )
        document_candidate["name"] = "Conflicting document target"

        document_db_path = (
            document_conflict_root
            / "data"
            / "enterprise"
            / "enterprise_ai.sqlite3"
        )
        document_sqlite = __import__("sqlite3").connect(
            document_db_path
        )
        try:
            document_columns = list(document_candidate)
            document_sqlite.execute(
                'INSERT INTO "documents" ('
                + ",".join(
                    '"' + column + '"'
                    for column in document_columns
                )
                + ") VALUES ("
                + ",".join(
                    "?"
                    for _ in document_columns
                )
                + ")",
                tuple(
                    document_candidate[column]
                    for column in document_columns
                ),
            )
            document_sqlite.commit()
        finally:
            document_sqlite.close()

        document_conflict_before = tree_hashes(
            document_conflict_root
        )
        assert_raises(
            "MIGRATION_DOCUMENT_CONFLICT",
            lambda: document_conflict.plan(
                source_scope=SOURCE,
                target_scope=TARGET,
            ),
        )
        assert (
            tree_hashes(document_conflict_root)
            == document_conflict_before
        )
        print("PASS document_id_conflict_zero_writes")

        dataset_conflict_root = root / "dataset-id-conflict"
        dataset_conflict, _ = fixture(
            dataset_conflict_root
        )
        _, dataset_internal = dataset_conflict.plan(
            source_scope=SOURCE,
            target_scope=TARGET,
        )
        dataset_candidate = dict(
            dataset_internal[2]["path_stores"]["datasets"][0]["target"]
        )
        dataset_candidate["name"] = "Conflicting dataset target"

        dataset_db_path = (
            dataset_conflict_root
            / "data"
            / "enterprise"
            / "enterprise_ai.sqlite3"
        )
        dataset_sqlite = __import__("sqlite3").connect(
            dataset_db_path
        )
        try:
            dataset_columns = list(dataset_candidate)
            dataset_sqlite.execute(
                'INSERT INTO "datasets" ('
                + ",".join(
                    '"' + column + '"'
                    for column in dataset_columns
                )
                + ") VALUES ("
                + ",".join(
                    "?"
                    for _ in dataset_columns
                )
                + ")",
                tuple(
                    dataset_candidate[column]
                    for column in dataset_columns
                ),
            )
            dataset_sqlite.commit()
        finally:
            dataset_sqlite.close()

        dataset_conflict_before = tree_hashes(
            dataset_conflict_root
        )
        assert_raises(
            "MIGRATION_DATASET_CONFLICT",
            lambda: dataset_conflict.plan(
                source_scope=SOURCE,
                target_scope=TARGET,
            ),
        )
        assert (
            tree_hashes(dataset_conflict_root)
            == dataset_conflict_before
        )
        print("PASS dataset_id_conflict_zero_writes")

        vector_conflict_root = root / "sqlite-vector-id-conflict"
        vector_conflict, _ = fixture(
            vector_conflict_root
        )
        _, vector_internal = vector_conflict.plan(
            source_scope=SOURCE,
            target_scope=TARGET,
        )
        vector_rows = list(
            vector_internal[3].get("rows") or []
        )
        assert vector_rows

        (
            vector_kind,
            vector_id,
            vector_json,
            vector_payload_json,
            vector_scope,
            vector_create,
        ) = vector_rows[0]

        assert vector_create is True

        vector_payload = json.loads(
            vector_payload_json
        )
        vector_payload["conflict_probe"] = True
        conflicting_vector_payload = json.dumps(
            vector_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        vector_db_path = (
            vector_conflict_root
            / "data"
            / "enterprise"
            / "vectors.sqlite3"
        )
        vector_sqlite = __import__("sqlite3").connect(
            vector_db_path
        )
        try:
            vector_sqlite.execute(
                """
                INSERT INTO vectors(
                    kind,
                    vector_id,
                    company_id,
                    user_id,
                    scope,
                    vector_json,
                    payload_json
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    vector_kind,
                    vector_id,
                    TARGET["company_id"],
                    TARGET["user_id"],
                    vector_scope,
                    vector_json,
                    conflicting_vector_payload,
                ),
            )
            vector_sqlite.commit()
        finally:
            vector_sqlite.close()

        vector_conflict_before = tree_hashes(
            vector_conflict_root
        )
        assert_raises(
            "MIGRATION_VECTOR_CONFLICT",
            lambda: vector_conflict.plan(
                source_scope=SOURCE,
                target_scope=TARGET,
            ),
        )
        assert (
            tree_hashes(vector_conflict_root)
            == vector_conflict_before
        )
        print("PASS sqlite_vector_id_conflict_zero_writes")

        print("PASS id_conflict_matrix_all_nine_stores")


        # ------------------------------------------------------------
        # GA.5-B2 permanent material rollback boundary matrix
        # ------------------------------------------------------------

        def rollback_fixture(name):
            rollback_case_root = root / name
            rollback_case, rollback_reports = fixture(
                rollback_case_root,
                registry=True,
            )

            GovernedDeliverableRegistry(
                rollback_reports,
                tenant_registry=rollback_case.tenants,
            ).register(
                scope=TARGET,
                run_id="preexisting-target-run",
                manifest=manifest(),
                outputs={"html": "legacy.html"},
                domain="preexisting",
            )

            EnterpriseKnowledgeStore(
                rollback_reports / ".knowledge",
                rollback_case.tenants,
            ).register_knowledge(
                scope=TARGET,
                knowledge_id="preexisting-target-note",
                knowledge_type="governed_note",
                title="Preexisting",
                content="Target state must survive rollback",
                source={"source": "rollback-fixture"},
                provenance={"origin": "rollback-fixture"},
            )

            EnterpriseSqlConnectionStore(
                rollback_reports / ".sql_connections",
                rollback_case.tenants,
            ).register(
                scope=TARGET,
                connection_id="preexisting-target-sql",
                server="existing-server",
                database="existing-db",
                auth_mode="SQL_AUTH",
                credential_ref="existing-secret-reference",
                secret_reference="existing-secret-reference",
                username="existing-user",
                allowed_schemas=["dbo"],
                allowed_tables=["dbo.Table"],
            )

            rollback_db = Database(
                rollback_case_root
                / "data"
                / "enterprise"
                / "enterprise_ai.sqlite3"
            )

            rollback_db.execute(
                """
                INSERT INTO memories(
                    id,
                    company_id,
                    user_id,
                    scope,
                    category,
                    content,
                    created_at,
                    updated_at
                )
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    "preexisting-target-memory",
                    "tenant-a",
                    "target-admin",
                    "user",
                    "fact",
                    "preexisting",
                    "now",
                    "now",
                ),
            )

            SQLiteVectorStore(
                rollback_case_root
                / "data"
                / "enterprise"
                / "vectors.sqlite3"
            ).upsert(
                "memory",
                "preexisting-target-vector",
                [0.0, 1.0],
                {
                    "company_id": "tenant-a",
                    "user_id": "target-admin",
                    "scope": "user",
                },
            )

            existing_document_dir = (
                rollback_case_root
                / "workspace"
                / "Conocimiento"
                / "tenant-a"
                / "preexisting-target-document"
            )

            existing_document_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            existing_document_file = (
                existing_document_dir
                / "v1_existing.txt"
            )

            existing_document_file.write_bytes(
                b"preexisting target document"
            )

            existing_document_hash = hashlib.sha256(
                existing_document_file.read_bytes()
            ).hexdigest()

            rollback_db.execute(
                """
                INSERT INTO documents(
                    id,
                    company_id,
                    user_id,
                    scope,
                    name,
                    stored_path,
                    extension,
                    mime_type,
                    size_bytes,
                    current_hash,
                    current_version,
                    status,
                    active,
                    added_by,
                    created_at,
                    updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "preexisting-target-document",
                    "tenant-a",
                    "target-admin",
                    "user",
                    "Preexisting document",
                    str(existing_document_file),
                    ".txt",
                    "text/plain",
                    existing_document_file.stat().st_size,
                    existing_document_hash,
                    1,
                    "ready",
                    1,
                    "target-admin",
                    "now",
                    "now",
                ),
            )

            rollback_db.execute(
                """
                INSERT INTO document_versions(
                    id,
                    document_id,
                    version,
                    file_hash,
                    stored_path,
                    indexed_at,
                    chunk_count,
                    metadata_json
                )
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    "preexisting-target-version",
                    "preexisting-target-document",
                    1,
                    existing_document_hash,
                    str(existing_document_file),
                    "now",
                    0,
                    "{}",
                ),
            )

            existing_dataset_file = (
                rollback_case_root
                / "workspace"
                / "Conocimiento"
                / "tenant-a"
                / "preexisting-target-dataset.csv"
            )

            existing_dataset_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            existing_dataset_file.write_bytes(
                b"value,label\n1,existing\n"
            )

            existing_dataset_hash = hashlib.sha256(
                existing_dataset_file.read_bytes()
            ).hexdigest()

            rollback_db.execute(
                """
                INSERT INTO datasets(
                    id,
                    company_id,
                    user_id,
                    scope,
                    name,
                    path,
                    file_hash,
                    sheet,
                    columns_json,
                    roles_json,
                    metadata_json,
                    active,
                    created_at,
                    updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "preexisting-target-dataset",
                    "tenant-a",
                    "target-admin",
                    "user",
                    "Preexisting dataset",
                    str(existing_dataset_file),
                    existing_dataset_hash,
                    "CSV",
                    json.dumps(["value", "label"]),
                    json.dumps({"sales": "value"}),
                    json.dumps({"origin": "rollback-fixture"}),
                    1,
                    "now",
                    "now",
                ),
            )

            rollback_qdrant = QdrantVectorStore(
                rollback_case_root
                / "data"
                / "enterprise"
                / "qdrant"
            )

            try:
                rollback_qdrant.upsert(
                    "document",
                    "11111111-1111-1111-1111-111111111111",
                    [0.0, 1.0],
                    {
                        "company_id": "tenant-a",
                        "user_id": "target-admin",
                        "scope": "user",
                        "document_id": "preexisting-target-document",
                    },
                )
            finally:
                rollback_qdrant.close()

            rollback_source_path = (
                rollback_case_root
                / "config"
                / "enterprise_sources.json"
            )

            rollback_query_path = (
                rollback_case_root
                / "config"
                / "enterprise_queries.json"
            )

            rollback_sources = json.loads(
                rollback_source_path.read_text(
                    encoding="utf-8"
                )
            )

            rollback_sources["sources"].append(
                {
                    "source_id": "preexisting-target-source",
                    "kind": "sql_server",
                    "status": "ENABLED",
                    "name": "Preexisting Target",
                    "scope": {"company_id": "tenant-a"},
                    "locator": {
                        "server": "existing-host",
                        "database": "existing-db",
                    },
                    "credential_ref": "existing-secret-reference",
                    "access": {"mode": "read_only"},
                }
            )

            rollback_source_path.write_text(
                json.dumps(
                    rollback_sources,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )

            rollback_queries = json.loads(
                rollback_query_path.read_text(
                    encoding="utf-8"
                )
            )

            rollback_queries["queries"].append(
                {
                    "query_id": "preexisting-target-query",
                    "source_id": "preexisting-target-source",
                    "status": "ENABLED",
                    "sql": "SELECT id FROM dbo.Table",
                    "row_limit": 25,
                    "timeout_seconds": 30,
                    "approved_by": "existing-admin",
                    "approved_at": "2026-01-01T00:00:00+00:00",
                }
            )

            rollback_query_path.write_text(
                json.dumps(
                    rollback_queries,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )

            return (
                rollback_case_root,
                rollback_case,
                tree_hashes(rollback_case_root),
            )

        rollback_kwargs = {
            "source_scope": SOURCE,
            "target_scope": TARGET,
            "source_registry_source_scope": {
                "company_id": "empresa-local"
            },
            "source_registry_target_scope": {
                "company_id": "tenant-a"
            },
            "source_id_map": {
                "legacy-source": "tenant-a-source"
            },
            "query_id_map": {
                "legacy-query": "tenant-a-query"
            },
            "dry_run": False,
        }

        for rollback_boundary in (
            "deliverables",
            "knowledge",
            "sql",
            "documents",
            "enterprise_ai",
            "audit",
        ):
            (
                rollback_case_root,
                rollback_case,
                rollback_before,
            ) = rollback_fixture(
                "rollback-matrix-" + rollback_boundary
            )

            rollback_case.fail_after_step = rollback_boundary

            assert_raises(
                "MIGRATION_ROLLED_BACK",
                lambda rollback_case=rollback_case:
                    rollback_case.migrate(
                        **rollback_kwargs
                    ),
            )

            assert (
                tree_hashes(rollback_case_root)
                == rollback_before
            )

            print(
                "PASS rollback_boundary_"
                + rollback_boundary
            )

        (
            vector_rollback_root,
            vector_rollback,
            vector_rollback_before,
        ) = rollback_fixture(
            "rollback-matrix-post-vector"
        )

        original_vector_apply = vector_rollback._vector_apply

        def vector_apply_then_fail(plan, scopes):
            original_vector_apply(plan, scopes)
            raise RuntimeError(
                "induced post-vector failure"
            )

        vector_rollback._vector_apply = vector_apply_then_fail

        assert_raises(
            "MIGRATION_ROLLED_BACK",
            lambda: vector_rollback.migrate(
                **rollback_kwargs
            ),
        )

        assert (
            tree_hashes(vector_rollback_root)
            == vector_rollback_before
        )

        print("PASS rollback_post_vector_qdrant_apply")

        (
            registry_rollback_root,
            registry_rollback,
            registry_rollback_before,
        ) = rollback_fixture(
            "rollback-matrix-partial-registry"
        )

        rollback_migration_module = sys.modules[
            LegacyScopeMigrator.__module__
        ]

        original_query_registry_writer = (
            rollback_migration_module._write_query_registry
        )

        def fail_query_registry_writer(path, payload):
            raise OSError(
                "induced query registry write failure"
            )

        try:
            rollback_migration_module._write_query_registry = (
                fail_query_registry_writer
            )

            assert_raises(
                "MIGRATION_ROLLED_BACK",
                lambda: registry_rollback.migrate(
                    **rollback_kwargs
                ),
            )

        finally:
            rollback_migration_module._write_query_registry = (
                original_query_registry_writer
            )

        assert (
            tree_hashes(registry_rollback_root)
            == registry_rollback_before
        )

        print("PASS rollback_partial_source_query_registry")

        (
            preexisting_rollback_root,
            preexisting_rollback,
            preexisting_rollback_before,
        ) = rollback_fixture(
            "rollback-matrix-preexisting-target"
        )

        required_preexisting_paths = (
            "workspace/Reportes/.registry/"
            "tenant-a/target-admin/_/_/"
            "preexisting-target-run.json",

            "workspace/Reportes/.knowledge/"
            "tenant-a/target-admin/_/_/"
            "preexisting-target-note.json",

            "workspace/Reportes/.sql_connections/"
            "tenant-a/target-admin/_/_/"
            "preexisting-target-sql.json",

            "workspace/Conocimiento/tenant-a/"
            "preexisting-target-document/"
            "v1_existing.txt",

            "workspace/Conocimiento/tenant-a/"
            "preexisting-target-dataset.csv",

            "config/enterprise_sources.json",
            "config/enterprise_queries.json",
        )

        for preexisting_path in required_preexisting_paths:
            assert (
                preexisting_path
                in preexisting_rollback_before
            )

        preexisting_rollback.fail_after_step = "enterprise_ai"

        assert_raises(
            "MIGRATION_ROLLED_BACK",
            lambda: preexisting_rollback.migrate(
                **rollback_kwargs
            ),
        )

        assert (
            tree_hashes(preexisting_rollback_root)
            == preexisting_rollback_before
        )

        print("PASS preexisting_target_rollback_preserved")
        print("PASS byte_exact_rollback_matrix")
        print("PASS rollback_matrix_all_material_boundaries")


        # ------------------------------------------------------------
        # GA.5-B2 permanent cleanup-failure contract
        # ------------------------------------------------------------

        cleanup_migration_module = sys.modules[
            LegacyScopeMigrator.__module__
        ]

        cleanup_kwargs = {
            "source_scope": SOURCE,
            "target_scope": TARGET,
            "source_registry_source_scope": {
                "company_id": "empresa-local"
            },
            "source_registry_target_scope": {
                "company_id": "tenant-a"
            },
            "source_id_map": {
                "legacy-source": "tenant-a-source"
            },
            "query_id_map": {
                "legacy-query": "tenant-a-query"
            },
            "dry_run": False,
        }

        def install_cleanup_failure():
            original_rmtree = (
                cleanup_migration_module.shutil.rmtree
            )

            blocked = []

            def failing_rmtree(path, *args, **kwargs):
                candidate = Path(path)

                if candidate.name.startswith(
                    "ia-legacy-scope-migration-"
                ):
                    blocked.append(candidate)

                    raise OSError(
                        "induced migration snapshot cleanup failure"
                    )

                return original_rmtree(
                    path,
                    *args,
                    **kwargs,
                )

            cleanup_migration_module.shutil.rmtree = (
                failing_rmtree
            )

            return original_rmtree, blocked

        def restore_cleanup_failure(
            original_rmtree,
            blocked,
        ):
            cleanup_migration_module.shutil.rmtree = (
                original_rmtree
            )

            seen = set()

            for snapshot in blocked:
                snapshot_key = str(snapshot)

                if snapshot_key in seen:
                    continue

                seen.add(snapshot_key)

                if snapshot.exists():
                    original_rmtree(snapshot)

        cleanup_success_root = (
            root / "cleanup-failure-success"
        )

        cleanup_success, cleanup_success_reports = fixture(
            cleanup_success_root,
            registry=True,
        )

        cleanup_success_before = tree_hashes(
            cleanup_success_root
        )

        (
            cleanup_success_rmtree,
            cleanup_success_snapshots,
        ) = install_cleanup_failure()

        try:
            assert_raises(
                "MIGRATION_CLEANUP_FAILED",
                lambda: cleanup_success.migrate(
                    **cleanup_kwargs
                ),
            )

        finally:
            restore_cleanup_failure(
                cleanup_success_rmtree,
                cleanup_success_snapshots,
            )

        assert cleanup_success_snapshots

        cleanup_success_after = tree_hashes(
            cleanup_success_root
        )

        assert (
            cleanup_success_after
            != cleanup_success_before
        )

        assert (
            GovernedDeliverableRegistry(
                cleanup_success_reports,
                tenant_registry=cleanup_success.tenants,
            ).get(
                TARGET,
                "legacy-run",
            )["run_id"]
            == "legacy-run"
        )

        assert (
            EnterpriseKnowledgeStore(
                cleanup_success_reports / ".knowledge",
                cleanup_success.tenants,
            ).get(
                TARGET,
                "legacy-note",
            )["knowledge_id"]
            == "legacy-note"
        )

        assert (
            EnterpriseSqlConnectionStore(
                cleanup_success_reports / ".sql_connections",
                cleanup_success.tenants,
            ).get(
                TARGET,
                "legacy-sql",
            )["connection_id"]
            == "legacy-sql"
        )

        cleanup_success_audit = sorted(
            (
                cleanup_success_reports
                / ".migration_audit"
            ).glob(
                "legacy-scope-*.json"
            )
        )

        assert len(cleanup_success_audit) == 1

        cleanup_success_evidence = json.loads(
            cleanup_success_audit[0].read_text(
                encoding="utf-8"
            )
        )

        assert (
            cleanup_success_evidence["mutated"]
            is True
        )

        cleanup_success_retry = cleanup_success.migrate(
            **cleanup_kwargs
        )

        assert (
            cleanup_success_retry["status"]
            == "MIGRATED"
        )

        assert (
            cleanup_success_retry["mutated"]
            is False
        )

        assert all(
            int(value) == 0
            for value
            in cleanup_success_retry["migrated"].values()
        )

        print("PASS success_cleanup_failure_contract")

        cleanup_rollback_root = (
            root / "cleanup-failure-rollback"
        )

        cleanup_rollback, _ = fixture(
            cleanup_rollback_root,
            registry=True,
        )

        cleanup_rollback_before = tree_hashes(
            cleanup_rollback_root
        )

        cleanup_rollback.fail_after_step = (
            "enterprise_ai"
        )

        (
            cleanup_rollback_rmtree,
            cleanup_rollback_snapshots,
        ) = install_cleanup_failure()

        try:
            assert_raises(
                "MIGRATION_CLEANUP_FAILED",
                lambda: cleanup_rollback.migrate(
                    **cleanup_kwargs
                ),
            )

        finally:
            restore_cleanup_failure(
                cleanup_rollback_rmtree,
                cleanup_rollback_snapshots,
            )

        assert cleanup_rollback_snapshots

        assert (
            tree_hashes(cleanup_rollback_root)
            == cleanup_rollback_before
        )

        cleanup_rollback.fail_after_step = None

        cleanup_rollback_retry = (
            cleanup_rollback.migrate(
                **cleanup_kwargs
            )
        )

        assert (
            cleanup_rollback_retry["status"]
            == "MIGRATED"
        )

        assert (
            cleanup_rollback_retry["mutated"]
            is True
        )

        assert (
            cleanup_rollback_retry["migrated"][
                "deliverables"
            ]
            == 1
        )

        assert (
            cleanup_rollback_retry["migrated"][
                "enterprise_ai_rows"
            ]
            == 1
        )

        print("PASS rollback_cleanup_failure_contract")

        assert (
            cleanup_migration_module.shutil.rmtree
            is cleanup_rollback_rmtree
        )

        print("PASS cleanup_failure_contract_permanent")


        # ------------------------------------------------------------
        # GA.5-B2 permanent cross-tenant public API matrix
        # ------------------------------------------------------------

        from enterprise_ai.memory import MemoryManager
        from enterprise_source_registry import (
            load_governed_enterprise_source_registry,
            resolve_governed_enterprise_sources,
        )
        from enterprise_query_registry import (
            load_governed_enterprise_query_registry,
            resolve_governed_enterprise_query,
        )

        def record_ids(records, field):
            return sorted(
                str(item.get(field) or "")
                for item in records
            )

        cross_root = root / "cross-tenant-public-api-matrix"

        cross_migrator, cross_reports = fixture(
            cross_root,
            registry=True,
        )

        cross_result = cross_migrator.migrate(
            source_scope=SOURCE,
            target_scope=TARGET,
            source_registry_source_scope={
                "company_id": "empresa-local"
            },
            source_registry_target_scope={
                "company_id": "tenant-a"
            },
            source_id_map={
                "legacy-source": "tenant-a-source"
            },
            query_id_map={
                "legacy-query": "tenant-a-query"
            },
            dry_run=False,
        )

        assert cross_result["status"] == "MIGRATED"
        assert cross_result["mutated"] is True

        cross_migrator.tenants.create(
            tenant_id="tenant-b",
            name="Tenant B",
        )

        cross_identity = EnterpriseIdentityStore(
            cross_reports / ".identity",
            cross_migrator.tenants,
        )

        cross_identity.create_user(
            user_id="other-admin",
            username="other-admin",
            display_name="Other Tenant",
            password="long-password-123",
            tenant_id="tenant-b",
            roles=["TENANT_ADMIN"],
        )

        cross_identity.create_user(
            user_id="target-other-user",
            username="target-other-user",
            display_name="Other Target User",
            password="long-password-123",
            tenant_id="tenant-a",
            roles=["VIEWER"],
        )

        cross_source_scope = dict(SOURCE)
        cross_target_scope = dict(TARGET)

        cross_foreign_scope = {
            **TARGET,
            "company_id": "tenant-b",
            "user_id": "other-admin",
        }

        cross_same_tenant_other_scope = {
            **TARGET,
            "user_id": "target-other-user",
        }

        cross_source_principal = Principal(
            company_id="empresa-local",
            user_id="admin-local",
            role="user",
        )

        cross_target_principal = Principal(
            company_id="tenant-a",
            user_id="target-admin",
            role="user",
        )

        cross_foreign_principal = Principal(
            company_id="tenant-b",
            user_id="other-admin",
            role="user",
        )

        cross_same_tenant_other_principal = Principal(
            company_id="tenant-a",
            user_id="target-other-user",
            role="user",
        )

        # Deliverables
        cross_deliverables = GovernedDeliverableRegistry(
            cross_reports
        )

        assert record_ids(
            cross_deliverables.list(
                cross_source_scope
            ),
            "run_id",
        ) == ["legacy-run"]

        assert record_ids(
            cross_deliverables.list(
                cross_target_scope
            ),
            "run_id",
        ) == ["legacy-run"]

        assert (
            cross_deliverables.list(
                cross_foreign_scope
            )
            == []
        )

        assert (
            cross_deliverables.list(
                cross_same_tenant_other_scope
            )
            == []
        )

        print("PASS cross_tenant_deliverables")

        # Knowledge
        cross_knowledge = EnterpriseKnowledgeStore(
            cross_reports / ".knowledge"
        )

        assert record_ids(
            cross_knowledge.list(
                cross_source_scope,
                include_inactive=True,
            ),
            "knowledge_id",
        ) == ["legacy-note"]

        assert record_ids(
            cross_knowledge.list(
                cross_target_scope,
                include_inactive=True,
            ),
            "knowledge_id",
        ) == ["legacy-note"]

        assert (
            cross_knowledge.list(
                cross_foreign_scope,
                include_inactive=True,
            )
            == []
        )

        assert (
            cross_knowledge.list(
                cross_same_tenant_other_scope,
                include_inactive=True,
            )
            == []
        )

        print("PASS cross_tenant_knowledge")

        # SQL profiles
        cross_sql = EnterpriseSqlConnectionStore(
            cross_reports / ".sql_connections"
        )

        assert record_ids(
            cross_sql.list(
                cross_source_scope
            ),
            "connection_id",
        ) == ["legacy-sql"]

        assert record_ids(
            cross_sql.list(
                cross_target_scope
            ),
            "connection_id",
        ) == ["legacy-sql"]

        assert (
            cross_sql.list(
                cross_foreign_scope
            )
            == []
        )

        assert (
            cross_sql.list(
                cross_same_tenant_other_scope
            )
            == []
        )

        print("PASS cross_tenant_sql_profiles")

        # Enterprise AI rows through normal product services
        cross_db = Database(
            cross_root
            / "data"
            / "enterprise"
            / "enterprise_ai.sqlite3"
        )

        cross_documents = DocumentService(
            None,
            cross_db,
            None,
            None,
        )

        cross_datasets = StructuredDataService(
            cross_db
        )

        cross_memories = MemoryManager(
            cross_db,
            None,
            None,
        )

        cross_source_documents = cross_documents.list(
            cross_source_principal,
            include_inactive=True,
        )

        cross_target_documents = cross_documents.list(
            cross_target_principal,
            include_inactive=True,
        )

        assert len(cross_source_documents) == 3
        assert len(cross_target_documents) == 3

        assert all(
            item["company_id"] == "empresa-local"
            for item in cross_source_documents
        )

        assert all(
            item["company_id"] == "tenant-a"
            for item in cross_target_documents
        )

        assert (
            cross_documents.list(
                cross_foreign_principal,
                include_inactive=True,
            )
            == []
        )

        assert (
            cross_documents.list(
                cross_same_tenant_other_principal,
                include_inactive=True,
            )
            == []
        )

        cross_source_datasets = cross_datasets.list(
            cross_source_principal
        )

        cross_target_datasets = cross_datasets.list(
            cross_target_principal
        )

        assert len(cross_source_datasets) == 3
        assert len(cross_target_datasets) == 3

        assert all(
            item["company_id"] == "empresa-local"
            for item in cross_source_datasets
        )

        assert all(
            item["company_id"] == "tenant-a"
            for item in cross_target_datasets
        )

        assert (
            cross_datasets.list(
                cross_foreign_principal
            )
            == []
        )

        assert (
            cross_datasets.list(
                cross_same_tenant_other_principal
            )
            == []
        )

        cross_source_memories = cross_memories.list(
            cross_source_principal,
            include_inactive=True,
        )

        cross_target_memories = cross_memories.list(
            cross_target_principal,
            include_inactive=True,
        )

        assert len(cross_source_memories) == 1
        assert len(cross_target_memories) == 1

        assert all(
            item["company_id"] == "empresa-local"
            for item in cross_source_memories
        )

        assert all(
            item["company_id"] == "tenant-a"
            for item in cross_target_memories
        )

        assert (
            cross_memories.list(
                cross_foreign_principal,
                include_inactive=True,
            )
            == []
        )

        assert (
            cross_memories.list(
                cross_same_tenant_other_principal,
                include_inactive=True,
            )
            == []
        )

        print("PASS cross_tenant_enterprise_ai_rows")

        # SQLite vector search API
        cross_sqlite_vectors = SQLiteVectorStore(
            cross_root
            / "data"
            / "enterprise"
            / "vectors.sqlite3"
        )

        cross_source_memory_vectors = (
            cross_sqlite_vectors.search(
                "memory",
                [1.0, 0.0],
                cross_source_principal,
                limit=20,
            )
        )

        cross_target_memory_vectors = (
            cross_sqlite_vectors.search(
                "memory",
                [1.0, 0.0],
                cross_target_principal,
                limit=20,
            )
        )

        assert len(cross_source_memory_vectors) == 1
        assert len(cross_target_memory_vectors) == 1

        assert (
            cross_sqlite_vectors.search(
                "memory",
                [1.0, 0.0],
                cross_foreign_principal,
                limit=20,
            )
            == []
        )

        assert (
            cross_sqlite_vectors.search(
                "memory",
                [1.0, 0.0],
                cross_same_tenant_other_principal,
                limit=20,
            )
            == []
        )

        assert all(
            item["payload"]["company_id"]
            == "empresa-local"
            for item in cross_source_memory_vectors
        )

        assert all(
            item["payload"]["company_id"]
            == "tenant-a"
            for item in cross_target_memory_vectors
        )

        cross_source_document_vectors = (
            cross_sqlite_vectors.search(
                "document",
                [0.0, 1.0],
                cross_source_principal,
                limit=20,
            )
        )

        cross_target_document_vectors = (
            cross_sqlite_vectors.search(
                "document",
                [0.0, 1.0],
                cross_target_principal,
                limit=20,
            )
        )

        assert len(cross_source_document_vectors) == 4
        assert len(cross_target_document_vectors) == 4

        assert (
            cross_sqlite_vectors.search(
                "document",
                [0.0, 1.0],
                cross_foreign_principal,
                limit=20,
            )
            == []
        )

        assert (
            cross_sqlite_vectors.search(
                "document",
                [0.0, 1.0],
                cross_same_tenant_other_principal,
                limit=20,
            )
            == []
        )

        assert all(
            item["payload"]["company_id"]
            == "empresa-local"
            for item in cross_source_document_vectors
        )

        assert all(
            item["payload"]["company_id"]
            == "tenant-a"
            for item in cross_target_document_vectors
        )

        print("PASS cross_tenant_sqlite_vectors")

        # Persistent Qdrant public search API
        cross_qdrant = QdrantVectorStore(
            cross_root
            / "data"
            / "enterprise"
            / "qdrant"
        )

        try:
            cross_source_qdrant = cross_qdrant.search(
                "document",
                [0.0, 1.0],
                cross_source_principal,
                limit=20,
            )

            cross_target_qdrant = cross_qdrant.search(
                "document",
                [0.0, 1.0],
                cross_target_principal,
                limit=20,
            )

            cross_foreign_qdrant = cross_qdrant.search(
                "document",
                [0.0, 1.0],
                cross_foreign_principal,
                limit=20,
            )

            cross_same_user_qdrant = cross_qdrant.search(
                "document",
                [0.0, 1.0],
                cross_same_tenant_other_principal,
                limit=20,
            )

        finally:
            cross_qdrant.close()

        assert len(cross_source_qdrant) == 2
        assert len(cross_target_qdrant) == 2
        assert cross_foreign_qdrant == []
        assert cross_same_user_qdrant == []

        assert all(
            item["payload"]["company_id"]
            == "empresa-local"
            for item in cross_source_qdrant
        )

        assert all(
            item["payload"]["company_id"]
            == "tenant-a"
            for item in cross_target_qdrant
        )

        print("PASS cross_tenant_qdrant")

        # Source Registry: governed context resolution
        cross_source_registry = (
            load_governed_enterprise_source_registry(
                str(
                    cross_root
                    / "config"
                    / "enterprise_sources.json"
                )
            )
        )

        assert (
            cross_source_registry["status"]
            == "LOADED"
        )

        cross_source_resolved = (
            resolve_governed_enterprise_sources(
                registry=cross_source_registry,
                context={
                    "company_id": "empresa-local"
                },
            )
        )

        cross_target_resolved = (
            resolve_governed_enterprise_sources(
                registry=cross_source_registry,
                context={
                    "company_id": "tenant-a"
                },
            )
        )

        cross_foreign_resolved = (
            resolve_governed_enterprise_sources(
                registry=cross_source_registry,
                context={
                    "company_id": "tenant-b"
                },
            )
        )

        cross_source_ids = record_ids(
            cross_source_resolved["sources"],
            "source_id",
        )

        cross_target_ids = record_ids(
            cross_target_resolved["sources"],
            "source_id",
        )

        cross_foreign_ids = record_ids(
            cross_foreign_resolved["sources"],
            "source_id",
        )

        assert cross_source_ids == [
            "legacy-source"
        ]

        assert cross_target_ids == [
            "tenant-a-source"
        ]

        assert cross_foreign_ids == []

        print("PASS cross_tenant_source_registry")

        # Query governance is reachable only through the
        # source IDs exposed by the governed Source resolver.
        cross_query_registry = (
            load_governed_enterprise_query_registry(
                str(
                    cross_root
                    / "config"
                    / "enterprise_queries.json"
                )
            )
        )

        assert (
            cross_query_registry["status"]
            == "LOADED"
        )

        cross_source_query = (
            resolve_governed_enterprise_query(
                registry=cross_query_registry,
                source_id=cross_source_ids[0],
                query_id="legacy-query",
            )
        )

        cross_target_query = (
            resolve_governed_enterprise_query(
                registry=cross_query_registry,
                source_id=cross_target_ids[0],
                query_id="tenant-a-query",
            )
        )

        assert (
            cross_source_query["status"]
            == "APPROVED"
        )

        assert (
            cross_source_query["query"]["source_id"]
            == "legacy-source"
        )

        assert (
            cross_target_query["status"]
            == "APPROVED"
        )

        assert (
            cross_target_query["query"]["source_id"]
            == "tenant-a-source"
        )

        assert cross_foreign_ids == []

        print("PASS cross_tenant_query_registry_chain")

        # A foreign identity cannot be paired with target tenant-a.
        assert_raises(
            "MIGRATION_TARGET_IDENTITY_INVALID",
            lambda: cross_migrator.plan(
                source_scope=SOURCE,
                target_scope={
                    **TARGET,
                    "user_id": "other-admin",
                },
            ),
        )

        print("PASS cross_tenant_target_identity")
        print("PASS cross_tenant_public_api_matrix")

    print("PASS GA5_B2")


if __name__ == "__main__":
    main()
