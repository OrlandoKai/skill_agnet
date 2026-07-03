import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import MODEL_PATH
from model.llama_wrapper import LocalLlamaModel


def main() -> None:
    print(f"Loading model: {MODEL_PATH}")
    model = LocalLlamaModel()
    prompt = "[INST] Reply with one short sentence: what is a skill-calling agent? [/INST]"
    output = model.generate(prompt, max_tokens=80, temperature=0.0)
    print("\nModel output:")
    print(output)


if __name__ == "__main__":
    main()
