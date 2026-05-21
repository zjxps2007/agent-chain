"""LLM provider helpers used by built-in agents."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional


DEFAULT_OPENAI_MODEL = "gpt-5.5"


class LLMConfigurationError(RuntimeError):
    """LLM provider configuration is missing or incompatible."""


def load_openai_client(client: Optional[Any] = None) -> Any:
    """Return an OpenAI client instance, loading the optional dependency lazily."""
    if client is not None:
        return client

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConfigurationError(
            "openai 패키지가 설치되어 있지 않습니다. "
            "`pip install 'agent-chain[llm]'` 또는 `pip install openai` 후 다시 실행하세요."
        ) from exc

    loaded = OpenAI()
    if not hasattr(loaded, "responses") or not hasattr(loaded.responses, "create"):
        raise LLMConfigurationError(
            "설치된 openai 클라이언트가 Responses API를 지원하지 않습니다. "
            "openai 패키지를 최신 버전으로 업그레이드하세요."
        )
    return loaded


def extract_response_text(response: Any) -> str:
    """Extract text from an OpenAI Responses API response-like object."""
    output_text = _get_value(response, "output_text")
    if isinstance(output_text, str):
        return output_text.strip()

    chunks: list[str] = []
    output = _get_value(response, "output") or []
    for item in output:
        content = _get_value(item, "content") or []
        for part in content:
            text = _get_value(part, "text")
            if isinstance(text, str):
                chunks.append(text)

    return "\n".join(chunks).strip()


def create_text_response(
    client: Any,
    *,
    model: str,
    instructions: str,
    input_text: str,
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
    text_format: Optional[Dict[str, Any]] = None,
    store: bool = False,
) -> str:
    """Call the OpenAI Responses API and return plain output text."""
    if not hasattr(client, "responses") or not hasattr(client.responses, "create"):
        raise LLMConfigurationError("client.responses.create(...)를 제공하는 OpenAI 호환 클라이언트가 필요합니다.")

    payload: Dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "store": store,
    }

    if temperature is not None:
        payload["temperature"] = temperature
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}

    text_options: Dict[str, Any] = {}
    if verbosity:
        text_options["verbosity"] = verbosity
    if text_format:
        text_options["format"] = text_format
    if text_options:
        payload["text"] = text_options

    response = client.responses.create(**payload)
    text = extract_response_text(response)
    if not text:
        raise LLMConfigurationError("LLM 응답에서 텍스트를 추출하지 못했습니다.")
    return text


def parse_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object from raw or fenced model output."""
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        if start == -1:
            raise
        data, _ = json.JSONDecoder().raw_decode(candidate[start:])

    if not isinstance(data, dict):
        raise ValueError("JSON object가 아닙니다.")
    return data


def _get_value(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)
