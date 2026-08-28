from __future__ import annotations

import hashlib
import math
import threading
import time
import uuid
from typing import Any, Dict, Iterator, Optional, Sequence

from .config import EnterpriseConfig
from .context_engine import ContextEngine
from .database import Database, utcnow
from .memory import MemoryManager
from .providers import LLMProvider
from .security import Principal

INTERNAL_TERMS = (
    "venta", "ventas", "compra", "compras", "proveedor", "cliente", "empresa", "inventario",
    "producto", "flete", "margen", "utilidad", "documento", "archivo", "procedimiento", "politica",
    "regla", "factura", "melaza", "reporte",
)

# Señales que indican que el usuario está preguntando por conocimiento propio de la
# empresa y no por conocimiento general del modelo. Se mantienen deliberadamente
# separadas de INTERNAL_TERMS: por ejemplo, "¿Qué es un proveedor?" sí es una
# pregunta general aunque contenga la palabra proveedor.
INTERNAL_OWNERSHIP_CUES = (
    "nuestro ", "nuestra ", "nuestros ", "nuestras ", "mi empresa", "la empresa", "en la empresa",
    "de la empresa", "interno", "interna", "internos", "internas", "segun el documento",
    "según el documento", "segun el archivo", "según el archivo", "este documento", "este archivo",
    "dataset", "base de datos cargada", "datos cargados", "ventas internas", "compras internas",
    "vendimos", "compramos", "pagamos", "facturamos", "tenemos en inventario", "nuestro proveedor",
    "nuestro cliente", "nuestra politica", "nuestra política", "nuestro procedimiento", "nuestra regla",
)

GENERAL_QUESTION_PREFIXES = (
    "que es ", "qué es ", "para que sirve ", "para qué sirve ", "como funciona ", "cómo funciona ",
    "explica ", "explicame ", "explícame ", "diferencia entre ", "que significa ", "qué significa ",
    "como hago ", "cómo hago ", "como puedo ", "cómo puedo ", "como se usa ", "cómo se usa ",
    "que hace ", "qué hace ", "define ", "dame un ejemplo de ",
)

DETAIL_CUES = (
    "detalladamente", "con detalle", "a detalle", "a fondo", "paso a paso", "completo", "completa",
    "profundiza", "profundizar", "explicacion completa", "explicación completa", "tutorial", "extenso", "extensa",
    "todas las caracteristicas", "todas las características", "lista completa",
)

BRIEF_CUES = (
    "breve", "brevemente", "resumen", "resume", "en una oracion", "en una oración", "en una frase",
    "conciso", "concisamente", "solo define", "respuesta corta", "rapido", "rápido",
)

SYSTEM_CAPABILITY_CUES = (
    "de qué eres capaz", "de que eres capaz", "qué puedes hacer", "que puedes hacer",
    "cuáles son tus capacidades", "cuales son tus capacidades", "qué capacidades tienes", "que capacidades tienes",
    "qué funciones tienes", "que funciones tienes", "qué funcionalidades tienes", "que funcionalidades tienes",
    "qué eres", "que eres", "quién eres", "quien eres", "qué modelo usas", "que modelo usas",
    "cómo funciona este asistente", "como funciona este asistente", "cómo funciona tu memoria", "como funciona tu memoria",
    "como asistente empresarial", "asistente empresarial",
)


class EnterpriseAIService:
    def __init__(self, cfg: EnterpriseConfig, db: Database, llm: LLMProvider, memory: MemoryManager, context: ContextEngine):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.memory = memory
        self.context = context
        runtime = cfg.section("runtime")
        self.max_concurrent_generations = max(1, int(runtime.get("max_concurrent_generations", 1)))
        self.queue_timeout_seconds = max(5, int(runtime.get("queue_timeout_seconds", 120)))
        self.max_generation_seconds = max(60, int(runtime.get("max_generation_seconds", 900)))
        self.max_auto_continuations = max(0, int(runtime.get("max_auto_continuations", 2)))
        llm_cfg = cfg.section("llm")
        self.base_num_ctx = max(2048, int(llm_cfg.get("num_ctx", 4096)))
        self.detailed_num_ctx = max(self.base_num_ctx, int(llm_cfg.get("detailed_num_ctx", 16384)))
        self._generation_slots = threading.BoundedSemaphore(self.max_concurrent_generations)

    @staticmethod
    def _looks_internal(question: str) -> bool:
        low = question.lower()
        return any(term in low for term in INTERNAL_TERMS)

    @staticmethod
    def _direct_memory_question(question: str) -> bool:
        low = question.lower()
        cues = ("cómo calculamos", "como calculamos", "cómo se calcula", "como se calcula", "cuál es la regla", "cual es la regla", "qué significa", "que significa", "cómo definimos", "como definimos")
        return any(cue in low for cue in cues)

    @staticmethod
    def _looks_system_capabilities(question: str) -> bool:
        low = " ".join((question or "").strip().lower().split())
        if not low:
            return False
        return any(cue in low for cue in SYSTEM_CAPABILITY_CUES)

    @staticmethod
    def _looks_general_knowledge(question: str) -> bool:
        """Clasificador local, instantáneo y conservador para conocimiento general.

        V8.2 construía siempre el ContextEngine tras fallar el fast-path de memoria.
        Eso arrancaba nomic-embed-text incluso para preguntas como "¿Qué es SQL
        Server?". En una VM CPU-only ese embedding puede sumar decenas de segundos.
        V8.5 conserva el routing de V8.3 y evita embeddings/RAG cuando la consulta es claramente general.
        """
        low = " ".join((question or "").strip().lower().split())
        if not low:
            return False
        if any(cue in low for cue in INTERNAL_OWNERSHIP_CUES):
            return False
        # Preguntas conceptuales explícitas son generales salvo que tengan una señal
        # de pertenencia empresarial. Así "¿Qué es utilidad?" puede usar Qwen,
        # mientras "¿Cuál es nuestra utilidad 2025?" nunca pasa por aquí.
        normalized = low.lstrip("¿¡ ")
        if any(normalized.startswith(prefix) for prefix in GENERAL_QUESTION_PREFIXES):
            return True
        # Si no contiene vocabulario empresarial sensible, también puede resolverse
        # con conocimiento general (programación, tecnología, redacción, etc.).
        return not any(term in low for term in INTERNAL_TERMS)

    def _response_profile(self, question: str, *, general: bool) -> Dict[str, Any]:
        """Selecciona estilo y ventana de contexto, nunca un tope de salida.

        V8.5.5 reserva espacio de contexto para que la RESPUESTA pueda terminar.
        Esto corrige el recorte que ocurría cuando historial + prompt consumían casi
        todo num_ctx=2048/4096. El modelo sigue usando num_predict=-1 (hasta EOS).
        """
        low = " ".join((question or "").strip().lower().split())
        if any(cue in low for cue in DETAIL_CUES):
            return {"name": "detallada", "generation_mode": "natural", "num_ctx": self.detailed_num_ctx, "reserve_output_tokens": max(8192, self.detailed_num_ctx // 2)}
        if any(cue in low for cue in BRIEF_CUES):
            return {"name": "breve", "generation_mode": "natural", "num_ctx": self.base_num_ctx, "reserve_output_tokens": max(1024, self.base_num_ctx // 4)}
        return {"name": "normal", "generation_mode": "natural", "num_ctx": self.base_num_ctx, "reserve_output_tokens": max(1536, self.base_num_ctx // 3)}

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Aproximación conservadora para español/Qwen. Solo se usa para presupuestar
        # el INPUT y dejar espacio libre de contexto; no limita la salida.
        return max(1, int(math.ceil(len(str(text or "")) / 3.5)))

    def _build_general_messages(self, question: str, history: Optional[Sequence[Dict[str, str]]], profile: Dict[str, Any]) -> tuple[list[Dict[str, str]], Dict[str, Any]]:
        system_prompt = self._general_system_prompt(profile)
        num_ctx = int(profile["num_ctx"])
        reserve = int(profile["reserve_output_tokens"])
        fixed_tokens = self._estimate_tokens(system_prompt) + self._estimate_tokens(question) + 48
        history_budget = max(0, num_ctx - reserve - fixed_tokens)
        selected: list[Dict[str, str]] = []
        used = 0
        dropped = 0
        candidates = list(history or [])[-16:]
        for item in reversed(candidates):
            role = str(item.get("role", "user")).lower()
            if role not in {"user", "assistant"}:
                continue
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            cost = self._estimate_tokens(content) + 8
            if used + cost <= history_budget:
                selected.append({"role": role, "content": content})
                used += cost
            else:
                dropped += 1
        selected.reverse()
        messages = [{"role": "system", "content": system_prompt}, *selected, {"role": "user", "content": question}]
        return messages, {
            "num_ctx": num_ctx,
            "reserve_output_tokens": reserve,
            "history_messages_used": len(selected),
            "history_messages_dropped": dropped,
            "estimated_input_tokens": fixed_tokens + used,
        }

    @staticmethod
    def _general_system_prompt(profile: Dict[str, Any]) -> str:
        style = profile.get("name", "normal")
        if style == "breve":
            length_rule = "Para preguntas simples o definiciones, responde en 2 a 4 oraciones. No agregues listas ni secciones salvo que el usuario las pida."
        elif style == "normal":
            length_rule = "Da una respuesta clara de extensión moderada. Usa listas solo si aportan claridad."
        else:
            length_rule = "El usuario pidió detalle; desarrolla la respuesta de forma estructurada sin relleno innecesario."
        return (
            "Eres IA Empresarial Local, ejecutada localmente. El motor LLM actual es Qwen3 4B Instruct mediante Ollama; "
            "no eres un modelo de OpenAI y no debes afirmar pertenecer a OpenAI. La plataforma integra memoria persistente, "
            "RAG documental y datos estructurados, pero en esta ruta de conocimiento general no recibes evidencia interna salvo "
            "que el sistema la recupere por otra ruta. Responde en español usando conocimiento general. No inventes fecha de corte "
            "de entrenamiento, ventas, clientes, proveedores, políticas, cifras ni hechos internos de la empresa. Si la pregunta "
            "requiere información interna, indícalo y pide una fuente empresarial verificable. "
            + length_rule
        )

    def _system_capabilities_answer(self, question: str) -> str:
        """Describe capacidades REALES de esta instalación sin pedir al LLM que se describa a sí mismo.

        Evita afirmaciones inventadas sobre fecha de corte, nube, proveedor, memoria o
        acceso a datos. La respuesta se construye desde la configuración instalada.
        """
        llm_cfg = self.cfg.section("llm")
        emb_cfg = self.cfg.section("embeddings")
        vec_cfg = self.cfg.section("vector")
        sec_cfg = self.cfg.section("security")
        docs_cfg = self.cfg.section("documents")
        detailed = any(cue in " ".join((question or "").lower().split()) for cue in DETAIL_CUES)
        provider = str(llm_cfg.get("provider", "ollama"))
        model = str(llm_cfg.get("ollama_model") if provider == "ollama" else llm_cfg.get("lmstudio_model") or "modelo local")
        embedding = str(emb_cfg.get("model") if emb_cfg.get("provider", "ollama") == "ollama" else emb_cfg.get("lmstudio_model") or "modelo de embeddings local")
        vector_backend = str(vec_cfg.get("backend", "qdrant"))
        database_name = self.cfg.database_path.name
        allowed = ", ".join(str(x).lstrip(".").upper() for x in docs_cfg.get("allowed_extensions", [])) or "PDF, DOCX, XLSX, CSV, TXT y Markdown"
        if not detailed:
            return (
                f"Soy **IA Empresarial Local**, con **{model}** mediante **{provider}**. "
                f"Puedo responder conocimiento general, recuperar reglas desde memoria persistente en **SQLite ({database_name})**, "
                f"consultar documentos con RAG usando **{vector_backend}** y **{embedding}**, y trabajar con datos estructurados mediante el analizador local. "
                "Para cifras empresariales priorizo cálculos determinísticos y evidencia interna; no invento ventas, clientes, proveedores o políticas. "
                "No tengo Internet ni datos en tiempo real por defecto, y la capacidad de redactar código no equivale a ejecutarlo si no existe una herramienta de ejecución conectada."
            )
        bind_local = bool(sec_cfg.get("bind_local_only", True))
        return f"""## Capacidades reales de IA Empresarial Local

### 1. Motor de IA local
- **Proveedor LLM:** {provider}.
- **Modelo configurado:** {model}.
- El modelo se ejecuta localmente; esta instalación no debe presentarse como un modelo de OpenAI.
- Puedo explicar, redactar, resumir, comparar, proponer soluciones y ayudar a desarrollar o revisar código a partir del conocimiento general del modelo.
- **No afirmo una fecha de corte de conocimiento** porque la aplicación no mantiene una fuente verificable para ese dato.

### 2. Memoria permanente
- Existe una memoria empresarial persistente almacenada en **SQLite ({database_name})**.
- La memoria permanente es distinta del historial reciente del chat: una conversación no se convierte automáticamente en una regla permanente.
- Puede guardar reglas, definiciones y conocimiento estable con empresa/usuario, categoría, importancia, estado, fuente y fechas.
- Las consultas directas a reglas conocidas pueden resolverse sin invocar al LLM, por lo que son rápidas y reproducibles.
- La persistencia sobrevive a reinicios mientras el almacenamiento permanezca íntegro; para recuperación ante pérdida de disco se requieren respaldos.

### 3. Documentos y RAG
- Formatos admitidos por configuración: **{allowed}**.
- El backend vectorial solicitado es **{vector_backend}** y el modelo de embeddings es **{embedding}**.
- RAG se activa cuando la pregunta requiere documentos/conocimiento empresarial; las preguntas generales no deben despertar embeddings innecesariamente.
- Los documentos se indexan por fragmentos y versiones, y la respuesta puede incluir referencias al archivo, hoja, página o rango cuando esa metadata está disponible.
- El contenido recuperado se trata como evidencia, no como instrucciones del sistema, para reducir prompt injection.

### 4. Datos estructurados, Excel y CSV
- Para cifras, totales, filtros y métricas empresariales el diseño prioriza **Python/Pandas o consultas estructuradas**, no cálculos inventados por el LLM.
- El analizador local puede procesar Excel/CSV grandes fuera del cargador documental del chat y generar reportes ejecutivos en Excel/PDF.
- El LLM se usa para explicar resultados; la cifra debe provenir del cálculo determinístico o de la base de datos correspondiente.
- Si faltan columnas necesarias —por ejemplo costo para calcular utilidad— debo indicarlo en lugar de estimarlas.

### 5. Programación y automatización
- Puedo explicar y redactar código, SQL, Python, C#, ASP.NET, JavaScript y otros lenguajes que el modelo conozca.
- Puedo revisar lógica y proponer correcciones cuando el código se proporciona como contexto.
- **Esta interfaz no debe afirmar que ejecuta código, modifica servidores o despliega aplicaciones** salvo que exista una herramienta específica conectada para hacerlo.

### 6. Conocimiento general
- Puedo responder conceptos generales de tecnología, administración, finanzas, operaciones, programación y otros dominios cubiertos por el modelo.
- El conocimiento del modelo puede contener errores o estar desactualizado; para hechos empresariales o información que cambia con el tiempo se necesita una fuente verificable.
- No hay acceso web o a información en tiempo real por defecto.

### 7. Seguridad disponible actualmente
- Aislamiento lógico por **empresa y usuario** en memoria/documentos.
- Tokens locales firmados, auditoría de operaciones y logs rotativos.
- Configuración de enlace solo local: **{str(bind_local).lower()}**.
- Los archivos subidos tienen validaciones de extensión/tamaño y rutas saneadas.
- Esta base todavía no sustituye una plataforma completa de identidad corporativa: TLS, Active Directory/SSO, MFA, RBAC avanzado y políticas de red endurecidas forman parte del hardening productivo posterior.

### 8. Limitaciones reales
- Un modelo local de 4B es útil, pero puede equivocarse y no debe ser la fuente de verdad para cifras internas.
- El contexto del modelo es finito aunque no exista un recorte editorial fijo de la respuesta.
- La velocidad depende del hardware; en CPU las respuestas extensas pueden tardar.
- La memoria permanente **no es entrenamiento continuo ni fine-tuning**.
- Los documentos solo pueden responder lo que realmente contienen.
- Sin un dataset, documento, memoria o conexión de datos, no puedo conocer ventas, costos, inventarios o políticas internas.

### 9. Ejemplos prácticos
- **Regla empresarial:** “¿Cómo calculamos la utilidad?” → memoria permanente verificada.
- **Documento:** “¿Qué exige nuestra política de crédito?” → RAG y cita de la fuente.
- **Excel:** “¿Cuánto vendimos por producto y mes?” → cálculo determinístico sobre el archivo.
- **Análisis:** “Explícame por qué cayó este indicador” → el LLM interpreta cifras calculadas.
- **Programación:** “Genera un endpoint FastAPI para consultar clientes” → propuesta de código, sin afirmar que fue desplegado.
- **Conocimiento general:** “¿Qué es SQL Server?” → conocimiento general del modelo, sin consultar documentos internos si no hace falta.

En resumen, soy un **asistente local orquestado**: el LLM aporta lenguaje y conocimiento general, mientras memoria, RAG y herramientas de datos aportan evidencia y persistencia. Esa separación es la que permite evolucionar hacia un entorno empresarial confiable."""

    @staticmethod
    def _memory_answer(memories: Sequence[Dict[str, Any]]) -> str:
        if not memories:
            return ""
        top = memories[0]
        return "Según la memoria empresarial registrada: " + str(top.get("content", "")).strip()

    @staticmethod
    def _is_context_stop(reason: Any) -> bool:
        return str(reason or "").lower() in {"length", "max_tokens", "context_length", "context_window"}

    def _continuation_messages(self, original_messages: Sequence[Dict[str, str]], question: str, answer_so_far: str) -> list[Dict[str, str]]:
        system = next((str(m.get("content", "")) for m in original_messages if m.get("role") == "system"), "")
        # Solo se conserva un fragmento corto del final. Inyectar varios miles de
        # caracteres de la respuesta anterior provocaba que Qwen repitiera secciones.
        tail = answer_so_far[-1800:]
        return [
            {"role": "system", "content": system + "\nMODO CONTINUACIÓN TÉCNICA: responde exclusivamente con contenido NUEVO. No repitas títulos, listas, ejemplos ni frases ya emitidas. Termina los puntos pendientes y concluye."},
            {"role": "user", "content": question},
            {"role": "assistant", "content": tail},
            {"role": "user", "content": "Continúa desde la última idea incompleta. Devuelve solamente la continuación nueva; no vuelvas a empezar la respuesta."},
        ]

    @staticmethod
    def _merge_continuation(existing: str, new_text: str) -> tuple[str, bool]:
        """Elimina solapamiento exacto/por palabras y detecta continuaciones repetitivas."""
        existing = str(existing or "")
        new_text = str(new_text or "").strip()
        if not new_text:
            return "", True
        recent = existing[-12000:].strip()
        if new_text and new_text in recent:
            return "", True
        # Solapamiento por palabras: máximo 120 palabras del final/inicio.
        a = recent.split()[-120:]
        b = new_text.split()
        max_overlap = min(len(a), len(b), 120)
        overlap = 0
        for n in range(max_overlap, 4, -1):
            left = " ".join(a[-n:]).casefold().strip(' .,:;!?\n\t')
            right = " ".join(b[:n]).casefold().strip(' .,:;!?\n\t')
            if left and left == right:
                overlap = n
                break
        if overlap:
            new_text = " ".join(b[overlap:]).strip()
        if not new_text:
            return "", True
        # Guard simple contra bucles: si las primeras 30 palabras de la continuación
        # ya aparecen en el tramo reciente, no se emite otra vuelta repetida.
        lead = " ".join(new_text.split()[:30]).casefold()
        repeated = bool(lead and len(lead) > 80 and lead in recent.casefold())
        return ("" if repeated else new_text), repeated

    def _llm_chat_with_queue(self, messages: Sequence[Dict[str, str]], *, max_tokens: Optional[int] = None, num_ctx: Optional[int] = None) -> tuple[str, float, float]:
        queue_started = time.perf_counter()
        acquired = self._generation_slots.acquire(timeout=self.queue_timeout_seconds)
        queue_ms = (time.perf_counter() - queue_started) * 1000
        if not acquired:
            raise RuntimeError("Tiempo de espera de generación agotado")
        llm_started = time.perf_counter()
        try:
            current = list(messages)
            question = str(next((m.get("content", "") for m in reversed(current) if m.get("role") == "user"), ""))
            parts: list[str] = []
            continuations = 0
            while True:
                text = self.llm.chat(current, max_tokens=max_tokens, num_ctx=num_ctx)
                if text:
                    if continuations == 0:
                        parts.append(text)
                    else:
                        fresh, repeated = self._merge_continuation("\n".join(parts), text)
                        if fresh:
                            parts.append(fresh)
                        if repeated:
                            break
                reason = (getattr(self.llm, "last_completion", {}) or {}).get("done_reason")
                elapsed = time.perf_counter() - llm_started
                if not self._is_context_stop(reason):
                    break
                if elapsed >= self.max_generation_seconds or continuations >= self.max_auto_continuations:
                    break
                continuations += 1
                current = self._continuation_messages(messages, question, "\n".join(parts))
            answer = "\n".join(x.strip() for x in parts if x.strip()).strip()
            return answer, (time.perf_counter() - llm_started) * 1000, queue_ms
        finally:
            self._generation_slots.release()

    def chat(self, principal: Principal, message: str, history: Optional[Sequence[Dict[str, str]]] = None) -> Dict[str, Any]:
        started = time.perf_counter()
        llm_ms = 0.0
        queue_ms = 0.0
        candidate = None
        try:
            # FAST PATH 1: memoria empresarial directa, completamente local y sin
            # embeddings. Debe ejecutarse antes de ContextEngine.
            if self._direct_memory_question(message):
                memory_started = time.perf_counter()
                direct_memories = self.memory.search_lexical(
                    principal, message, limit=min(3, int(self.cfg.section("retrieval").get("max_memories", 6))), min_score=0.18
                )
                memory_ms = (time.perf_counter() - memory_started) * 1000
                if direct_memories:
                    answer = self._memory_answer(direct_memories)
                    sources = [
                        {
                            "type": "memory",
                            "memory_id": m["id"],
                            "category": m["category"],
                            "source_type": m.get("source_type"),
                            "source_ref": m.get("source_ref"),
                            "updated_at": m.get("updated_at"),
                            "score": m.get("score"),
                            "retrieval": "lexical-fast-path",
                        }
                        for m in direct_memories[:1]
                    ]
                    total_ms = (time.perf_counter() - started) * 1000
                    self._metric(principal, message, total_ms, {"memory_ms": memory_ms, "rag_ms": 0.0, "structured_ms": 0.0}, 0.0, len(direct_memories), 0, len(sources), "ok", None)
                    self.db.audit("chat.answer", principal.company_id, principal.user_id, "query", details={"sources": len(sources), "memories": len(direct_memories), "chunks": 0, "fast_path": "memory_lexical"})
                    return {
                        "ok": True,
                        "answer": answer,
                        "sources": sources,
                        "memory_candidate": None,
                        "timings_ms": {"memory_ms": round(memory_ms, 2), "rag_ms": 0.0, "structured_ms": 0.0, "llm_ms": 0.0, "total_ms": round(total_ms, 2)},
                        "retrieval": {"memories": len(direct_memories), "document_chunks": 0, "structured": False, "fast_path": "memory_lexical"},
                    }

            # FAST PATH 2 V8.5.5: preguntas sobre las capacidades de ESTA
            # instalación se responden desde configuración real, no desde la
            # autobiografía del LLM (que puede inventar proveedor, fecha de corte o memoria).
            if self._looks_system_capabilities(message):
                answer = self._system_capabilities_answer(message)
                total_ms = (time.perf_counter() - started) * 1000
                sources = [{"type": "system_capabilities", "version": "8.5.5", "model": getattr(self.llm, "model", None)}]
                self._metric(principal, message, total_ms, {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0}, 0.0, 0, 0, 1, "ok", None, output_chars=len(answer), route="system_capabilities")
                self.db.audit("chat.answer", principal.company_id, principal.user_id, "query", details={"sources": 1, "fast_path": "system_capabilities"})
                return {
                    "ok": True, "answer": answer, "sources": sources, "memory_candidate": None,
                    "timings_ms": {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0, "llm_ms": 0.0, "queue_ms": 0.0, "total_ms": round(total_ms, 2)},
                    "retrieval": {"memories": 0, "document_chunks": 0, "structured": False, "fast_path": "system_capabilities", "response_profile": "detallada" if any(cue in message.lower() for cue in DETAIL_CUES) else "normal", "generation_mode": "deterministic"},
                }

            # FAST PATH 3 V8.5: conocimiento general. No llama MemoryManager.search,
            # DocumentService.search, Qdrant ni al proveedor de embeddings. El modelo
            # local puede usar su conocimiento general, pero tiene prohibido inventar
            # hechos internos de la empresa.
            if self._looks_general_knowledge(message):
                profile = self._response_profile(message, general=True)
                messages, context_plan = self._build_general_messages(message, history, profile)
                answer, llm_ms, queue_ms = self._llm_chat_with_queue(messages, max_tokens=None, num_ctx=profile["num_ctx"])
                total_ms = (time.perf_counter() - started) * 1000
                sources = [{
                    "type": "model_knowledge",
                    "provider": getattr(self.llm, "name", "unknown"),
                    "model": getattr(self.llm, "model", None),
                }]
                self._metric(principal, message, total_ms, {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0}, llm_ms, 0, 0, 1, "ok", None, queue_ms=queue_ms, output_chars=len(answer), route="general_llm")
                self.db.audit("chat.answer", principal.company_id, principal.user_id, "query", details={"sources": 1, "memories": 0, "chunks": 0, "fast_path": "general_llm", "response_profile": profile["name"], "generation_mode": "natural"})
                return {
                    "ok": True,
                    "answer": answer,
                    "sources": sources,
                    "memory_candidate": None,
                    "timings_ms": {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0, "llm_ms": round(llm_ms, 2), "queue_ms": round(queue_ms, 2), "total_ms": round(total_ms, 2)},
                    "retrieval": {"memories": 0, "document_chunks": 0, "structured": False, "fast_path": "general_llm", "response_profile": profile["name"], "generation_mode": "natural", "context_plan": context_plan},
                }

            # Solo las consultas empresariales llegan al recuperador completo. Asimismo,
            # solo aquí evaluamos si el mensaje propone una memoria nueva.
            candidate = self.memory.propose_from_message(principal, message)
            built = self.context.build(principal, message, history)
            structured_ok = bool(built.structured and not built.structured.get("insufficient"))
            has_evidence = bool(built.memories or built.document_chunks or structured_ok)
            if self._looks_internal(message) and not has_evidence:
                answer = "No dispongo de datos internos suficientes para responder con confiabilidad. Agrega o indexa la fuente correspondiente, registra el dataset o guarda la regla empresarial necesaria."
            elif built.structured and built.structured.get("insufficient") and self._looks_internal(message) and not (built.memories or built.document_chunks):
                answer = "No dispongo de datos suficientes para calcularlo de forma confiable. " + str(built.structured.get("reason", ""))
            elif built.memories and not built.document_chunks and not structured_ok and self._direct_memory_question(message):
                # Para preguntas directas sobre una regla/definición ya guardada, la memoria
                # es la fuente de verdad. Responder de forma determinística evita esperar al
                # LLM y elimina el riesgo de que reformule incorrectamente la regla.
                answer = self._memory_answer(built.memories)
            else:
                profile = self._response_profile(message, general=False)
                messages = [{"role": "system", "content": built.system_prompt}]
                if built.evidence_text:
                    messages.append({"role": "system", "content": "CONTEXTO INTERNO RECUPERADO:\n" + built.evidence_text})
                messages.append({"role": "user", "content": message})
                try:
                    answer, llm_ms, queue_ms = self._llm_chat_with_queue(messages, max_tokens=None)
                except Exception:
                    # Degradación segura: si el LLM local tarda/no está disponible pero sí
                    # existe una memoria recuperada, devolvemos únicamente esa evidencia.
                    # Nunca fabricamos datos.
                    if built.memories and not built.document_chunks and not structured_ok:
                        answer = self._memory_answer(built.memories) + "\n\n(Respuesta directa desde memoria; el LLM local no respondió a tiempo.)"
                    else:
                        raise
            total_ms = (time.perf_counter() - started) * 1000
            self._metric(principal, message, total_ms, built.timings, llm_ms, len(built.memories), len(built.document_chunks), len(built.sources), "ok", None, queue_ms=queue_ms, output_chars=len(answer), route="internal_context")
            self.db.audit("chat.answer", principal.company_id, principal.user_id, "query", details={"sources": len(built.sources), "memories": len(built.memories), "chunks": len(built.document_chunks)})
            return {
                "ok": True,
                "answer": answer,
                "sources": built.sources,
                "memory_candidate": candidate,
                "timings_ms": {**{k: round(v, 2) for k, v in built.timings.items()}, "llm_ms": round(llm_ms, 2), "queue_ms": round(queue_ms, 2), "total_ms": round(total_ms, 2)},
                "retrieval": {"memories": len(built.memories), "document_chunks": len(built.document_chunks), "structured": bool(built.structured), **({"response_profile": profile["name"], "generation_mode": "natural"} if "profile" in locals() else {})},
            }
        except Exception as exc:
            total_ms = (time.perf_counter() - started) * 1000
            self._metric(principal, message, total_ms, {}, llm_ms, 0, 0, 0, "error", type(exc).__name__, queue_ms=queue_ms, route="chat")
            self.db.audit("chat.error", principal.company_id, principal.user_id, "query", outcome="error", details={"error_type": type(exc).__name__})
            raise

    def stream_general(self, principal: Principal, message: str, history: Optional[Sequence[Dict[str, str]]] = None) -> Iterator[Dict[str, Any]]:
        """Streaming real para conocimiento general, sin memoria/RAG/embeddings.

        Mantiene un único generador concurrente por defecto en servidores CPU-only,
        reporta espera de cola y tiempo hasta primer token, y permite que el cliente
        corte la conexión para cancelar la lectura de la generación.
        """
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        if self._looks_system_capabilities(message):
            answer = self._system_capabilities_answer(message)
            total_ms = (time.perf_counter() - started) * 1000
            profile_name = "detallada" if any(cue in message.lower() for cue in DETAIL_CUES) else "normal"
            source = {"type": "system_capabilities", "version": "8.5.5", "model": getattr(self.llm, "model", None)}
            self._metric(principal, message, total_ms, {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0}, 0.0, 0, 0, 1, "ok", None, first_token_ms=0.0, queue_ms=0.0, output_chars=len(answer), route="system_capabilities")
            self.db.audit("chat.answer", principal.company_id, principal.user_id, "query", details={"request_id": request_id, "fast_path": "system_capabilities"})
            yield {"type": "start", "request_id": request_id, "route": "system_capabilities", "profile": profile_name, "generation_mode": "deterministic"}
            yield {"type": "first_token", "request_id": request_id, "first_token_ms": 0.0, "queue_ms": 0.0}
            yield {"type": "token", "request_id": request_id, "text": answer}
            yield {"type": "done", "request_id": request_id, "answer": answer, "sources": [source],
                   "timings_ms": {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0, "llm_ms": 0.0, "queue_ms": 0.0, "first_token_ms": 0.0, "total_ms": round(total_ms, 2)},
                   "retrieval": {"memories": 0, "document_chunks": 0, "structured": False, "fast_path": "system_capabilities", "response_profile": profile_name, "generation_mode": "deterministic", "completion_reason": "complete", "continuations": 0},
                   "memory_candidate": None}
            return
        if not self._looks_general_knowledge(message):
            yield {"type": "fallback", "request_id": request_id}
            return

        profile = self._response_profile(message, general=True)
        yield {"type": "start", "request_id": request_id, "route": "general_llm", "profile": profile["name"], "generation_mode": "natural"}
        yield {"type": "status", "request_id": request_id, "phase": "queue", "message": "Esperando turno de generación..."}
        queue_started = time.perf_counter()
        acquired = self._generation_slots.acquire(timeout=self.queue_timeout_seconds)
        queue_ms = (time.perf_counter() - queue_started) * 1000
        if not acquired:
            self.db.audit("chat.queue_timeout", principal.company_id, principal.user_id, "query", outcome="error", details={"request_id": request_id, "queue_ms": round(queue_ms, 2)})
            yield {"type": "error", "request_id": request_id, "message": "El servidor está ocupado. Intenta nuevamente en unos momentos."}
            return

        answer_parts = []
        first_token_ms = None
        llm_started = time.perf_counter()
        try:
            yield {"type": "status", "request_id": request_id, "phase": "generation", "message": "Generando respuesta con el modelo local...", "queue_ms": round(queue_ms, 2)}
            messages, context_plan = self._build_general_messages(message, history, profile)
            current_messages = messages
            continuations = 0
            completion_reason = "natural"
            provider_done_reason = None
            while True:
                continuation_buffer: list[str] = []
                is_continuation = continuations > 0
                for piece in self.llm.stream_chat(current_messages, max_tokens=None, num_ctx=profile["num_ctx"]):
                    if not piece:
                        continue
                    if first_token_ms is None:
                        first_token_ms = (time.perf_counter() - started) * 1000
                        yield {"type": "first_token", "request_id": request_id, "first_token_ms": round(first_token_ms, 2), "queue_ms": round(queue_ms, 2)}
                    if is_continuation:
                        # Una continuación se bufferiza para quitar solapamientos antes
                        # de mostrarla; así no aparecen párrafos/títulos duplicados.
                        continuation_buffer.append(piece)
                    else:
                        answer_parts.append(piece)
                        yield {"type": "token", "request_id": request_id, "text": piece}

                if is_continuation:
                    fresh, repeated = self._merge_continuation("".join(answer_parts), "".join(continuation_buffer))
                    if fresh:
                        sep = "\n" if answer_parts and not "".join(answer_parts).endswith("\n") else ""
                        answer_parts.append(sep + fresh)
                        yield {"type": "token", "request_id": request_id, "text": sep + fresh}
                    if repeated:
                        completion_reason = "repetition_guard_stop"
                        yield {"type": "status", "request_id": request_id, "phase": "safety", "message": "Se detectó repetición en una continuación y se detuvo para no duplicar contenido."}
                        break

                completion = getattr(self.llm, "last_completion", {}) or {}
                provider_done_reason = completion.get("done_reason")
                if not self._is_context_stop(provider_done_reason):
                    completion_reason = "natural" if continuations == 0 else "continued_to_eos"
                    break
                elapsed = time.perf_counter() - llm_started
                if elapsed >= self.max_generation_seconds or continuations >= self.max_auto_continuations:
                    completion_reason = "technical_context_stop" if continuations >= self.max_auto_continuations else "operational_safety_stop"
                    yield {"type": "status", "request_id": request_id, "phase": "safety", "message": "La respuesta alcanzó una salvaguarda técnica. No se realizarán más continuaciones automáticas para evitar bucles."}
                    break
                continuations += 1
                yield {"type": "status", "request_id": request_id, "phase": "continuation", "message": "Continuando el tramo pendiente sin repetir contenido...", "continuation": continuations}
                current_messages = self._continuation_messages(messages, message, "".join(answer_parts))

            answer = "".join(answer_parts).strip()
            llm_ms = (time.perf_counter() - llm_started) * 1000
            total_ms = (time.perf_counter() - started) * 1000
            sources = [{"type": "model_knowledge", "provider": getattr(self.llm, "name", "unknown"), "model": getattr(self.llm, "model", None)}]
            first_token_ms = first_token_ms if first_token_ms is not None else total_ms
            chars = len(answer)
            self._metric(principal, message, total_ms, {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0}, llm_ms, 0, 0, 1, "ok", None, first_token_ms=first_token_ms, queue_ms=queue_ms, output_chars=chars, route="general_llm_stream")
            self.db.audit("chat.answer", principal.company_id, principal.user_id, "query", details={"request_id": request_id, "sources": 1, "fast_path": "general_llm_stream", "response_profile": profile["name"], "generation_mode": "natural", "completion_reason": completion_reason, "provider_done_reason": provider_done_reason, "continuations": continuations, "first_token_ms": round(first_token_ms, 2), "queue_ms": round(queue_ms, 2)})
            yield {
                "type": "done", "request_id": request_id, "answer": answer, "sources": sources,
                "timings_ms": {"memory_ms": 0.0, "rag_ms": 0.0, "structured_ms": 0.0, "llm_ms": round(llm_ms, 2), "queue_ms": round(queue_ms, 2), "first_token_ms": round(first_token_ms, 2), "total_ms": round(total_ms, 2)},
                "retrieval": {"memories": 0, "document_chunks": 0, "structured": False, "fast_path": "general_llm_stream", "response_profile": profile["name"], "generation_mode": "natural", "completion_reason": completion_reason, "provider_done_reason": provider_done_reason, "continuations": continuations, "context_plan": context_plan},
                "memory_candidate": None,
            }
        except GeneratorExit:
            total_ms = (time.perf_counter() - started) * 1000
            self.db.audit("chat.cancelled", principal.company_id, principal.user_id, "query", outcome="cancelled", details={"request_id": request_id, "total_ms": round(total_ms, 2)})
            raise
        except Exception as exc:
            total_ms = (time.perf_counter() - started) * 1000
            self._metric(principal, message, total_ms, {}, 0.0, 0, 0, 0, "error", type(exc).__name__, first_token_ms=first_token_ms, queue_ms=queue_ms, output_chars=sum(len(x) for x in answer_parts), route="general_llm_stream")
            self.db.audit("chat.error", principal.company_id, principal.user_id, "query", outcome="error", details={"request_id": request_id, "error_type": type(exc).__name__})
            yield {"type": "error", "request_id": request_id, "message": "No se pudo completar la respuesta con el modelo local.", "error_type": type(exc).__name__}
        finally:
            self._generation_slots.release()

    def _metric(self, principal: Principal, prompt: str, total_ms: float, timings: Dict[str, float], llm_ms: float, memories_count: int, chunks_count: int, sources_count: int, status: str, error_type: Optional[str], *, first_token_ms: Optional[float] = None, queue_ms: Optional[float] = None, output_chars: Optional[int] = None, route: Optional[str] = None) -> None:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO query_metrics(timestamp,company_id,user_id,prompt_hash,prompt_length,provider,model,total_ms,memory_ms,rag_ms,structured_ms,llm_ms,memories_count,chunks_count,sources_count,status,error_type,first_token_ms,queue_ms,output_chars,route) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                utcnow(), principal.company_id, principal.user_id, prompt_hash, len(prompt),
                getattr(self.llm, "name", "unknown"), getattr(self.llm, "model", None), total_ms,
                timings.get("memory_ms"), timings.get("rag_ms"), timings.get("structured_ms"), llm_ms,
                memories_count, chunks_count, sources_count, status, error_type,
                first_token_ms, queue_ms, output_chars, route,
            ),
        )
