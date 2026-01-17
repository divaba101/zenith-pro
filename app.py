# app.py (V18.0)
import streamlit as st
from config import Config
# --- CORRECTION : Mise à jour des modules importés ---
from modules import studio, gallery, ai_chat

# --- Initialisation et Vérification ---
Config.initialize_project()
st.set_page_config(layout="wide", page_title=f"Zenith Pro {Config.VERSION}", page_icon="🪄")

# Appliquer le style CSS
st.markdown("""<style>
    .stButton>button { border-radius: 8px; height: 3em; font-weight: 600; }
    .stTextArea>div>div>textarea { font-family: 'Courier New', monospace; }
</style>""", unsafe_allow_html=True)

# Vérifier la configuration de ComfyUI après avoir initialisé la page
if not Config.is_comfyui_path_valid():
    st.error(
        "Le chemin vers ComfyUI est invalide ou non configuré. "
        "Veuillez définir `COMFYUI_BASE_PATH` dans votre fichier `.env`."
    )
    st.code(f"Exemple : COMFYUI_BASE_PATH = \"C:/Users/VotreNom/Desktop/ComfyUI\"")
    st.stop()

# --- Barre Latérale et Nouvelle Navigation ---
with st.sidebar:
    st.title("🪄 Zenith Pro")
    st.caption(f"Architecture Modulaire v{Config.VERSION}")
    
    # --- CORRECTION : Mise à jour de la liste des pages ---
    pages = ["Studio", "Galerie", "AI Chat"]
    
    if 'page' not in st.session_state:
        st.session_state['page'] = pages[0]
        
    choice = st.radio("Navigation", pages, index=pages.index(st.session_state['page']))
    if choice != st.session_state['page']:
        st.session_state['page'] = choice
        st.rerun()

# --- Routage des pages mis à jour ---
if st.session_state['page'] == "Studio":
    studio.render()
elif st.session_state['page'] == "Galerie":
    gallery.render()
elif st.session_state['page'] == "AI Chat":
    ai_chat.render()

