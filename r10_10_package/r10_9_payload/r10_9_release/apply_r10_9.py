from __future__ import annotations
import argparse, re, shutil
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent

def backup(path,root,bdir):
    if path.exists():
        dst=bdir/path.relative_to(root); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dst)

def patch_factory(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from .traceability import TraceabilityManager' not in s:
        anchor='from .structured_data import StructuredDataService\n'
        if anchor not in s: raise RuntimeError('factory import anchor no encontrado')
        s=s.replace(anchor,anchor+'from .traceability import TraceabilityManager\n',1)
    m=re.search(r'class Components:\n    def __init__\(self, ([^\n]+)\):',s)
    if not m: raise RuntimeError('factory Components signature no encontrada')
    args=[x.strip() for x in m.group(1).split(',')]
    if 'traceability' not in args:
        pos=args.index('feedback')+1 if 'feedback' in args else args.index('memory')+1
        args.insert(pos,'traceability')
        s=s[:m.start()]+'class Components:\n    def __init__(self, '+', '.join(args)+'):'+s[m.end():]
    if 'self.traceability = traceability' not in s:
        anchor='        self.feedback = feedback\n' if '        self.feedback = feedback\n' in s else '        self.memory = memory\n'
        s=s.replace(anchor,anchor+'        self.traceability = traceability\n',1)
    if 'traceability = TraceabilityManager(db)' not in s:
        anchor='    db = Database(cfg.database_path)\n'
        if anchor not in s: raise RuntimeError('factory db anchor no encontrado')
        s=s.replace(anchor,anchor+'    traceability = TraceabilityManager(db)\n',1)
    m=re.search(r'    return Components\(([^\n]+)\)',s)
    if not m: raise RuntimeError('factory return Components no encontrado')
    ret=[x.strip() for x in m.group(1).split(',')]
    if 'traceability' not in ret:
        pos=ret.index('feedback')+1 if 'feedback' in ret else ret.index('memory')+1
        ret.insert(pos,'traceability')
        s=s[:m.start()]+'    return Components('+', '.join(ret)+')'+s[m.end():]
    path.write_text(s,encoding='utf-8')

def patch_context(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from .traceability import trace_step' not in s:
        anchor='from .structured_data import StructuredDataService\n'
        if anchor not in s: raise RuntimeError('context import anchor no encontrado')
        s=s.replace(anchor,anchor+'from .traceability import trace_step\n',1)
    if 'trace_step("retrieval"' not in s:
        needle='        system_prompt = (\n'
        if needle not in s: raise RuntimeError('context system_prompt anchor no encontrado')
        block='''        trace_step("retrieval", engine="ContextEngine", details={
            "documents": len(chunks), "memories": len(memories), "rules": len([x for x in sources if x.get("type") == "rule"]),
            "structured_present": bool(structured), "sources_count": len(sources),
        })
'''
        s=s.replace(needle,block+needle,1)
    path.write_text(s,encoding='utf-8')

def patch_structured(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from .traceability import trace_step' not in s:
        anchor='from .security import Principal, scope_clause\n'
        if anchor not in s: raise RuntimeError('structured import anchor no encontrado')
        s=s.replace(anchor,anchor+'from .traceability import trace_step\n',1)
    anchor='''        source = {
            "type": "dataset",
            "file": dataset["name"],
            "sheet": sheet,
            "rows_used": int(len(work)),
            "filters": plan.get("filters", []),
            "year": plan.get("year"),
            "calculation": "python/pandas",
        }
'''
    if 'trace_step("structured_calculation"' not in s:
        if anchor not in s: raise RuntimeError('structured source anchor no encontrado')
        block='''        trace_step("structured_calculation", engine="python/pandas", source_type="dataset", source_ref=dataset.get("id") or dataset.get("dataset_id"), details={
            "file": dataset.get("name"), "sheet": sheet, "rows_used": int(len(work)), "filters": plan.get("filters", []),
            "year": plan.get("year"), "operation": plan.get("operation"), "metric": plan.get("metric"), "group_by": plan.get("group_by"),
            "columns_used": [x for x in [roles.get("date"), roles.get("sales"), roles.get("quantity"), roles.get("cost"), roles.get("freight"), group_column] if x],
            "calculation": "python/pandas",
        })
'''
        s=s.replace(anchor,anchor+block,1)
    path.write_text(s,encoding='utf-8')

def patch_analytic(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from .traceability import trace_step' not in s:
        anchor='from .semantic_registry import bridge_roles\n'
        if anchor not in s: raise RuntimeError('analytic import anchor no encontrado')
        s=s.replace(anchor,anchor+'from .traceability import trace_step\n',1)
    ret='''    return {
        "frame": filtered, "row_mask": mask, "metrics": metrics,
        "applied_filters": applied_filters, "applied_metrics": applied_metrics, "errors": errors,
        "rows_input": int(len(frame)), "rows_output": int(len(filtered)),
    }
'''
    if 'trace_step("analytic_rules"' not in s:
        if ret not in s: raise RuntimeError('analytic return anchor no encontrado')
        block='''    trace_step("analytic_rules", engine="SafeRuleEvaluator", details={
        "filters_count": len(applied_filters), "metrics_count": len(applied_metrics), "errors_count": len(errors),
        "rows_input": int(len(frame)), "rows_output": int(len(filtered)),
        "filters": applied_filters, "metrics": applied_metrics, "errors": errors,
    })
'''
        s=s.replace(ret,block+ret,1)
    path.write_text(s,encoding='utf-8')

def patch_service(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from .traceability import current_trace_id' not in s:
        anchor='from .security import Principal\n'
        if anchor not in s: raise RuntimeError('service import anchor no encontrado')
        s=s.replace(anchor,anchor+'from .traceability import current_trace_id\n',1)
    if 'def _attach_trace(' not in s:
        anchor='\n\nclass EnterpriseAIService:\n'
        if anchor not in s: raise RuntimeError('service class anchor no encontrado')
        helper='''

def _attach_trace(payload: Dict[str, Any]) -> Dict[str, Any]:
    tid = current_trace_id()
    if tid:
        payload["trace_id"] = tid
    return payload
'''
        s=s.replace(anchor,helper+anchor,1)
    s=s.replace('return result\n', 'return _attach_trace(result)\n')
    path.write_text(s,encoding='utf-8')

def patch_api(path: Path):
    s=path.read_text(encoding='utf-8')
    old_chat='    @router.post("/api/enterprise/chat")\n    def enterprise_chat(body: ChatRequest, principal: Principal = Depends(principal_dependency)):\n        try:\n            return components.service.chat(principal, body.message, body.history)\n'
    new_chat='    @router.post("/api/enterprise/chat")\n    def enterprise_chat(body: ChatRequest, principal: Principal = Depends(principal_dependency)):\n        try:\n            with components.traceability.scope(principal, trace_type="chat", prompt=body.message) as trace_id:\n                result = components.service.chat(principal, body.message, body.history)\n                components.traceability.add_step(trace_id, "response_delivery", engine=getattr(components.llm, "name", "local"), details={"sources_count": len(result.get("sources") or [])})\n                result["trace_id"] = trace_id\n                return result\n'
    if 'trace_type="chat"' not in s:
        if old_chat not in s: raise RuntimeError('api chat anchor no encontrado')
        s=s.replace(old_chat,new_chat,1)

    if 'trace_type="chat_stream"' not in s:
        a=s.find('    @router.post("/api/enterprise/chat/stream")\n')
        b=s.find('    @router.get("/api/enterprise/memories")\n',a)
        if a<0 or b<0: raise RuntimeError('api stream boundaries no encontrados')
        new_stream='    @router.post("/api/enterprise/chat/stream")\n    def enterprise_chat_stream(body: ChatRequest, principal: Principal = Depends(principal_dependency)):\n        def events():\n            try:\n                with components.traceability.scope(principal, trace_type="chat_stream", prompt=body.message) as trace_id:\n                    streamed = False\n                    for event in components.service.stream_general(principal, body.message, body.history):\n                        if event.get("type") == "fallback":\n                            break\n                        streamed = True\n                        if event.get("type") == "done":\n                            event = {**event, "trace_id": trace_id}\n                            components.traceability.add_step(trace_id, "response_delivery", engine=getattr(components.llm, "name", "local"), details={"sources_count": len(event.get("sources") or [])})\n                        yield json.dumps(event, ensure_ascii=False) + "\\n"\n                    if not streamed:\n                        yield json.dumps({"type": "status", "phase": "retrieval", "message": "Consultando evidencia empresarial..."}, ensure_ascii=False) + "\\n"\n                        result = components.service.chat(principal, body.message, body.history)\n                        result = {**result, "type": "done", "trace_id": trace_id}\n                        components.traceability.add_step(trace_id, "response_delivery", engine=getattr(components.llm, "name", "local"), details={"sources_count": len(result.get("sources") or [])})\n                        yield json.dumps(result, ensure_ascii=False) + "\\n"\n            except GeneratorExit:\n                raise\n            except Exception as exc:\n                components.db.audit("chat.stream_error", principal.company_id, principal.user_id, "query", outcome="error", details={"error_type": type(exc).__name__})\n                components.logger.exception("chat stream error", extra={"event": "chat.stream_error", "company_id": principal.company_id, "user_id": principal.user_id, "error_type": type(exc).__name__})\n                yield json.dumps({"type": "error", "message": "No se pudo completar la respuesta con el servicio local."}, ensure_ascii=False) + "\\n"\n        return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})\n\n'
        s=s[:a]+new_stream+s[b:]

    if '/api/enterprise/traces/{trace_id}' not in s:
        marker='    @router.get("/api/enterprise/settings")\n'
        if marker not in s: raise RuntimeError('api settings marker no encontrado')
        endpoints='    @router.get("/api/enterprise/traces")\n    def list_traces(limit: int = 100, principal: Principal = Depends(principal_dependency)):\n        return {"traces": components.traceability.list(principal, limit=limit)}\n\n    @router.get("/api/enterprise/traces/{trace_id}")\n    def get_trace(trace_id: str, principal: Principal = Depends(principal_dependency)):\n        try:\n            return components.traceability.get(principal, trace_id)\n        except KeyError as exc:\n            raise HTTPException(status_code=404, detail=str(exc)) from exc\n\n    @router.get("/api/enterprise/traces/{trace_id}/explain")\n    def explain_trace(trace_id: str, principal: Principal = Depends(principal_dependency)):\n        try:\n            return components.traceability.explain(principal, trace_id)\n        except KeyError as exc:\n            raise HTTPException(status_code=404, detail=str(exc)) from exc\n\n'
        s=s.replace(marker,endpoints+marker,1)
    oldjs="if(d.request_id)src+=(src?'<br>':'')+'Solicitud: '+escHtml(d.request_id);return src}"
    if oldjs in s and 'Trazabilidad:' not in s:
        newjs="if(d.request_id)src+=(src?'<br>':'')+'Solicitud: '+escHtml(d.request_id);if(d.trace_id)src+=(src?'<br>':'')+'Trazabilidad: <a href=\"/api/enterprise/traces/'+encodeURIComponent(d.trace_id)+'/explain\" target=\"_blank\">¿Cómo obtuve este resultado?</a>';return src}"
        s=s.replace(oldjs,newjs,1)
    path.write_text(s,encoding='utf-8')

def patch_universal(path: Path):
    s=path.read_text(encoding='utf-8')
    if 'from enterprise_ai.traceability import build_file_trace' not in s:
        insert='''
try:
    from enterprise_ai.traceability import build_file_trace
except Exception:
    build_file_trace = None
'''
        idx=s.find('\n\n')
        if idx<0: raise RuntimeError('universal import insertion no encontrado')
        s=s[:idx]+insert+s[idx:]
    if 'profile["traceability"] = build_file_trace' not in s:
        marker='        result = pd.DataFrame([model["kpis"]])\n'
        if marker in s:
            block='''        if build_file_trace:
            profile["traceability"] = build_file_trace(filename=path.name, sheet=meta.get("hoja_analizada"), rows=len(original), columns=[str(c) for c in original.columns], roles=roles, derived=profile.get("calculos_derivados", {}), notes=notes, outputs=outputs, prompt=prompt)
'''
            s=s.replace(marker,block+marker,1)
    path.write_text(s,encoding='utf-8')

def main(root: Path):
    root=root.resolve(); ent=root/'scripts'/'enterprise_ai'
    if not ent.exists(): raise RuntimeError('No existe scripts/enterprise_ai')
    bdir=root/'updates'/('pre_r10_9_traceability_'+datetime.now().strftime('%Y%m%d_%H%M%S')); bdir.mkdir(parents=True,exist_ok=True)
    targets=[ent/'factory.py',ent/'context_engine.py',ent/'structured_data.py',ent/'service.py',ent/'api.py',ent/'analytic_rules.py',root/'scripts'/'analizador_universal.py',root/'VERSION.txt']
    for p in targets: backup(p,root,bdir)
    shutil.copy2(HERE/'traceability.py',ent/'traceability.py')
    patch_factory(ent/'factory.py'); patch_context(ent/'context_engine.py'); patch_structured(ent/'structured_data.py'); patch_service(ent/'service.py'); patch_api(ent/'api.py')
    if (ent/'analytic_rules.py').exists(): patch_analytic(ent/'analytic_rules.py')
    if (root/'scripts'/'analizador_universal.py').exists(): patch_universal(root/'scripts'/'analizador_universal.py')
    (root/'VERSION.txt').write_text('8.5.5-r10.9-traceability\n',encoding='utf-8')
    print(f'Backup: {bdir}'); print('R10.9 patch OK')

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--root',required=True); a=ap.parse_args(); main(Path(a.root))
