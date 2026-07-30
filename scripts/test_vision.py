import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import VISION_MODEL_PATH, VISION_PROJECTOR_PATH
from model.vision_wrapper import LocalVisionLlamaModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test local Qwen2.5-VL GGUF image QA.")
    parser.add_argument("--image", required=True, help="Path to a local image file.")
    parser.add_argument(
        "--prompt",
        default="Describe this image briefly.",
        help="Question to ask about the image.",
    )
    parser.add_argument(
        "--model_path",
        "--model-path",
        dest="model_path",
        default=VISION_MODEL_PATH,
        help="Local Qwen2.5-VL GGUF model path.",
    )
    parser.add_argument(
        "--projector_path",
        "--projector-path",
        dest="projector_path",
        default=VISION_PROJECTOR_PATH,
        help="Local Qwen2.5-VL vision projector GGUF path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_path = Path(args.image)
    if not image_path.exists():
        raise FileNotFoundError(f"Image file was not found: {image_path}")

    print(f"Loading vision model: {args.model_path}")
    print(f"Loading vision projector: {args.projector_path}")
    model = LocalVisionLlamaModel(
        model_path=args.model_path,
        projector_path=args.projector_path,
    )
    output = model.generate_with_images(
        prompt=args.prompt,
        image_paths=[image_path],
        max_tokens=256,
        temperature=0.0,
    )
    print("\nVision model output:")
    print(output)


if __name__ == "__main__":
    main()
