import base64
from io import BytesIO
import mimetypes
from pathlib import Path

from config import N_CTX, N_GPU_LAYERS, VISION_MODEL_PATH, VISION_PROJECTOR_PATH


MAX_VISION_IMAGE_EDGE = 768


class LocalVisionLlamaModel:
    """Qwen2.5-VL GGUF wrapper for local image question answering."""

    def __init__(
        self,
        model_path: str = VISION_MODEL_PATH,
        projector_path: str = VISION_PROJECTOR_PATH,
        n_ctx: int = N_CTX,
        n_gpu_layers: int = N_GPU_LAYERS,
        verbose: bool = False,
        **llama_kwargs,
    ) -> None:
        model_file = Path(model_path)
        projector_file = Path(projector_path)
        if not model_file.exists():
            raise FileNotFoundError(
                "Local vision model file was not found. "
                f"Expected GGUF path: {model_file}"
            )
        if not projector_file.exists():
            raise FileNotFoundError(
                "Local vision projector file was not found. "
                f"Expected GGUF path: {projector_file}"
            )

        try:
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Qwen25VLChatHandler
        except ImportError as exc:
            raise ImportError(
                "Qwen2.5-VL support requires llama-cpp-python with "
                "Qwen25VLChatHandler. Install or upgrade llama-cpp-python."
            ) from exc

        self.model_path = str(model_file)
        self.projector_path = str(projector_file)
        chat_handler = Qwen25VLChatHandler(
            clip_model_path=self.projector_path,
            verbose=verbose,
        )
        self.llm = Llama(
            model_path=self.model_path,
            chat_handler=chat_handler,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=verbose,
            **llama_kwargs,
        )

    def generate_with_images(
        self,
        prompt: str,
        image_paths: str | Path | list[str | Path],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> str:
        paths = [image_paths] if isinstance(image_paths, (str, Path)) else list(image_paths)
        if not paths:
            raise ValueError("At least one image path is required for vision generation.")

        content = [
            {
                "type": "image_url",
                "image_url": {"url": self._image_to_data_url(path)},
            }
            for path in paths
        ]
        content.append({"type": "text", "text": prompt})

        response = self.llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful vision-language assistant. "
                        "Answer naturally and directly."
                    ),
                },
                {"role": "user", "content": content},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
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
    def _image_to_data_url(image_path: str | Path) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file was not found: {path}")
        image_bytes, mime_type = LocalVisionLlamaModel._prepare_image_bytes(path)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _prepare_image_bytes(path: Path) -> tuple[bytes, str]:
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        try:
            from PIL import Image
        except ImportError:
            return path.read_bytes(), mime_type

        try:
            with Image.open(path) as image:
                image.load()
                needs_resize = max(image.size) > MAX_VISION_IMAGE_EDGE
                needs_png = mime_type not in {"image/png", "image/jpeg"}
                if not needs_resize and not needs_png:
                    return path.read_bytes(), mime_type

                if needs_resize:
                    scale = MAX_VISION_IMAGE_EDGE / max(image.size)
                    image = image.resize(
                        (
                            max(1, int(image.size[0] * scale)),
                            max(1, int(image.size[1] * scale)),
                        ),
                        Image.Resampling.LANCZOS,
                    )
                if image.mode not in {"RGB", "L"}:
                    image = image.convert("RGB")

                buffer = BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue(), "image/png"
        except Exception:
            return path.read_bytes(), mime_type
