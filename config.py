from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = r"D:\llm\models\llama2-7b-chat-q4_k_m-self.gguf"
MODEL_DIR = r"D:\llm\models"
VISION_MODEL_PATH = r"D:\llm\models\qwen2.5-vl-7b\Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf"
VISION_PROJECTOR_PATH = r"D:\llm\models\qwen2.5-vl-7b\Qwen2.5-VL-7B-Instruct-vision.gguf"
N_CTX = 4096
N_GPU_LAYERS = -1
DEFAULT_TOP_K = 3
DEFAULT_MAX_STEPS = 3

SKILL_LIBRARY_PATH = BASE_DIR / "data" / "skill_library.json"
RESULTS_DIR = BASE_DIR / "results"
CHAT_IMAGE_DIR = RESULTS_DIR / "chat_images"
