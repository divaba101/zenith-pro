# modules/importer.py (V18.0)
import streamlit as st
import requests
import json
import uuid
import re
import os
from pathlib import Path
from config import Config

def format_size(bytes):
    if not bytes or bytes == 0:
        return "Inconnue"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} TB"

def clean_html(raw_html):
    """Supprime les balises HTML d'une chaîne de caractères."""
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def _search_civitai_models(query: str, limit: int = 10):
    """
    Interroge l'API de Civitai pour rechercher des modèles et retourne une liste formatée.
    """
    api_url = f"https://civitai.com/api/v1/models?query={query}&limit={limit}"
    results = []

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json().get('items', [])

        for model in data:
            name = model.get('name')
            
            # Extraction de la description
            raw_desc = model.get('description', '')
            clean_desc = clean_html(raw_desc).strip()
            desc_snippet = "\n".join(clean_desc.split('\n')[:2]) # Prend les 2 premières lignes
            if not desc_snippet:
                desc_snippet = "Aucune description disponible."

            # Extraction du lien de téléchargement (le plus récent)
            download_url = None
            if model.get('modelVersions') and len(model['modelVersions']) > 0:
                latest_version = model['modelVersions'][0]
                if latest_version.get('files') and len(latest_version['files']) > 0:
                    # On privilégie un fichier .safetensors si possible
                    file_to_download = latest_version['files'][0]
                    for f in latest_version['files']:
                        if f['name'].endswith('.safetensors'):
                            file_to_download = f
                            break
                    download_url = file_to_download.get('downloadUrl')
                    filename = file_to_download.get('name', f"{name.replace(' ', '_')}.safetensors")

            # Image
            image_url = None
            if model.get('modelVersions') and model['modelVersions'][0].get('images'):
                image_url = model['modelVersions'][0]['images'][0].get('url')

            # Size
            size_bytes = None
            if download_url:
                try:
                    headers = {"Authorization": f"Bearer {Config.CIVITAI_API_KEY}"} if Config.CIVITAI_API_KEY else {}
                    head = requests.head(download_url, headers=headers, timeout=5)
                    size_bytes = int(head.headers.get('content-length', 0))
                except:
                    size_bytes = file_to_download.get('sizeKB')
                    if size_bytes:
                        size_bytes *= 1024  # Convert KB to bytes

            model_type = model.get('type', 'Unknown')
            if name and download_url:
                results.append({
                    "name": name,
                    "description": desc_snippet,
                    "download_url": download_url,
                    "type": model_type,
                    "filename": filename,
                    "source": "Civitai",
                    "image_url": image_url,
                    "size_bytes": size_bytes
                })
        return results

    except requests.exceptions.Timeout:
        st.error("Erreur : Le serveur de Civitai a mis trop de temps à répondre.")
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur de connexion à l'API Civitai : {e}")
    except json.JSONDecodeError:
        st.error("Erreur : La réponse de l'API Civitai n'est pas un JSON valide.")
    return []


def _search_huggingface_models(query: str, limit: int = 10):
    """
    Interroge l'API Hugging Face pour rechercher des modèles Stable Diffusion.
    """
    api_url = f"https://huggingface.co/api/models?search={query}&tags=stable-diffusion&limit={limit}"
    results = []

    headers = {}
    if Config.HUGGINGFACE_API_KEY:
        headers["Authorization"] = f"Bearer {Config.HUGGINGFACE_API_KEY}"

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        for model in data:
            name = model.get('id', '').split('/')[-1]
            description = model.get('description', '') or model.get('cardData', {}).get('description', '')
            clean_desc = clean_html(description).strip()[:200] + "..." if len(description) > 200 else clean_html(description).strip()
            if not clean_desc:
                clean_desc = "Aucune description disponible."

            # Déterminer le type
            tags = model.get('tags', [])
            model_type = 'Checkpoint'
            if 'lora' in tags or 'LoRA' in tags:
                model_type = 'LORA'
            elif 'vae' in tags or 'VAE' in tags:
                model_type = 'VAE'

            image_url = None
            if model.get('cardData', {}).get('model-index', []):
                for idx in model['cardData']['model-index']:
                    if 'results' in idx:
                        for res in idx['results']:
                            if res.get('metrics') and 'IS' in str(res['metrics']):
                                image_url = f"https://huggingface.co/{model['id']}/resolve/main/{res.get('dataset', {}).get('name', '')}"
                                break
                        if image_url:
                            break

            download_url = f"https://huggingface.co/{model['id']}/resolve/main/model.safetensors"  # Approximation
            filename = f"{name}.safetensors"

            size_bytes = None
            try:
                head = requests.head(download_url, timeout=5)
                size_bytes = int(head.headers.get('content-length', 0))
            except:
                pass

            if name and download_url:
                results.append({
                    "name": name,
                    "description": clean_desc,
                    "download_url": download_url,
                    "type": model_type,
                    "filename": filename,
                    "source": "Hugging Face",
                    "image_url": image_url,
                    "size_bytes": size_bytes
                })
        return results

    except Exception as e:
        st.error(f"Erreur Hugging Face : {e}")
        return []



def download_model(download_url, model_name, model_type, filename, source=""):
    if not Config.BASE_PATH:
        st.error("Chemin ComfyUI non configuré dans .env.")
        return

    type_to_folder = {
        'Checkpoint': 'checkpoints',
        'LORA': 'loras',
        'VAE': 'vae',
        'TextualInversion': 'embeddings',
        'Controlnet': 'controlnet',
    }
    folder = type_to_folder.get(model_type, 'checkpoints')

    models_dir = Config.BASE_PATH / 'models' / folder
    models_dir.mkdir(parents=True, exist_ok=True)

    filepath = models_dir / filename
    if filepath.exists():
        st.warning(f"Le fichier '{filename}' existe déjà dans models/{folder}/.")
        return

    headers = {}
    if source == "Civitai" and Config.CIVITAI_API_KEY:
        headers["Authorization"] = f"Bearer {Config.CIVITAI_API_KEY}"
    elif source == "Hugging Face" and Config.HUGGINGFACE_API_KEY:
        headers["Authorization"] = f"Bearer {Config.HUGGINGFACE_API_KEY}"

    try:
        response = requests.get(download_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        downloaded = 0
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        st.success(f"Modèle '{model_name}' téléchargé avec succès dans models/{folder}/ ({downloaded} bytes)")
    except requests.exceptions.Timeout:
        st.error("Erreur : Téléchargement expiré.")
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur de téléchargement : {e}")
    except Exception as e:
        st.error(f"Erreur inattendue : {e}")


def render():
    st.subheader("📥 Importateur")

    tab1, tab2 = st.tabs(["Rechercher des modèles", "Importer depuis un Fichier/URL"])

    with tab1:
        st.markdown("### 🔎 Rechercher des modèles")

        # Sources disponibles
        available_sources = ["Hugging Face"]
        if Config.CIVITAI_API_KEY:
            available_sources.append("Civitai")

        selected_sources = st.multiselect(
            "Sélectionnez les sources de recherche :",
            options=available_sources,
            default=available_sources,
            key="selected_sources"
        )

        search_query = st.text_input("Entrez votre recherche (ex: `epic realism`, `Pony`, `anime`)", key="model_search")

        if st.button("Lancer la recherche", use_container_width=True):
            if search_query and selected_sources:
                all_results = []
                with st.spinner(f"Recherche de '{search_query}' sur {', '.join(selected_sources)}..."):
                    if "Civitai" in selected_sources:
                        all_results.extend(_search_civitai_models(search_query))
                    if "Hugging Face" in selected_sources:
                        all_results.extend(_search_huggingface_models(search_query))
                st.session_state.search_results = all_results
            else:
                st.warning("Veuillez entrer un terme de recherche et sélectionner au moins une source.")

        # Affichage des résultats stockés en session
        if 'search_results' in st.session_state and st.session_state.search_results:
            st.divider()
            st.markdown(f"**Résultats de la recherche :**")
            for result in st.session_state.search_results:
                with st.expander(f"**{result['name']}** ({result['source']})"):
                    if result.get('image_url'):
                        st.image(result['image_url'], width=200)
                    st.markdown(f"*{result['description']}*")
                    st.markdown(f"**Type :** {result['type']}")
                    st.markdown(f"**Taille :** {format_size(result.get('size_bytes'))}")
                    if st.button("Télécharger automatiquement", key=f"download_{result['source']}_{result['name'].replace(' ', '_')}", use_container_width=True):
                        download_model(result['download_url'], result['name'], result['type'], result['filename'], result['source'])
                    st.markdown(f"**[➡️ Télécharger manuellement]({result['download_url']})**")
                    st.caption("Note : Le lien peut expirer. Faites un clic droit > 'Copier l'adresse du lien' pour l'utiliser avec un gestionnaire de téléchargement.")

    with tab2:
        st.markdown("### 📂 Importer un workflow")
        uploaded_file = st.file_uploader("Chargez un fichier de workflow JSON", type=['json'])
        if uploaded_file and st.button("Sauvegarder le Workflow", key="save_wf", use_container_width=True):
            try:
                workflow_data = json.load(uploaded_file)
                if not isinstance(workflow_data, dict):
                    st.error("Le fichier n'est pas un objet JSON valide.")
                    return
                if 'nodes' not in workflow_data:
                    st.warning("Le fichier ne contient pas de 'nodes'. Ce n'est peut-être pas un workflow ComfyUI valide.")
                file_name = f"imported_{uuid.uuid4().hex[:8]}.json"
                save_path = Config.WF_DIR / file_name
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow_data, f, indent=4)
                st.success(f"Workflow importé avec succès sous le nom : `{file_name}`")
                st.info("Vous pouvez maintenant le sélectionner dans l'onglet 'Studio'.")
            except json.JSONDecodeError:
                st.error("Le fichier fourni n'est pas un JSON valide.")
            except Exception as e:
                st.error(f"Une erreur est survenue lors de la sauvegarde : {e}")
