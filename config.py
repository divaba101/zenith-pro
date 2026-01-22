# config.py (V3.2)
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    VERSION = "3.2"

    # --- Chemins de base du projet ---
    PROJECT_ROOT = Path(__file__).resolve().parent
    WF_DIR = PROJECT_ROOT / "workflows" / "API"
    LOG_DIR = PROJECT_ROOT / "logs"
    HIDDEN_FILES_DB = LOG_DIR / ".hidden_images.json"
    
    # --- NOUVEAU : Dossier pour les configurations sauvegardées ---
    PRESETS_DIR = PROJECT_ROOT / "presets"

    # --- Configuration externe depuis .env ---
    BASE_PATH_STR = os.getenv("COMFYUI_BASE_PATH")
    COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
    GALLERY_PATH_STR = os.getenv("GALLERY_PATH")
    LOCAL_STORAGE_PATH_STR = os.getenv("LOCAL_STORAGE_PATH")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # --- API Keys pour les importations ---
    CIVITAI_API_KEY = os.getenv("CIVITAI_API_KEY")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

    # --- Initialisation sécurisée des chemins ---
    BASE_PATH = Path(BASE_PATH_STR) if BASE_PATH_STR and BASE_PATH_STR.strip() else None
    OUTPUT_DIR = BASE_PATH / "output" if BASE_PATH else None
    INPUT_DIR = BASE_PATH / "input" if BASE_PATH else None
    GALLERY_PATH = Path(GALLERY_PATH_STR) if GALLERY_PATH_STR and GALLERY_PATH_STR.strip() else None
    LOCAL_STORAGE_PATH = Path(LOCAL_STORAGE_PATH_STR) if LOCAL_STORAGE_PATH_STR and LOCAL_STORAGE_PATH_STR.strip() else None

    @staticmethod
    def initialize_project():
        Config.WF_DIR.mkdir(parents=True, exist_ok=True)
        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        # S'assure que le dossier des presets existe
        Config.PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_comfyui_path_valid():
        if not isinstance(Config.BASE_PATH, Path) or not Config.BASE_PATH.exists(): return False
        if not isinstance(Config.OUTPUT_DIR, Path) or not Config.OUTPUT_DIR.exists(): return False
        return True

    @staticmethod
    def is_comfyui_reachable():
        try:
            import requests
            response = requests.get(f'{Config.COMFYUI_URL}/queue', timeout=5)
            return response.status_code == 200
        except:
            return False
