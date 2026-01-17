# utils/system.py (V6.0 - Rapide, sans métadonnées)
import json
import shutil
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
        shutil.copy2(source_path, Config.GALLERY_PATH)
        return True
    except Exception as e:
        print(f"Erreur lors de la copie vers la galerie: {e}")
        return False
