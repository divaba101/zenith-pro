# modules/importer.py (V18.0)
import streamlit as st
import requests
import json
import uuid
import re
from config import Config

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
        response = requests.get(api_url, timeout=15)
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
            
            if name and download_url:
                results.append({
                    "name": name,
                    "description": desc_snippet,
                    "download_url": download_url
                })
        return results

    except requests.exceptions.Timeout:
        st.error("Erreur : Le serveur de Civitai a mis trop de temps à répondre.")
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur de connexion à l'API Civitai : {e}")
    except json.JSONDecodeError:
        st.error("Erreur : La réponse de l'API Civitai n'est pas un JSON valide.")
    return []


def render():
    st.subheader("📥 Importateur")
    
    tab1, tab2 = st.tabs(["Rechercher sur Civitai", "Importer depuis un Fichier/URL"])
    
    with tab1:
        st.markdown("### 🔎 Rechercher un modèle sur Civitai")
        search_query = st.text_input("Entrez votre recherche (ex: `epic realism`, `Pony`, `anime`)", key="civitai_search")
        
        if st.button("Lancer la recherche", use_container_width=True):
            if search_query:
                with st.spinner(f"Recherche de '{search_query}' sur Civitai..."):
                    search_results = _search_civitai_models(search_query)
                    st.session_state.civitai_search_results = search_results
            else:
                st.warning("Veuillez entrer un terme de recherche.")

        # Affichage des résultats stockés en session
        if 'civitai_search_results' in st.session_state and st.session_state.civitai_search_results:
            st.divider()
            st.markdown(f"**Résultats de la recherche :**")
            for result in st.session_state.civitai_search_results:
                with st.expander(f"**{result['name']}**"):
                    st.markdown(f"*{result['description']}*")
                    st.markdown(f"**[➡️ Télécharger le modèle]({result['download_url']})**")
                    st.caption("Note : Le lien peut expirer. Faites un clic droit > 'Copier l'adresse du lien' pour l'utiliser avec un gestionnaire de téléchargement.")

    with tab2:
        st.markdown("### 📂 Importer un workflow")
        uploaded_file = st.file_uploader("Chargez un fichier de workflow JSON", type=['json'])
        if uploaded_file and st.button("Sauvegarder le Workflow", key="save_wf", use_container_width=True):
            try:
                file_name = f"imported_{uuid.uuid4().hex[:8]}.json"
                save_path = Config.WF_DIR / file_name
                workflow_data = json.load(uploaded_file)
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(workflow_data, f, indent=4)
                st.success(f"Workflow importé avec succès sous le nom : `{file_name}`")
                st.info("Vous pouvez maintenant le sélectionner dans l'onglet 'Studio'.")
            except json.JSONDecodeError:
                st.error("Le fichier fourni n'est pas un JSON valide.")
            except Exception as e:
                st.error(f"Une erreur est survenue lors de la sauvegarde : {e}")