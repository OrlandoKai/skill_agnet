import json
import re
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
    ) -> str:
        response = self.llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choices = response.get("choices", [])
        if not choices:
            return ""

        first = choices[0]
        if "text" in first:
            return str(first["text"]).strip()
        if "message" in first and isinstance(first["message"], dict):
            return str(first["message"].get("content", "")).strip()
        return str(first).strip()

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
