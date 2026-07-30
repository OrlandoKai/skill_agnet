import json
import re
import inspect
from pathlib import Path

from config import MODEL_PATH, N_CTX, N_GPU_LAYERS


class LocalLlamaModel:
    """Small wrapper around llama-cpp-python for local GGUF inference."""

    def __init__(
        self,
        model_path: str = MODEL_PATH,
        n_ctx: int = N_CTX,
        n_gpu_layers: int = N_GPU_LAYERS,
        verbose: bool = False,
        **llama_kwargs,
    ) -> None:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                "Local Llama model file was not found. "
                f"Expected GGUF path: {path}"
            )

        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise ImportError(
                "llama-cpp-python is not installed. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from exc

        self.model_path = str(path)
        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=verbose,
            **llama_kwargs,
        )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.0,
        stop: list[str] | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repeat_penalty: float | None = None,
        repeat_last_n: int | None = None,
    ) -> str:
        params = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stop,
        }
        if top_p is not None:
            params["top_p"] = top_p
        if top_k is not None:
            params["top_k"] = top_k
        if repeat_penalty is not None:
            params["repeat_penalty"] = repeat_penalty
        if repeat_last_n is not None:
            params["repeat_last_n"] = repeat_last_n

        response = self.llm(prompt, **self._supported_kwargs(self.llm.__call__, params))
        choices = response.get("choices", [])
        if not choices:
            return ""

        first = choices[0]
        if "text" in first:
            return str(first["text"]).strip()
        if "message" in first and isinstance(first["message"], dict):
            return str(first["message"].get("content", "")).strip()
        return str(first).strip()

    def generate_chat(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.0,
        stop: list[str] | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repeat_penalty: float | None = None,
        repeat_last_n: int | None = None,
    ) -> str:
        params = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stop,
        }
        if top_p is not None:
            params["top_p"] = top_p
        if top_k is not None:
            params["top_k"] = top_k
        if repeat_penalty is not None:
            params["repeat_penalty"] = repeat_penalty
        if repeat_last_n is not None:
            params["repeat_last_n"] = repeat_last_n

        response = self.llm.create_chat_completion(
            **self._supported_kwargs(self.llm.create_chat_completion, params)
        )
        choices = response.get("choices", [])
        if not choices:
            return ""

        first = choices[0]
        message = first.get("message")
        if isinstance(message, dict):
            return str(message.get("content", "")).strip()
        if "text" in first:
            return str(first["text"]).strip()
        return str(first).strip()

    @staticmethod
    def _supported_kwargs(callable_obj, params: dict) -> dict:
        filtered = {key: value for key, value in params.items() if value is not None}
        try:
            supported = set(inspect.signature(callable_obj).parameters)
        except (TypeError, ValueError):
            return filtered
        return {key: value for key, value in filtered.items() if key in supported}

    @staticmethod
    def extract_json_from_text(text: str) -> dict | None:
        if not text or not text.strip():
            return None

        stripped = text.strip()
        parsed = LocalLlamaModel._parse_json_object(stripped)
        if parsed is not None:
            return parsed

        block_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
        for match in block_pattern.finditer(text):
            block = match.group(1).strip()
            parsed = LocalLlamaModel._parse_json_object(block)
            if parsed is not None:
                return parsed

            candidate = LocalLlamaModel._find_first_json_object(block)
            if candidate:
                parsed = LocalLlamaModel._parse_json_object(candidate)
                if parsed is not None:
                    return parsed

        candidate = LocalLlamaModel._find_first_json_object(text)
        if candidate:
            return LocalLlamaModel._parse_json_object(candidate)
        return None

    @staticmethod
    def _parse_json_object(text: str) -> dict | None:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _find_first_json_object(text: str) -> str | None:
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False

        for index in range(start, len(text)):
            char = text[index]

            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]

        return None
