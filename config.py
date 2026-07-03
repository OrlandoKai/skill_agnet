from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = r"D:\llm\models\llama2-7b-chat-q4_k_m-self.gguf"
N_CTX = 4096
N_GPU_LAYERS = -1
DEFAULT_TOP_K = 3
DEFAULT_MAX_STEPS = 3

SKILL_LIBRARY_PATH = BASE_DIR / "data" / "skill_library.json"
RESULTS_DIR = BASE_DIR / "results"
