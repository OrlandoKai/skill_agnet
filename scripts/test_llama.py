import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import MODEL_PATH
from model.llama_wrapper import LocalLlamaModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test a local GGUF model with llama-cpp-python.")
    parser.add_argument(
        "--model_path",
        "--model-path",
        dest="model_path",
        default=MODEL_PATH,
        help="Local GGUF model path. Defaults to config.MODEL_PATH.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"Loading model: {args.model_path}")
    model = LocalLlamaModel(model_path=args.model_path)
    prompt = "[INST] Reply with one short sentence: what is a skill-calling agent? [/INST]"
    output = model.generate(prompt, max_tokens=80, temperature=0.0)
    print("\nModel output:")
    print(output)


if __name__ == "__main__":
    main()
