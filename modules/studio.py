# modules/studio.py (V32.5.1 - Correction de st.dialog)
import streamlit as st
import json
import uuid
import time
import threading
from pathlib import Path
from datetime import datetime
from config import Config
from utils.api_comfy import send_to_comfy, track_progress, get_latest_image, poll_job_status
from utils.system import get_model_maps, update_workflow_paths, validate_workflow_models, copy_to_gallery, copy_to_local_storage

# (Listes et fonctions de base inchangées)
COMMON_SAMPLERS = ["euler", "euler_ancestral", "dpmpp_2s_ancestral", "dpmpp_2m_sde", "ddim", "lcm"]
COMMON_SCHEDULERS = ["normal", "karras", "exponential", "simple", "ddim_uniform"]
def load_model_maps(): return get_model_maps(["checkpoints", "loras", "vae"])

def add_lora_node_to_workflow(wf: dict, lora_options: list):
    if not lora_options: st.warning("Aucune LoRA disponible à ajouter."); return
    sampler_nodes = {nid: n for nid, n in wf.items() if isinstance(n, dict) and "KSampler" in n.get("class_type", "")}
    if not sampler_nodes: st.warning("Impossible d'ajouter une LoRA : aucun KSampler trouvé."); return
    lora_loaders = {nid: n for nid, n in wf.items() if isinstance(n, dict) and "lora_name" in n.get("inputs", {})}
    new_node_id = str(max(int(k) for k in wf if k.isdigit()) + 1)
    if not lora_loaders:
        ckpt_loaders = {nid: n for nid, n in wf.items() if isinstance(n, dict) and "ckpt_name" in n.get("inputs", {})}
        if not ckpt_loaders: st.warning("Impossible d'ajouter une LoRA : aucun CheckpointLoader trouvé."); return
        first_ckpt_loader_id = list(ckpt_loaders.keys())[0]
        wf[new_node_id] = {"inputs": {"model": [first_ckpt_loader_id, 0], "clip": [first_ckpt_loader_id, 1], "lora_name": lora_options[0], "strength_model": 0.8, "strength_clip": 0.8}, "class_type": "LoraLoader", "_meta": {"title": "LoRA Ajoutée"}}
        for sampler_node in sampler_nodes.values():
            if sampler_node["inputs"]["model"][0] == first_ckpt_loader_id: sampler_node["inputs"]["model"] = [new_node_id, 0]
        st.toast(f"Première LoRA (Nœud {new_node_id}) ajoutée !")
    else:
        source_nodes = {node.get("inputs", {}).get("model", [None])[0] for node in lora_loaders.values()}
        end_of_chain_loras = [nid for nid in lora_loaders if nid not in source_nodes]
        last_lora_id = end_of_chain_loras[0] if end_of_chain_loras else list(lora_loaders.keys())[0]
        wf[new_node_id] = {"inputs": {"model": [last_lora_id, 0], "clip": [last_lora_id, 1], "lora_name": lora_options[0], "strength_model": 0.8, "strength_clip": 0.8}, "class_type": "LoraLoader", "_meta": {"title": "LoRA Ajoutée"}}
        for sampler_node in sampler_nodes.values():
            if sampler_node["inputs"]["model"][0] == last_lora_id: sampler_node["inputs"]["model"] = [new_node_id, 0]
        st.toast(f"Nouvelle LoRA (Nœud {new_node_id}) ajoutée !")

def render_presets_popover(wf: dict):
    with st.popover("💾 Presets", use_container_width=True):
        st.markdown("##### Sauvegarder la configuration")
        preset_name = st.text_input("Nom du preset", placeholder="Ex: Portrait Sci-Fi...", label_visibility="collapsed")
        if st.button("Sauvegarder", use_container_width=True):
            if preset_name:
                filename = f"{preset_name.replace(' ', '_').lower()}.json"
                save_path = Config.PRESETS_DIR / filename
                with open(save_path, 'w', encoding='utf-8') as f: json.dump(wf, f, indent=2)
                st.toast(f"Preset '{preset_name}' sauvegardé !"); st.rerun()
            else: st.warning("Veuillez donner un nom.")
        st.divider()
        st.markdown("##### Charger une configuration")
        presets = sorted(Config.PRESETS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not presets: st.info("Aucun preset sauvegardé."); return
        if 'preset_page' not in st.session_state: st.session_state.preset_page = 0
        items_per_page, start_idx = 5, st.session_state.preset_page * 5
        paginated_presets = presets[start_idx : start_idx + items_per_page]
        for preset_path in paginated_presets:
            preset_display_name = preset_path.stem.replace('_', ' ').capitalize()
            with st.container(border=True):
                st.write(f"**{preset_display_name}**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🔍 Détails", key=f"details_{preset_path.name}", use_container_width=True):
                        st.session_state.show_preset_details = preset_path; st.rerun()
                with c2:
                    if st.button("🔌 Charger", key=f"load_{preset_path.name}", use_container_width=True):
                        with open(preset_path, 'r', encoding='utf-8') as f: loaded_wf = json.load(f)
                        positive_nodes = [n for n in loaded_wf.values() if isinstance(n, dict) and "positive" in n.get("_meta", {}).get("title", "").lower()]
                        for node in positive_nodes: node['inputs']['text'] = ""
                        st.session_state.active_workflow, st.session_state.workflow_version = loaded_wf, st.session_state.workflow_version + 1
                        st.toast(f"Preset '{preset_display_name}' chargé."); st.rerun()
                with c3:
                    if st.button("🗑️", key=f"del_{preset_path.name}", use_container_width=True):
                        preset_path.unlink(); st.rerun()
        total_pages = (len(presets) + items_per_page - 1) // items_per_page
        if total_pages > 1:
            pc1, pc2, pc3 = st.columns([0.4, 0.2, 0.4])
            with pc1:
                if st.button("⬅️", disabled=st.session_state.preset_page == 0): st.session_state.preset_page -= 1; st.rerun()
            with pc2: st.write(f"{st.session_state.preset_page + 1}/{total_pages}")
            with pc3:
                if st.button("➡️", disabled=st.session_state.preset_page >= total_pages - 1): st.session_state.preset_page += 1; st.rerun()

def display_preset_details_container():
    """Affiche un conteneur 'modal' pour les détails du preset."""
    preset_path = st.session_state.show_preset_details
    preset_name = preset_path.stem.replace('_', ' ').capitalize()
    
    # --- CORRECTION : On utilise un st.container au lieu de st.dialog ---
    with st.container(border=True):
        st.subheader(f"Détails de '{preset_name}'")
        try:
            with open(preset_path, 'r', encoding='utf-8') as f: data = json.load(f)
            st.markdown("##### Modèles principaux")
            ckpt = next((n['inputs']['ckpt_name'] for n in data.values() if isinstance(n, dict) and 'ckpt_name' in n.get('inputs', {})), "Non trouvé")
            loras = [n['inputs']['lora_name'] for n in data.values() if isinstance(n, dict) and 'lora_name' in n.get('inputs', {})]
            vae = next((n['inputs']['vae_name'] for n in data.values() if isinstance(n, dict) and 'vae_name' in n.get('inputs', {})), "Par défaut")
            st.text(f"Checkpoint: {Path(ckpt).name}"); st.text(f"VAE: {Path(vae).name}")
            if loras: st.text("LoRAs:"); st.json([Path(l).name for l in loras])
            st.divider()
            st.download_button("📄 Exporter ce workflow (JSON API)", json.dumps(data, indent=2), f"workflow_{preset_path.name}", "application/json", use_container_width=True)
        except Exception as e: st.error(f"Impossible de lire les détails : {e}")
        
        if st.button("Fermer les détails", use_container_width=True):
             del st.session_state.show_preset_details
             st.rerun()
    st.divider() # Ajoute un séparateur visuel

def render_prompt_inputs(wf, version):
    st.divider(); st.subheader("✨ Prompts")
    positive_prompt_nodes = {nid: n for nid, n in wf.items() if isinstance(n, dict) and n.get("class_type") == "CLIPTextEncode" and "positive" in n.get("_meta", {}).get("title", "").lower()}
    negative_prompt_nodes = {nid: n for nid, n in wf.items() if isinstance(n, dict) and n.get("class_type") == "CLIPTextEncode" and "negative" in n.get("_meta", {}).get("title", "").lower()}
    if not positive_prompt_nodes and not negative_prompt_nodes:
        sampler_nodes = {nid: n for nid, n in wf.items() if isinstance(n, dict) and "KSampler" in n.get("class_type", "")}
        if sampler_nodes:
            sampler_input_map = list(sampler_nodes.values())[0]['inputs']
            pos_id = sampler_input_map.get('positive', [None])[0]
            neg_id = sampler_input_map.get('negative', [None])[0]
            if pos_id: positive_prompt_nodes = {pos_id: wf.get(pos_id)}
            if neg_id: negative_prompt_nodes = {neg_id: wf.get(neg_id)}
    if positive_prompt_nodes:
        for i, (nid, node) in enumerate(positive_prompt_nodes.items()):
            if node: node['inputs']['text'] = st.text_area("Prompt Positif", value=node['inputs']['text'], height=150, key=f"widget_pos_prompt_{i}_{version}")
    if negative_prompt_nodes:
        for i, (nid, node) in enumerate(negative_prompt_nodes.items()):
            if node: node['inputs']['text'] = st.text_area("Prompt Négatif", value=node['inputs']['text'], height=100, key=f"widget_neg_prompt_{i}_{version}")

def render_model_selectors(wf, model_maps, version):
    with st.expander("📦 Modèles du Workflow"):
        ckpt_nodes, lora_nodes, vae_nodes = [n for n in wf.values() if isinstance(n, dict) and "ckpt_name" in n.get("inputs", {})], [n for n in wf.values() if isinstance(n, dict) and "lora_name" in n.get("inputs", {})], [n for n in wf.values() if isinstance(n, dict) and "vae_name" in n.get("inputs", {})]
        if ckpt_nodes:
            st.markdown("##### 💠 Checkpoint(s)")
            for i, node in enumerate(ckpt_nodes):
                options, current_val = list(model_maps["checkpoints"].keys()), node['inputs']['ckpt_name']
                try: current_index = options.index(current_val)
                except ValueError: current_index = 0
                node['inputs']['ckpt_name'] = st.selectbox("Checkpoint", options, current_index, lambda x: model_maps["checkpoints"][x], key=f"sel_ckpt_{i}_{version}")
        if lora_nodes:
            st.markdown("##### 🎨 LoRA(s)")
            for i, node in enumerate(lora_nodes):
                options, current_val = list(model_maps["loras"].keys()), node['inputs']['lora_name']
                try: current_index = options.index(current_val)
                except ValueError: current_index = 0
                node['inputs']['lora_name'] = st.selectbox("LoRA", options, current_index, lambda x: model_maps["loras"][x], key=f"sel_lora_{i}_{version}")
        if st.button("➕ Ajouter une LoRA", use_container_width=True): add_lora_node_to_workflow(wf, list(model_maps["loras"].keys())); st.rerun()
        if vae_nodes:
            st.markdown("##### ✨ VAE(s)")
            for i, node in enumerate(vae_nodes):
                options, current_val = list(model_maps["vae"].keys()), node['inputs']['vae_name']
                try: current_index = options.index(current_val)
                except ValueError: current_index = 0
                node['inputs']['vae_name'] = st.selectbox("VAE", options, current_index, lambda x: model_maps["vae"][x], key=f"sel_vae_{i}_{version}")

def render_advanced_settings(wf, version):
    with st.expander("🛠️ Réglages Avancés"):
        sampler_nodes, latent_nodes = {nid: n for nid, n in wf.items() if isinstance(n, dict) and "KSampler" in n.get("class_type", "")}, {nid: n for nid, n in wf.items() if isinstance(n, dict) and n.get("class_type") == "EmptyLatentImage"}
        if sampler_nodes:
            st.markdown("##### Paramètres du Sampler")
            inputs, c1, c2 = list(sampler_nodes.values())[0]['inputs'], *st.columns(2)
            with c1:
                try: sampler_index = COMMON_SAMPLERS.index(inputs['sampler_name'])
                except ValueError: COMMON_SAMPLERS.insert(0, inputs['sampler_name']); sampler_index = 0
                inputs['sampler_name'] = st.selectbox("Sampler", COMMON_SAMPLERS, index=sampler_index, key=f"widget_sampler_{version}")
                try: scheduler_index = COMMON_SCHEDULERS.index(inputs['scheduler'])
                except ValueError: COMMON_SCHEDULERS.insert(0, inputs['scheduler']); scheduler_index = 0
                inputs['scheduler'] = st.selectbox("Scheduler", COMMON_SCHEDULERS, index=scheduler_index, key=f"widget_scheduler_{version}")
            with c2:
                inputs['seed'] = st.number_input("Seed", value=inputs['seed'], key=f"widget_seed_{version}")
                inputs['steps'] = st.slider("Steps", 1, 150, value=inputs['steps'], key=f"widget_steps_{version}")
                inputs['cfg'] = st.slider("CFG", 0.0, 30.0, value=float(inputs['cfg']), step=0.5, key=f"widget_cfg_{version}")
        if latent_nodes:
            st.markdown("##### Dimensions de l'Image")
            inputs, c1, c2, c3 = list(latent_nodes.values())[0]['inputs'], *st.columns(3)
            with c1: inputs['width'] = st.number_input("Largeur", value=inputs['width'], min_value=64, step=8, key=f"widget_width_{version}")
            with c2: inputs['height'] = st.number_input("Hauteur", value=inputs['height'], min_value=64, step=8, key=f"widget_height_{version}")
            with c3: inputs['batch_size'] = st.slider("Lot", 1, 10, value=inputs['batch_size'], key=f"widget_batch_{version}")

def initialize_generation_queue():
    """Initialize the generation queue in session state."""
    if 'generation_jobs' not in st.session_state:
        st.session_state.generation_jobs = []
    if 'job_counter' not in st.session_state:
        st.session_state.job_counter = 0

def update_job_statuses():
    """Update the status of all running jobs."""
    jobs = st.session_state.generation_jobs
    running_jobs = [job for job in jobs if job['status'] == 'running']

    for job in running_jobs:
        status_info = poll_job_status(job['prompt_id'])
        job['progress'] = status_info['progress']

        if status_info['status'] == 'completed':
            job['status'] = 'completed'
            # Fetch the image
            img_data, img_name, source_path = get_latest_image(job['prompt_id'])
            if img_data:
                job['image'] = img_data
                job['image_name'] = img_name
                job['source_path'] = source_path
                # Show toast with thumbnail
                st.toast(f"✅ Génération terminée: {img_name}", icon="🎉")
                # Copy to destinations
                if copy_to_gallery(source_path):
                    st.toast(f"📁 Image copiée dans la galerie")
                if copy_to_local_storage(source_path):
                    st.toast(f"💾 Image copiée dans le stockage local")
            else:
                job['status'] = 'failed'
                st.toast("❌ Échec de récupération de l'image", icon="⚠️")

        elif status_info['status'] == 'failed':
            job['status'] = 'failed'
            st.toast(f"❌ Génération échouée: {status_info.get('error', 'Erreur inconnue')}", icon="⚠️")

def start_pending_jobs():
    """Start jobs that are queued if slots are available."""
    jobs = st.session_state.generation_jobs
    running_count = sum(1 for job in jobs if job['status'] == 'running')
    max_concurrent = 5

    queued_jobs = [job for job in jobs if job['status'] == 'queued']
    for job in queued_jobs:
        if running_count >= max_concurrent:
            break

        # Start the job
        prompt_id = send_to_comfy(job['workflow'], st.session_state.client_id)
        if prompt_id != "ERROR_CONNECTION":
            job['prompt_id'] = prompt_id
            job['status'] = 'running'
            job['start_time'] = datetime.now()
            running_count += 1
        else:
            job['status'] = 'failed'
            st.toast("❌ Connexion à ComfyUI échouée", icon="⚠️")

def add_generation_job(workflow, model_maps, turbo_mode):
    """Add a new generation job to the queue."""
    job_id = st.session_state.job_counter
    st.session_state.job_counter += 1

    # Prepare workflow (same as before)
    final_wf = workflow.copy()

    job = {
        'id': job_id,
        'workflow': final_wf,
        'status': 'queued',
        'progress': 0.0,
        'prompt_id': None,
        'start_time': None,
        'image': None,
        'image_name': None,
        'source_path': None,
        'turbo_mode': turbo_mode
    }

    st.session_state.generation_jobs.append(job)
    start_pending_jobs()
    st.toast(f"🎯 Génération ajoutée à la file (#{job_id})", icon="➕")

def render_generation_queue():
    """Render the generation queue with modern, clean styling."""
    jobs = st.session_state.generation_jobs

    if not jobs:
        return

    # Clean up completed jobs older than 5 minutes
    now = datetime.now()
    st.session_state.generation_jobs = [
        job for job in jobs
        if not (job['status'] == 'completed' and
                job.get('start_time') and
                (now - job['start_time']).seconds > 300)
    ]

    active_jobs = [job for job in st.session_state.generation_jobs
                   if job['status'] in ['queued', 'running', 'completed']]

    if not active_jobs:
        return

    st.markdown("---")
    col_title, col_clear = st.columns([0.8, 0.2])
    with col_title:
        st.subheader("🎨 File de Génération")
    with col_clear:
        if st.button("🗑️ Vider", key="clear_completed", help="Supprimer les générations terminées"):
            st.session_state.generation_jobs = [
                job for job in st.session_state.generation_jobs
                if job['status'] != 'completed'
            ]
            st.rerun()

    for job in active_jobs:
        with st.container(border=True):
            col_info, col_progress = st.columns([0.7, 0.3])

            with col_info:
                status_emoji = {
                    'queued': '⏳',
                    'running': '⚡',
                    'completed': '✅',
                    'failed': '❌'
                }.get(job['status'], '❓')

                status_text = {
                    'queued': 'En attente',
                    'running': 'En cours',
                    'completed': 'Terminée',
                    'failed': 'Échouée'
                }.get(job['status'], 'Inconnue')

                st.markdown(f"**{status_emoji} Génération #{job['id']}** - {status_text}")

                if job['status'] == 'running' and job.get('start_time'):
                    elapsed = (datetime.now() - job['start_time']).seconds
                    st.caption(f"Temps écoulé: {elapsed}s")

                if job['status'] == 'completed' and job.get('image_name'):
                    st.caption(f"Image: {job['image_name']}")

            with col_progress:
                if job['status'] == 'running':
                    st.progress(job['progress'], text=".1%")
                elif job['status'] == 'completed' and job.get('image'):
                    # Show thumbnail
                    st.image(job['image'], width=80, caption="")
                elif job['status'] == 'failed':
                    st.error("Échec")

def render():
    st.title("🎮 Studio Zenith Pro")
    if 'client_id' not in st.session_state:
        st.session_state.client_id = str(uuid.uuid4())
    if 'workflow_version' not in st.session_state:
        st.session_state.workflow_version = 0

    initialize_generation_queue()
    update_job_statuses()

    # On affiche le conteneur de détails en premier s'il est activé
    if 'show_preset_details' in st.session_state and st.session_state.show_preset_details:
        display_preset_details_container()

    model_maps = load_model_maps()
    col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
    with col1:
        files = sorted([f.name for f in Config.WF_DIR.glob("*.json")])
        selected_wf_file = st.selectbox("Workflow de base", files, key="selectbox_workflow")
    with col2:
        turbo_mode = st.toggle("🚀 MODE TURBO")
    with col3:
        if 'active_workflow' in st.session_state:
            render_presets_popover(st.session_state.active_workflow)

    if st.session_state.get('last_wf') != selected_wf_file:
        with open(Config.WF_DIR / selected_wf_file, 'r', encoding='utf-8') as f:
            st.session_state.active_workflow = json.load(f)
        st.session_state.last_wf = selected_wf_file
        st.session_state.workflow_version += 1
        st.rerun()

    if 'active_workflow' in st.session_state:
        wf_in_session, wf_version = st.session_state.active_workflow, st.session_state.workflow_version
        render_prompt_inputs(wf_in_session, wf_version)
        render_model_selectors(wf_in_session, model_maps, wf_version)
        render_advanced_settings(wf_in_session, wf_version)
        st.divider()
        validation_errors = validate_workflow_models(wf_in_session, model_maps)
        if validation_errors:
            st.error("❌ Problèmes détectés :")
            for error in validation_errors:
                st.write(f"• Modèle manquant : {error['name']} (type: {error['type']})")
            st.info("Corrigez la sélection dans '📦 Modèles du Workflow'")
            generate_disabled = True
        else:
            generate_disabled = False

        if st.button("🚀 LANCER LA GÉNÉRATION", type="primary", use_container_width=True, disabled=generate_disabled):
            try:
                add_generation_job(wf_in_session, model_maps, turbo_mode)
            except Exception as e:
                st.error(f"Erreur lors de l'ajout à la file : {e}")

    # Render the generation queue
    render_generation_queue()
