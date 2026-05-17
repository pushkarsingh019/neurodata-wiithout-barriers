from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from neurodata_web.config import AppConfig


class LocalLLMUnavailable(RuntimeError):
    """Raised when the configured local LLM server cannot answer."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    route: str


class LocalLLMClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def health(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.config.llm_base_url}/models")
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # pragma: no cover - depends on user runtime
            return {
                "status": "unavailable",
                "base_url": self.config.llm_base_url,
                "error": str(exc),
            }
        return {
            "status": "ready",
            "base_url": self.config.llm_base_url,
            "model": self._model_from_models(data),
            "raw": data,
        }

    def complete(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 700,
        temperature: float = 0.2,
    ) -> LLMResult:
        model = self._resolve_model()
        chat_error: Exception | None = None
        try:
            return self._chat_complete(
                model=model,
                system=system,
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            chat_error = exc
        try:
            return self._text_complete(
                model=model,
                prompt=f"{system}\n\nUser request:\n{user}\n\nAnswer:",
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as exc:
            raise LocalLLMUnavailable(f"chat failed: {chat_error}; completions failed: {exc}") from exc

    def _chat_complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=self.config.llm_timeout) as client:
            response = client.post(f"{self.config.llm_base_url}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        text = _clean_model_text(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
        if not text.strip():
            raise LocalLLMUnavailable("chat completion returned no text")
        return LLMResult(text=text.strip(), model=model, route="chat/completions")

    def _text_complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResult:
        payload = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=self.config.llm_timeout) as client:
            response = client.post(f"{self.config.llm_base_url}/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        text = _clean_model_text(data.get("choices", [{}])[0].get("text", ""))
        if not text.strip():
            raise LocalLLMUnavailable("completion returned no text")
        return LLMResult(text=text.strip(), model=model, route="completions")

    def _resolve_model(self) -> str:
        if self.config.llm_model:
            return self.config.llm_model
        try:
            with httpx.Client(timeout=5) as client:
                response = client.get(f"{self.config.llm_base_url}/models")
                response.raise_for_status()
                return self._model_from_models(response.json()) or "local"
        except Exception as exc:
            raise LocalLLMUnavailable(str(exc)) from exc

    def _model_from_models(self, data: dict[str, Any]) -> str | None:
        rows = data.get("data") or data.get("models") or []
        if not rows:
            return None
        first = rows[0]
        if isinstance(first, str):
            return first
        return first.get("id") or first.get("model") or first.get("name")


def _clean_model_text(text: str) -> str:
    stripped = text.strip()
    while "<think>" in stripped and "</think>" in stripped:
        before, rest = stripped.split("<think>", 1)
        _, after = rest.split("</think>", 1)
        stripped = (before + after).strip()
    return stripped
