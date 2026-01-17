# modules/ai_chat.py (V3.1)
import streamlit as st
import requests
import json
from config import Config

class OllamaChat:
    @staticmethod
    def list_models():
        try:
            tags_url = Config.OLLAMA_URL.replace("/api/chat", "/api/tags")
            response = requests.get(tags_url, timeout=5)
            response.raise_for_status()
            return [model["name"] for model in response.json().get("models", [])]
        except Exception as e:
            st.error(f"Impossible de lister les modèles Ollama : {e}"); return []

    @staticmethod
    def get_streaming_response(messages: list, model_name: str):
        payload = {"model": model_name, "messages": messages, "stream": True}
        try:
            with requests.post(Config.OLLAMA_URL, json=payload, stream=True, timeout=60) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        yield content
        except requests.exceptions.Timeout: yield "❌ **Erreur :** Le serveur Ollama n'a pas répondu."
        except Exception as e: yield f"❌ **Erreur de streaming :** `{e}`."

@st.cache_data(ttl=300)
def get_available_models(): return OllamaChat.list_models()

def render():
    st.title("🤖 AI Chat")
    available_models = get_available_models()
    if 'selected_ollama_model' not in st.session_state:
        if Config.OLLAMA_MODEL in available_models: st.session_state.selected_ollama_model = Config.OLLAMA_MODEL
        elif available_models: st.session_state.selected_ollama_model = available_models[0]
        else: st.session_state.selected_ollama_model = None
    if available_models:
        try: current_index = available_models.index(st.session_state.selected_ollama_model)
        except (ValueError, TypeError): current_index = 0
        selected_model = st.selectbox("Modèle Ollama :", options=available_models, index=current_index, key="ollama_model_selector")
        if selected_model != st.session_state.selected_ollama_model:
            st.session_state.selected_ollama_model = selected_model; st.rerun()
    else: st.warning("Aucun modèle trouvé sur le serveur Ollama.")
    if st.button("🗑️ Effacer la conversation", use_container_width=True):
        if "ai_chat_messages" in st.session_state: del st.session_state.ai_chat_messages
        st.rerun()
    st.divider()
    if "ai_chat_messages" not in st.session_state:
        st.session_state.ai_chat_messages = [{"role": "assistant", "content": "Bonjour ! Comment puis-je vous aider ?"}]
    for message in st.session_state.ai_chat_messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    if prompt := st.chat_input("Posez votre question..."):
        if st.session_state.get('selected_ollama_model'):
            st.session_state.ai_chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                response = st.write_stream(OllamaChat.get_streaming_response(st.session_state.ai_chat_messages, st.session_state.selected_ollama_model))
            st.session_state.ai_chat_messages.append({"role": "assistant", "content": response})
        else: st.error("Veuillez sélectionner un modèle.")
