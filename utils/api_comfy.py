# utils/api_comfy.py (V2.5 - Correction du UnboundLocalError)
import requests
import websocket
import json
import time
from pathlib import Path
from PIL import Image
from io import BytesIO
from config import Config
from urllib.parse import quote

def send_to_comfy(prompt: dict, client_id: str) -> str:
    """Envoie le workflow (prompt) à l'API de ComfyUI."""
    url = f"{Config.COMFYUI_URL}/prompt"
    payload = {"prompt": prompt, "client_id": client_id}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json().get('prompt_id', 'NO_ID')
    except Exception as e:
        print(f"Erreur de connexion à ComfyUI: {e}")
        return "ERROR_CONNECTION"

def track_progress(prompt_id: str, client_id: str, console, progress, preview_map):
    """Suit l'avancement de la génération via WebSocket."""
    ws_url = f"ws://{Config.COMFYUI_URL.split('//')[1]}/ws?clientId={client_id}"
    try:
        ws = websocket.create_connection(ws_url)
        with console.status("Génération en cours...", expanded=True) as status:
            while True:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing' and message['data']['node'] is None and message['data']['prompt_id'] == prompt_id:
                        status.update(label="✅ Workflow terminé. Récupération de l'image...")
                        time.sleep(0.5)
                        ws.close()
                        break
                    elif message['type'] == 'progress':
                        # --- CORRECTION DE L'ERREUR ---
                        # On décompose l'opération en étapes claires pour éviter le UnboundLocalError
                        data = message['data']
                        p_val = data['value']
                        p_max = data['max']
                        # --- FIN DE LA CORRECTION ---
                        
                        progress.progress(p_val / p_max)
                        status.update(label=f"Génération en cours... (Étape {p_val}/{p_max})")
    except Exception as e:
        console.error(f"Erreur WebSocket: {e}")
    finally:
        if 'ws' in locals() and ws.connected:
            ws.close()

def get_latest_image(prompt_id: str) -> (Image.Image | None, str | None, Path | None):
    """
    Récupère l'image finale, avec des tentatives répétées et une journalisation détaillée pour contrer la race condition.
    """
    max_retries = 8
    retry_delay = 1

    for attempt in range(max_retries):
        print(f"\n--- [get_latest_image] Tentative {attempt + 1}/{max_retries} ---")
        try:
            url = f"{Config.COMFYUI_URL}/history/{prompt_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            history = response.json()
            prompt_history = history.get(prompt_id)

            if prompt_history and 'outputs' in prompt_history:
                outputs = prompt_history.get('outputs', {})
                for node_id, node_output in outputs.items():
                    if 'images' in node_output:
                        for image_data in node_output['images']:
                            if image_data['type'] == 'output':
                                print("✅ Image trouvée dans l'historique !")
                                source_path = Config.OUTPUT_DIR / image_data.get('subfolder', '') / image_data['filename']
                                image_url = f"{Config.COMFYUI_URL}/view?filename={quote(image_data['filename'])}&subfolder={quote(image_data.get('subfolder', ''))}&type={image_data['type']}"
                                
                                print(f"Téléchargement de l'image depuis : {image_url}")
                                img_response = requests.get(image_url, timeout=10)
                                img_response.raise_for_status()
                                
                                return Image.open(BytesIO(img_response.content)), image_data['filename'], source_path
            
            print("Image non trouvée dans l'historique pour cette tentative.")

        except Exception as e:
            print(f"Erreur durant la tentative {attempt + 1}: {e}")

        print(f"Nouvelle tentative dans {retry_delay} seconde(s)...")
        time.sleep(retry_delay)

    print("--- Échec final de la récupération de l'image après plusieurs tentatives. ---")
    return None, None, None

