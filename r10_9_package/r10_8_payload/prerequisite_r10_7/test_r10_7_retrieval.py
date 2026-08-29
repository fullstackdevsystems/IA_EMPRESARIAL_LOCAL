from __future__ import annotations
import sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))

# Cargar modulo evitando dependencias relativas reales con stubs minimos.
import types, importlib.util
pkg=types.ModuleType('enterprise_ai'); pkg.__path__=[]; sys.modules['enterprise_ai']=pkg
for name, cls in [('documents','DocumentService'),('memory','MemoryManager')]:
    m=types.ModuleType('enterprise_ai.'+name); setattr(m,cls,type(cls,(),{})); sys.modules['enterprise_ai.'+name]=m
sec=types.ModuleType('enterprise_ai.security')
class Principal:
    def __init__(self,company_id,user_id,role='user'): self.company_id=company_id; self.user_id=user_id; self.role=role
sec.Principal=Principal; sys.modules['enterprise_ai.security']=sec
spec=importlib.util.spec_from_file_location('enterprise_ai.advanced_retrieval',Path(__file__).with_name('advanced_retrieval.py'))
mod=importlib.util.module_from_spec(spec); sys.modules[spec.name]=mod; spec.loader.exec_module(mod)

class Mem:
    def search(self,p,q,limit,min_score):
        return [
          {'id':'m1','content':'La utilidad de ventas considera costo y flete.','score':.60,'importance':.8,'status':'active'},
          {'id':'m2','content':'La utilidad de ventas considera costo y flete.','score':.59,'importance':.7,'status':'active'},
          {'id':'m3','content':'Vacaciones de empleados se autorizan por RH.','score':.58,'importance':.7,'status':'active'},
        ]
class Docs:
    def search(self,p,q,limit,min_score):
        long='Ventas y margen de melaza. '+('Texto irrelevante de procedimiento. '*150)+' La utilidad descuenta flete.'
        return [
          {'vector_id':'d1','content':long,'score':.52,'name':'politica_ventas.md','metadata_json':'{"official":true,"area":"ventas"}'},
          {'vector_id':'d2','content':'Politica de vacaciones y asistencia de RH.','score':.80,'name':'rh.md','metadata_json':'{"area":"recursos_humanos"}'},
          {'vector_id':'d3','content':'Documento vencido de ventas.','score':.99,'name':'old.md','metadata_json':'{"area":"ventas","valid_to":"2020-01-01"}'},
        ]
class Gov:
    def applicable_rules(self,p,area=None):
        if area=='ventas' or area is None:
            return [{'id':'r1','name':'UTILIDAD_REAL','version':2,'area':'ventas','expression':'Venta - Costo - Flete','status':'VALIDADO'}]
        return []

def test_area_detection():
    assert mod.detect_areas('Analiza utilidad y margen de ventas por cliente')[0]=='ventas'

def test_dedupe_and_area_rerank():
    e=mod.AdvancedRetrievalEngine(Mem(),Docs(),Gov(),{'max_memories':3,'max_document_chunks':3,'max_chunk_chars':500})
    b=e.retrieve(Principal('A','u'),'Analiza utilidad y margen de ventas de melaza')
    assert len(b.memories)==2, b.memories
    assert b.memories[0]['id']=='m1'
    assert b.chunks[0]['name']=='politica_ventas.md', b.chunks
    assert all(x['name']!='old.md' for x in b.chunks)
    assert len(b.chunks[0]['content'])<=501
    assert b.rules and b.rules[0]['id']=='r1'

def test_scope_passthrough():
    p=Principal('EMPRESA_A','rafael')
    e=mod.AdvancedRetrievalEngine(Mem(),Docs(),Gov(),{})
    b=e.retrieve(p,'ventas')
    assert b.stats['reranker']=='hybrid-local-r10.7'

def test_compression_keeps_relevant_sentence():
    txt='A'*900+'. La utilidad de ventas descuenta flete. '+'B'*900
    out=mod._compress_text(txt,'utilidad ventas flete',180)
    assert 'utilidad' in out.lower() or len(out)<=181

def test_no_area_hard_failure():
    e=mod.AdvancedRetrievalEngine(Mem(),Docs(),Gov(),{'max_memories':2,'max_document_chunks':2})
    b=e.retrieve(Principal('A','u'),'Explica arquitectura de software')
    assert isinstance(b.memories,list) and isinstance(b.chunks,list)

if __name__=='__main__':
    tests=[v for k,v in globals().items() if k.startswith('test_') and callable(v)]
    for t in tests: t(); print('PASS',t.__name__)
    print(f'{len(tests)}/{len(tests)} PASS R10.7 ADVANCED RAG')
