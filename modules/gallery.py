# modules/gallery.py (V18.2 - Correction finale de la dépréciation)
import streamlit as st
import json
from PIL import Image
from config import Config
from pathlib import Path

def _get_hidden_list():
    if Config.HIDDEN_FILES_DB.exists():
        try:
            with open(Config.HIDDEN_FILES_DB, 'r', encoding='utf-8') as f: return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError): return []
    return []

def _set_hidden_list(hidden_list):
    with open(Config.HIDDEN_FILES_DB, 'w', encoding='utf-8') as f: json.dump(hidden_list, f)

def _hide_image(filename):
    hidden = _get_hidden_list()
    if filename not in hidden:
        hidden.append(filename)
        _set_hidden_list(hidden)

def _unhide_image(filename):
    hidden = _get_hidden_list()
    if filename in hidden:
        hidden.remove(filename)
        _set_hidden_list(hidden)

def _create_txt_log(img_path):
    log_path = Config.LOG_DIR / f"{img_path.stem}.txt"
    try:
        img = Image.open(img_path)
        content = img.info.get('prompt', 'Aucune métadonnée de prompt trouvée.')
        with open(log_path, 'w', encoding='utf-8') as f: f.write(content)
        st.toast(f"Log TXT créé : {log_path.name}")
    except Exception as e: st.error(f"Erreur lors de la création du log : {e}")

def render():
    st.subheader("🖼️ Galerie d'Images & Actions")
    
    use_custom_gallery = isinstance(Config.GALLERY_PATH, Path) and Config.GALLERY_PATH.exists()
    source_path = Config.GALLERY_PATH if use_custom_gallery else Config.OUTPUT_DIR
    
    st.caption(f"Affichage du répertoire : `{source_path}`")
    
    if not source_path or not source_path.exists():
        st.warning(f"Le répertoire d'images '{source_path}' est introuvable. Vérifiez votre configuration.")
        return

    hidden_list = _get_hidden_list()
    c1, c2 = st.columns([0.7, 0.3])
    with c1: search = st.text_input("🔍 Rechercher par nom...")
    with c2: show_hidden = st.checkbox("Voir les images masquées", value=False)
    
    all_images = sorted(source_path.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    images_to_display = [p for p in all_images if (show_hidden or p.name not in hidden_list) and (not search or search.lower() in p.name.lower())]

    if not images_to_display:
        st.info("Aucune image à afficher dans ce répertoire.")
        return

    cols = st.columns(3)
    for idx, path in enumerate(images_to_display):
        with cols[idx % 3]:
            try:
                st.image(str(path), use_column_width='always')
                
                is_hidden = path.name in hidden_list
                action_cols = st.columns(4)
                
                if action_cols[0].button("🗑️", key=f"del_{path.name}", help="Supprimer l'image"):
                    path.unlink(); st.rerun()
                
                button_char, help_text = ("🔽", "Afficher") if is_hidden else ("🔼", "Masquer")
                if action_cols[1].button(button_char, key=f"toggle_hide_{path.name}", help=help_text):
                    _unhide_image(path.name) if is_hidden else _hide_image(path.name)
                    st.rerun()

                if action_cols[2].button("🔄", key=f"play_{path.name}", help="Rejouer dans le Studio"):
                    img = Image.open(path)
                    if 'prompt' in img.info:
                        st.session_state['active_workflow'] = json.loads(img.info['prompt'])
                        st.session_state['page'] = "Studio"
                        st.rerun()
                    else: st.warning("Aucun workflow trouvé dans les métadonnées.")

                if action_cols[3].button("📝", key=f"log_{path.name}", help="Créer un log .txt"):
                    _create_txt_log(path)
            except FileNotFoundError: st.rerun()
            except Exception as e: st.error(f"Erreur avec {path.name}: {e}")
