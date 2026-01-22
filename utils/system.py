# utils/system.py (V7.0 - Surveillance des ressources système)
import json
import shutil
import psutil
import GPUtil
from pathlib import Path
from config import Config

def get_model_maps(model_types=["checkpoints", "loras", "vae"]):
    """
    Liste simplement les modèles sans lire les métadonnées. C'est beaucoup plus rapide.
    La valeur contient maintenant juste le nom du fichier.
    """
    maps = {m_type: {} for m_type in model_types}
    base_path = Config.BASE_PATH / "models"
    for m_type in model_types:
        type_path = base_path / m_type
        if type_path.exists():
            for f in type_path.rglob("*"):
                if f.suffix in [".safetensors", ".ckpt", ".pt", ".bin"]:
                    relative_path = str(f.relative_to(type_path)).replace("\\", "/")
                    maps[m_type][relative_path] = f.name # La valeur est juste le nom
    return maps

def validate_workflow_models(workflow: dict, model_maps: dict) -> list[dict]:
    """Vérifie si les modèles requis par le workflow existent dans les listes."""
    missing = []
    type_map = {"ckpt_name": "checkpoints", "lora_name": "loras", "vae_name": "vae"}
    for node in workflow.values():
        if isinstance(node, dict) and 'inputs' in node:
            for key, path in node['inputs'].items():
                if key in type_map and isinstance(path, str) and path not in model_maps.get(type_map[key], {}):
                    if not any(d['name'] == path for d in missing):
                        missing.append({"name": path, "type": type_map[key]})
    return missing

def update_workflow_paths(workflow: dict, model_maps: dict) -> dict:
    """Fonction de compatibilité, les mises à jour se font dans le UI."""
    return json.loads(json.dumps(workflow))

def copy_to_gallery(source_path: Path):
    """Copie un fichier vers le dossier de galerie personnalisé s'il est configuré."""
    if not Config.GALLERY_PATH or not source_path:
        return False
    try:
        Config.GALLERY_PATH.mkdir(parents=True, exist_ok=True)
        dest_path = Config.GALLERY_PATH / source_path.name
        shutil.copy2(source_path, dest_path)
        create_thumbnail(dest_path)
        return True
    except Exception as e:
        print(f"Erreur lors de la copie vers la galerie: {e}")
        return False

def copy_to_local_storage(source_path: Path):
    """Copie un fichier vers le dossier de stockage local utilisateur s'il est configuré."""
    if not Config.LOCAL_STORAGE_PATH or not source_path:
        return False
    try:
        Config.LOCAL_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, Config.LOCAL_STORAGE_PATH)
        return True
    except Exception as e:
        print(f"Erreur lors de la copie vers le stockage local: {e}")
        return False

def create_thumbnail(source_path: Path, size=(256, 256)):
    """Crée une miniature de l'image source dans le dossier thumbnails de la galerie."""
    if not Config.GALLERY_PATH or not source_path:
        return False
    try:
        from PIL import Image
        thumb_dir = Config.GALLERY_PATH / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_path = thumb_dir / source_path.name
        with Image.open(source_path) as img:
            img.thumbnail(size)
            img.save(thumb_path)
        return True
    except Exception as e:
        print(f"Erreur lors de la création de la miniature: {e}")
        return False

def get_system_resources():
    """Surveille les ressources système (CPU, RAM, GPU)."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        ram_percent = memory.percent
        ram_available_gb = memory.available / (1024 ** 3)

        gpu_info = []
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_info.append({
                    'name': gpu.name,
                    'usage': gpu.load * 100,
                    'memory_used': gpu.memoryUsed,
                    'memory_total': gpu.memoryTotal,
                    'temperature': gpu.temperature
                })
        except:
            gpu_info = None  # GPUtil non disponible

        return {
            'cpu_percent': cpu_percent,
            'ram_percent': ram_percent,
            'ram_available_gb': ram_available_gb,
            'gpu_info': gpu_info
        }
    except Exception as e:
        print(f"Erreur lors de la surveillance des ressources: {e}")
        return None

def is_system_overloaded(threshold_cpu=80, threshold_ram=85, threshold_gpu=90):
    """Vérifie si le système est surchargé selon les seuils donnés."""
    resources = get_system_resources()
    if not resources:
        return False  # En cas d'erreur, on assume que c'est OK

    overloaded = (
        resources['cpu_percent'] > threshold_cpu or
        resources['ram_percent'] > threshold_ram
    )

    if resources['gpu_info']:
        for gpu in resources['gpu_info']:
            if gpu['usage'] > threshold_gpu:
                overloaded = True
                break

    return overloaded

def check_generation_queue_active():
    """Vérifie si des générations sont actives dans la session Streamlit."""
    # Cette fonction sera appelée depuis les modules, donc on utilise st.session_state si disponible
    try:
        import streamlit as st
        jobs = st.session_state.get('generation_jobs', [])
        active_jobs = [job for job in jobs if job.get('status') in ['running', 'queued']]
        return len(active_jobs) > 0
    except:
        return False  # Si pas dans un contexte Streamlit
