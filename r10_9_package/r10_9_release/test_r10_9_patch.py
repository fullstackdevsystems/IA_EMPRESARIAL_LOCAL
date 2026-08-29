from pathlib import Path
import tempfile, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import apply_r10_9 as p
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    f=td/'factory.py'; f.write_text('''from .structured_data import StructuredDataService\nclass Components:\n    def __init__(self, cfg, db, memory, feedback, service):\n        self.memory = memory\n        self.feedback = feedback\ndef build_components():\n    db = Database(cfg.database_path)\n    return Components(cfg, db, memory, feedback, service)\n'''); p.patch_factory(f); s=f.read_text(); assert 'TraceabilityManager' in s and 'traceability' in s; print('PASS factory_patch')
    c=td/'context.py'; c.write_text('''from .structured_data import StructuredDataService\ndef x():\n        chunks=[]; memories=[]; sources=[]; structured=None\n        system_prompt = (\n            "x"\n        )\n'''); p.patch_context(c); assert 'trace_step("retrieval"' in c.read_text(); print('PASS context_patch')
    api=td/'api.py'; api.write_text('''def outer():
    @router.post("/api/enterprise/chat")
    def enterprise_chat(body: ChatRequest, principal: Principal = Depends(principal_dependency)):
        try:
            return components.service.chat(principal, body.message, body.history)
        except Exception as exc:
            pass

    @router.post("/api/enterprise/chat/stream")
    def enterprise_chat_stream(body: ChatRequest, principal: Principal = Depends(principal_dependency)):
        def events():
            try:
                streamed = False
                for event in components.service.stream_general(principal, body.message, body.history):
                    if event.get("type") == "fallback":
                        break
                    streamed = True
                    yield json.dumps(event, ensure_ascii=False) + "\\n"
                if not streamed:
                    yield json.dumps({"type": "status", "phase": "retrieval", "message": "Consultando evidencia empresarial..."}, ensure_ascii=False) + "\\n"
                    result = components.service.chat(principal, body.message, body.history)
                    result = {**result, "type": "done"}
                    yield json.dumps(result, ensure_ascii=False) + "\\n"
            except GeneratorExit:
                raise
            except Exception as exc:
                components.db.audit("chat.stream_error", principal.company_id, principal.user_id, "query", outcome="error", details={"error_type": type(exc).__name__})
                components.logger.exception("chat stream error", extra={"event": "chat.stream_error", "company_id": principal.company_id, "user_id": principal.user_id, "error_type": type(exc).__name__})
                yield json.dumps({"type": "error", "message": "No se pudo completar la respuesta con el servicio local."}, ensure_ascii=False) + "\\n"
        return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.get("/api/enterprise/memories")
    def list_memories(): pass

    @router.get("/api/enterprise/settings")
    def settings(): pass
'''); p.patch_api(api); txt=api.read_text(); assert '/api/enterprise/traces/{trace_id}/explain' in txt and 'trace_type="chat"' in txt and 'trace_type="chat_stream"' in txt; compile(txt,'api.py','exec'); print('PASS api_patch')
print('3/3 PASS R10.9 PATCH')
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    st=td/'structured.py'; st.write_text('''from .security import Principal, scope_clause\ndef q():\n        roles={"date":None,"sales":None,"quantity":None,"cost":None,"freight":None}; group_column=None; dataset={"name":"x"}; sheet="BD"; work=[]; plan={}\n        source = {\n            "type": "dataset",\n            "file": dataset["name"],\n            "sheet": sheet,\n            "rows_used": int(len(work)),\n            "filters": plan.get("filters", []),\n            "year": plan.get("year"),\n            "calculation": "python/pandas",\n        }\n'''); p.patch_structured(st); assert 'trace_step("structured_calculation"' in st.read_text(); print('PASS structured_patch')
    an=td/'analytic.py'; an.write_text('''from .semantic_registry import bridge_roles\ndef e(frame):\n    filtered=frame; mask=None; metrics={}; applied_filters=[]; applied_metrics=[]; errors=[]\n    return {\n        "frame": filtered, "row_mask": mask, "metrics": metrics,\n        "applied_filters": applied_filters, "applied_metrics": applied_metrics, "errors": errors,\n        "rows_input": int(len(frame)), "rows_output": int(len(filtered)),\n    }\n'''); p.patch_analytic(an); assert 'trace_step("analytic_rules"' in an.read_text(); print('PASS analytic_patch')
print('5/5 PASS R10.9 PATCH TOTAL')
