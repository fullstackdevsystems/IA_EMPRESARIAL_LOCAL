from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional, Sequence


class ProviderError(RuntimeError):
    pass


class LLMProvider(ABC):
    name = "abstract"

    @abstractmethod
    def chat(self, messages: Sequence[Dict[str, str]], *, json_mode: bool = False, max_tokens: Optional[int] = None, temperature: Optional[float] = None, num_ctx: Optional[int] = None) -> str:
        raise NotImplementedError

    def stream_chat(self, messages: Sequence[Dict[str, str]], *, max_tokens: Optional[int] = None, temperature: Optional[float] = None, num_ctx: Optional[int] = None) -> Iterator[str]:
        """Streaming opcional. Proveedores sin streaming degradan a una sola pieza."""
        text = self.chat(messages, max_tokens=max_tokens, temperature=temperature, num_ctx=num_ctx)
        if text:
            yield text

    def healthy(self) -> bool:
        return True


class EmbeddingProvider(ABC):
    name = "abstract"
    model = "abstract"

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        raise NotImplementedError


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int = 600, temperature: float = 0.2, max_tokens: int = 0, num_ctx: int = 4096):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        self.last_completion: Dict[str, Any] = {}

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.last_completion = {}
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise ProviderError(f"Ollama no disponible: {exc}") from exc

    def chat(self, messages, *, json_mode=False, max_tokens=None, temperature=None, num_ctx=None) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "stream": False,
            # Qwen3 en Ollama puede entrar en modo de razonamiento largo. Para este
            # asistente empresarial priorizamos respuestas fundamentadas y rápidas.
            "think": False,
            "keep_alive": "30m",
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_ctx": self.num_ctx if num_ctx is None else int(num_ctx),
            },
        }
        effective_max = self.max_tokens if max_tokens is None else int(max_tokens)
        # 0 / negativo = finalización natural. Ollama usa -1 para generar
        # hasta EOS (o hasta el límite técnico del contexto), evitando recortes
        # artificiales por perfiles de 96/160/320 tokens.
        payload["options"]["num_predict"] = -1 if effective_max <= 0 else effective_max
        if json_mode:
            payload["format"] = "json"
        data = self._post("/api/chat", payload)
        self.last_completion = {
            "done_reason": data.get("done_reason"),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
            "total_duration": data.get("total_duration"),
            "num_ctx": payload["options"]["num_ctx"],
        }
        return str((data.get("message") or {}).get("content") or "").strip()

    def stream_chat(self, messages, *, max_tokens=None, temperature=None, num_ctx=None) -> Iterator[str]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "stream": True,
            "think": False,
            "keep_alive": "30m",
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_ctx": self.num_ctx if num_ctx is None else int(num_ctx),
            },
        }
        effective_max = self.max_tokens if max_tokens is None else int(max_tokens)
        # 0 / negativo = finalización natural. Ollama usa -1 para generar
        # hasta EOS (o hasta el límite técnico del contexto), evitando recortes
        # artificiales por perfiles de 96/160/320 tokens.
        payload["options"]["num_predict"] = -1 if effective_max <= 0 else effective_max
        req = urllib.request.Request(
            self.base_url + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw in resp:
                    if not raw.strip():
                        continue
                    data = json.loads(raw.decode("utf-8"))
                    piece = str((data.get("message") or {}).get("content") or "")
                    if piece:
                        yield piece
                    if data.get("done"):
                        self.last_completion = {
                            "done_reason": data.get("done_reason"),
                            "prompt_eval_count": data.get("prompt_eval_count"),
                            "eval_count": data.get("eval_count"),
                            "total_duration": data.get("total_duration"),
                            "num_ctx": payload["options"]["num_ctx"],
                        }
                        break
        except Exception as exc:
            raise ProviderError(f"Ollama no disponible: {exc}") from exc

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/api/tags", timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False


class LMStudioProvider(LLMProvider):
    name = "lmstudio"

    def __init__(self, base_url: str, model: str, timeout: int = 180, temperature: float = 0.2, max_tokens: int = 700):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages, *, json_mode=False, max_tokens=None, temperature=None, num_ctx=None) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature if temperature is None else temperature,
            "stream": False,
        }
        effective_max = self.max_tokens if max_tokens is None else int(max_tokens)
        if effective_max > 0:
            payload["max_tokens"] = effective_max
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return str(data["choices"][0]["message"]["content"]).strip()
        except Exception as exc:
            raise ProviderError(f"LM Studio no disponible: {exc}") from exc

    def stream_chat(self, messages, *, max_tokens=None, temperature=None, num_ctx=None) -> Iterator[str]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature if temperature is None else temperature,
            "stream": True,
        }
        effective_max = self.max_tokens if max_tokens is None else int(max_tokens)
        if effective_max > 0:
            payload["max_tokens"] = effective_max
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                for raw in resp:
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        break
                    data = json.loads(data_text)
                    piece = str((((data.get("choices") or [{}])[0].get("delta") or {}).get("content")) or "")
                    if piece:
                        yield piece
        except Exception as exc:
            raise ProviderError(f"LM Studio no disponible: {exc}") from exc

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/models", timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False


class OllamaEmbeddingProvider(EmbeddingProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        values = [str(x) for x in texts]
        payload = {"model": self.model, "input": values}
        req = urllib.request.Request(
            self.base_url + "/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            embeddings = data.get("embeddings")
            if isinstance(embeddings, list) and len(embeddings) == len(values):
                return [[float(v) for v in emb] for emb in embeddings]
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise ProviderError(f"Embedding Ollama fallo: {exc}") from exc
        except Exception as exc:
            raise ProviderError(f"Embedding Ollama fallo: {exc}") from exc
        out: List[List[float]] = []
        for text in values:
            req = urllib.request.Request(
                self.base_url + "/api/embeddings",
                data=json.dumps({"model": self.model, "prompt": text}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                out.append([float(v) for v in data["embedding"]])
            except Exception as exc:
                raise ProviderError(f"No se pudieron generar embeddings con {self.model}: {exc}") from exc
        return out


class LMStudioEmbeddingProvider(EmbeddingProvider):
    name = "lmstudio"

    def __init__(self, base_url: str, model: str, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        values = [str(x) for x in texts]
        req = urllib.request.Request(
            self.base_url + "/embeddings",
            data=json.dumps({"model": self.model, "input": values}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = sorted(data.get("data", []), key=lambda item: int(item.get("index", 0)))
            if len(items) != len(values):
                raise ProviderError("LM Studio devolvio una cantidad inesperada de embeddings")
            return [[float(v) for v in item["embedding"]] for item in items]
        except Exception as exc:
            if isinstance(exc, ProviderError):
                raise
            raise ProviderError(f"Embedding LM Studio fallo: {exc}") from exc


class HashEmbeddingProvider(EmbeddingProvider):
    """Embedding deterministico solo para pruebas automatizadas sin Ollama."""
    name = "hash-test"
    model = "hash-test-256"

    def __init__(self, dimension: int = 256):
        self.dimension = dimension

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        result = []
        for text in texts:
            vec = [0.0] * self.dimension
            tokens = re.findall(r"[a-záéíóúñ0-9_]+", (text or "").lower())
            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dimension
                vec[idx] += 1.0 if digest[4] % 2 == 0 else -1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            result.append([x / norm for x in vec])
        return result


def build_llm_provider(cfg: Dict[str, Any]) -> LLMProvider:
    name = str(cfg.get("provider", "ollama")).lower()
    if name == "lmstudio":
        return LMStudioProvider(
            cfg.get("lmstudio_url", "http://127.0.0.1:1234/v1"),
            cfg.get("lmstudio_model", "local-model"),
            int(cfg.get("timeout_seconds", 180)),
            float(cfg.get("temperature", 0.2)),
            int(cfg.get("max_tokens", 700)),
        )
    model = cfg.get("ollama_model", "qwen3:4b-instruct")
    timeout = int(cfg.get("timeout_seconds", 600))
    # V8.5.1: 0 significa finalización natural, sin tope artificial de salida.
    # El contexto del modelo y el botón Detener siguen siendo salvaguardas técnicas.
    max_tokens = int(cfg.get("max_tokens", 0) or 0)
    return OllamaProvider(
        cfg.get("ollama_url", "http://127.0.0.1:11434"),
        model,
        timeout,
        float(cfg.get("temperature", 0.2)),
        max_tokens,
        int(cfg.get("num_ctx", 4096)),
    )


def build_embedding_provider(cfg: Dict[str, Any]) -> EmbeddingProvider:
    name = str(cfg.get("provider", "ollama")).lower()
    if name == "lmstudio":
        return LMStudioEmbeddingProvider(
            cfg.get("lmstudio_url", "http://127.0.0.1:1234/v1"),
            cfg.get("lmstudio_model") or cfg.get("model", "text-embedding-model"),
            int(cfg.get("timeout_seconds", 180)),
        )
    return OllamaEmbeddingProvider(
        cfg.get("ollama_url", "http://127.0.0.1:11434"),
        cfg.get("model", "nomic-embed-text"),
        int(cfg.get("timeout_seconds", 180)),
    )
