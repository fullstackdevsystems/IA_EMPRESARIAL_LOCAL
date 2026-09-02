from __future__ import annotations
import hashlib, json, re, unicodedata
from typing import Any, Dict, Iterable, List, Optional
from enterprise_knowledge_registry import retrieve_governed_enterprise_knowledge

KNOWLEDGE_RETRIEVAL_VERSION = "r10.16b"
_STOPWORDS={"a","al","algo","como","con","de","del","el","en","es","esta","este","la","las","lo","los","me","mi","para","por","que","quiero","se","sin","sobre","su","sus","un","una","y","the","of","to","and","for","in","on","with","from"}

def _norm(value: Any)->str:
    text=str(value or "").strip().lower()
    text="".join(c for c in unicodedata.normalize("NFD",text) if unicodedata.category(c)!="Mn")
    text=re.sub(r"[^a-z0-9_]+"," ",text)
    return re.sub(r"\s+"," ",text).strip()

def _tokens(value: Any)->List[str]:
    return [t for t in _norm(value).split() if len(t)>=3 and t not in _STOPWORDS]

def _entry_text(entry: Dict[str,Any])->str:
    pieces=[entry.get("title"),entry.get("content"),entry.get("keywords"),entry.get("tags")]
    out=[]
    for item in pieces:
        if item in (None,""): continue
        if isinstance(item,(dict,list)):
            out.append(json.dumps(item,ensure_ascii=False,sort_keys=True))
        else:
            out.append(str(item))
    return " ".join(out)

def _score_entry(prompt_tokens: Iterable[str], entry: Dict[str,Any])->Dict[str,Any]:
    p=set(prompt_tokens); tt=set(_tokens(entry.get("title"))); bt=set(_tokens(_entry_text(entry)))
    th=sorted(p & tt); bh=sorted(p & bt)
    return {"score":len(th)*3+len(bh),"title_hits":th,"body_hits":bh}

def retrieve_contextual_enterprise_knowledge(*,prompt:str,registry:Dict[str,Any],context:Optional[Dict[str,Any]]=None,as_of:Optional[str]=None,knowledge_types:Optional[List[str]]=None,max_results:int=8)->Dict[str,Any]:
    qtokens=_tokens(prompt); qhash=hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest()
    governed=retrieve_governed_enterprise_knowledge(registry=registry,context=context,as_of=as_of,knowledge_types=knowledge_types)
    governance={"approved_only":True,"scope_guard":True,"effective_date_guard":True,"deterministic_relevance_only":True,"llm_relevance_inference":False,"source_data_precedence":True,"knowledge_cannot_create_metrics":True}
    if governed.get("status")=="BLOCKED":
        return {"schema_version":KNOWLEDGE_RETRIEVAL_VERSION,"status":"BLOCKED","query_hash_sha256":qhash,"query_token_count":len(qtokens),"candidate_count":0,"matched_entry_count":0,"matches":[],"reason":governed.get("reason"),"governance":governance}
    candidates=list(governed.get("entries") or []); ranked=[]
    for entry in candidates:
        scored=_score_entry(qtokens,entry)
        if scored["score"]<=0: continue
        ranked.append({"entry_id":entry.get("entry_id"),"type":entry.get("type"),"title":entry.get("title"),"content":entry.get("content"),"scope":dict(entry.get("scope") or {}),"effective_from":entry.get("effective_from"),"effective_to":entry.get("effective_to"),"provenance":dict(entry.get("provenance") or {}),"relevance":scored})
    ranked.sort(key=lambda x:(-int((x.get("relevance") or {}).get("score") or 0),str(x.get("entry_id") or "")))
    try: limit=int(max_results)
    except Exception: limit=8
    limit=min(max(limit,1),50); ranked=ranked[:limit]
    return {"schema_version":KNOWLEDGE_RETRIEVAL_VERSION,"status":"RETRIEVED" if ranked else "EMPTY","query_hash_sha256":qhash,"query_token_count":len(qtokens),"candidate_count":len(candidates),"matched_entry_count":len(ranked),"matches":ranked,"reason":None,"governance":governance}

def public_knowledge_context(retrieval: Dict[str,Any])->Dict[str,Any]:
    matches=[]
    for m in list(retrieval.get("matches") or []):
        matches.append({"entry_id":m.get("entry_id"),"type":m.get("type"),"title":m.get("title"),"scope":dict(m.get("scope") or {}),"effective_from":m.get("effective_from"),"effective_to":m.get("effective_to"),"provenance":dict(m.get("provenance") or {}),"relevance":dict(m.get("relevance") or {})})
    return {"schema_version":retrieval.get("schema_version"),"status":retrieval.get("status"),"query_hash_sha256":retrieval.get("query_hash_sha256"),"query_token_count":retrieval.get("query_token_count"),"candidate_count":retrieval.get("candidate_count"),"matched_entry_count":retrieval.get("matched_entry_count"),"matches":matches,"reason":retrieval.get("reason"),"governance":dict(retrieval.get("governance") or {})}
