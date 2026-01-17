# utils/ai_logic.py (V1.4)
import requests
from config import Config

class ZenithAI:
    @staticmethod
    def chat(messages):
        """Communique avec l'API d'Ollama de manière sécurisée."""
        payload = {"model": Config.OLLAMA_MODEL, "messages": messages, "stream": False}
        try:
            response = requests.post(Config.OLLAMA_URL, json=payload, timeout=30)
            response.raise_for_status()  # Lève une exception pour les codes d'erreur HTTP (4xx, 5xx)
            return response.json().get("message", {}).get("content", "Réponse vide.")
        except requests.exceptions.Timeout:
            return "❌ Erreur: Le serveur Ollama a mis trop de temps à répondre."
        except requests.exceptions.RequestException as e:
            return f"❌ Erreur de connexion à Ollama: {e}"
        except Exception as e:
            return f"❌ Une erreur inattendue est survenue: {e}"

    @staticmethod
    def apply_turbo_mode(wf, steps=12, threshold=20):
        """Applique un mode de génération rapide au workflow."""
        for node in wf.values():
            if 'sampler_name' in node.get('inputs', {}):
                node['inputs']['sampler_name'] = 'euler'
                node['inputs']['scheduler'] = 'simple'
                if node['inputs'].get('steps', 0) > threshold:
                    node['inputs']['steps'] = steps
        return wf

    @staticmethod
    def analyze_workflow(wf):
        """
        Analyse un workflow pour extraire des informations pertinentes.
        Exemple : trouver les modèles manquants.
        """
        # (Implémentation future possible)
        missing_models = []
        # ... logique pour vérifier si les modèles du wf existent sur le disque
        return {
            "node_count": len(wf),
            "missing_models": missing_models
        }
