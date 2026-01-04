import streamlit as st
import json
import sys
import os
import time
from dotenv import load_dotenv
from langchain_community.callbacks import StreamlitCallbackHandler

# Imports backend
try:
    from app.vision import analyze_prescription_stream, process_file_to_images
    from app.vector_store import log_interaction, get_history
    from app.graph import graph 
except ImportError:
    # Fallback pour éviter les erreurs si les dossiers ne sont pas trouvés localement lors du test
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    try:
        from app.vision import analyze_prescription_stream, process_file_to_images
        from app.vector_store import log_interaction, get_history
        from app.graph import graph
    except ImportError:
        pass # Géré plus bas ou suppose que l'environnement est correct

# --- CONFIGURATION ---
load_dotenv()
st.set_page_config(page_title="Assistant Santé IA", page_icon="⚕️", layout="wide")

# --- INITIALISATION SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "scan_history" not in st.session_state:
    st.session_state.scan_history = []

# --- CSS MODERNE (Conservé et Optimisé) ---
st.markdown("""
<style>
/* =========================
   GLOBAL / BASE
========================= */
.stApp { background: #0f172a; color: #e5e7eb; }
h1 { color: #f9fafb; font-weight: 700; }
h2, h3 { color: #e5e7eb; font-weight: 600; }

/* =========================
   SIDEBAR
========================= */
[data-testid="stSidebar"] { background: #020617; }
[data-testid="stSidebar"] * { color: #e5e7eb !important; }

/* =========================
   TABS
========================= */
.stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #020617; padding: 10px; border-radius: 10px; }
.stTabs [data-baseweb="tab"] { height: 50px; border-radius: 8px; padding: 0 24px; font-size: 16px; font-weight: 500; color: #9ca3af; background: transparent; }
.stTabs [data-baseweb="tab"]:hover { background-color: #1e293b; color: #f9fafb; }
.stTabs [aria-selected="true"] { background: #1e293b; color: #f9fafb !important; }

/* =========================
   CARDS
========================= */
.med-card, .history-card { background: #111827; padding: 20px; border-radius: 12px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.4); }
.med-name { color: #f9fafb; font-size: 18px; font-weight: 600; }
.med-dosage { color: #60a5fa; font-weight: 500; }
.med-posology { color: #9ca3af; font-style: italic; }
.history-timestamp { color: #9ca3af; font-size: 13px; }
.history-user { color: #f9fafb; font-weight: 600; }
.history-ai { background: #020617; padding: 15px; border-radius: 8px; border-left: 3px solid #60a5fa; color: #e5e7eb; }

/* =========================
   CHAT
========================= */
.stChatMessage { background: transparent !important; }
[data-testid="stChatMessageContent"] { background: #111827 !important; border-radius: 12px; padding: 16px; color: #e5e7eb; border: 1px solid #1e293b; }
.stChatInputContainer { background: #020617; border-top: 1px solid #1e293b; padding: 16px; border-radius: 12px; }

/* =========================
   ELEMENTS DIVERS
========================= */
.stButton > button { background: #1e293b; color: #f9fafb; border-radius: 8px; padding: 12px 28px; font-weight: 600; border: none; }
.stButton > button:hover { background: #334155; }
[data-testid="stFileUploader"] { background: #020617; border-radius: 12px; padding: 20px; border: 2px dashed #334155; }
.status-scanning { background: #2563eb; color: white; padding: 6px 12px; border-radius: 6px; }
.status-success { background: #16a34a; color: white; padding: 6px 12px; border-radius: 6px; }
</style>
""", unsafe_allow_html=True)


# --- FONCTION UTILITAIRE FLUIDITÉ ---
def stream_text_generator(text):
    """Simule un effet de streaming pour le texte déjà généré"""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02) # Ajuster la vitesse ici

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2 style='color: white;'>Votre Profil</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: rgba(255,255,255,0.8); font-size: 14px;'>Ces informations aident l'IA à personnaliser ses réponses</p>", unsafe_allow_html=True)
    
    age = st.number_input("Âge", min_value=0, max_value=120, value=30)
    langue = st.selectbox("Langue préférée", ["Français", "Anglais", "Arabe", "Espagnol", "Mandarin"])
    etudes = st.selectbox("Niveau d'études", [
        "Pas d'études / Primaire", "Brevet des collèges", 
        "Baccalauréat / Lycée", "Études Supérieures (Licence/Master)", 
        "Doctorat / Expert Médical"
    ], index=2)
    
    user_profile = {"age": str(age), "langue": langue, "etudes": etudes}

st.title("Assistant Santé Intelligent")

tab_scan, tab_chat, tab_hist = st.tabs(["Scanner Ordonnance", "Discussion & Conseils", "Historique"])

# =========================================================
# 1. SCANNER ORDONNANCE (Code inchangé mais sécurisé)
# =========================================================
with tab_scan:
    st.subheader("Lecture et Explication d'Ordonnance")
    
    uploaded_file = st.file_uploader("Déposez une photo ou un PDF de votre ordonnance", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    start_analysis = False
    
    if uploaded_file:
        if st.button("Lancer l'analyse complète", type="primary"):
            start_analysis = True

        if start_analysis:
            images_data, error = process_file_to_images(uploaded_file)
            
            if error:
                st.error(error)
            elif images_data:
                p_bar = st.progress(0, text="Démarrage de l'analyse...")
                
                for i, (label, img_pil, img_bytes) in enumerate(images_data):
                    st.markdown("---")
                    col_img, col_process = st.columns([1, 2])
                    
                    with col_img:
                        st.image(img_pil, caption=label, use_container_width=True)
                    
                    with col_process:
                        # PHASE 1 : VISION
                        st.markdown("<div class='status-scanning'>Lecture du document en cours</div>", unsafe_allow_html=True)
                        vision_placeholder = st.empty()
                        full_extracted_text = ""
                        
                        for chunk in analyze_prescription_stream(img_bytes):
                            full_extracted_text += chunk
                            vision_placeholder.code(full_extracted_text, language="json")
                        
                        # PHASE 2 : STRUCTURATION
                        meds_found = []
                        try:
                            start = full_extracted_text.find('{')
                            end = full_extracted_text.rfind('}') + 1
                            if start != -1:
                                json_data = json.loads(full_extracted_text[start:end])
                                if "medicaments" in json_data:
                                    meds_found = json_data["medicaments"]
                                    vision_placeholder.empty()
                                    for med in meds_found:
                                        st.markdown(f"""
                                        <div class="med-card">
                                            <div class="med-name">{med.get('nom', '?')}</div>
                                            <div class="med-dosage">{med.get('dosage', '')}</div>
                                            <div class="med-posology">{med.get('posologie', '')}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                        except:
                            st.warning("Lecture difficile, passage en mode texte brut.")

                        # PHASE 3 : ANALYSE IA
                        st.markdown("<div class='status-success'>Lecture terminée - Analyse médicale en cours</div>", unsafe_allow_html=True)
                        
                        if meds_found:
                            context_text = f"Médicaments extraits : {json.dumps(meds_found, ensure_ascii=False)}."
                        else:
                            context_text = f"Texte brut : {full_extracted_text}"
                            
                        query_for_ai = f"{context_text} Explique-moi simplement à quoi servent ces médicaments et s'il y a des précautions, adapte toi à mon profil."

                        with st.spinner("L'IA rédige l'explication..."):
                            inputs = {
                                "user_query": query_for_ai,
                                "user_profile": user_profile,
                                "messages": [("user", query_for_ai)]
                            }
                            # Appel backend
                            response = graph.invoke(inputs, config={"callbacks": []})
                            final_text = response.get("simplified_text") or response.get("final_recommendation")
                            
                            # Affichage résultat
                            st.markdown(f"""
                            <div style='background: white; color: #1e293b; padding: 20px; border-radius: 12px; border-left: 4px solid #667eea;'>
                                {final_text}
                            </div>
                            """, unsafe_allow_html=True)

                            # LOGGING
                            log_interaction(
                                user_input=f"Scan: {label}", 
                                ai_response=f"Extraction: {full_extracted_text} \n\nExplication: {final_text}",
                                source_type="vision"
                            )
                            
                            st.session_state.scan_history.append({
                                "label": label,
                                "meds": meds_found,
                                "explication": final_text
                            })

                    p_bar.progress((i + 1) / len(images_data))
    
    # Historique Scan Persistant
    if st.session_state.scan_history:
        st.markdown("---")
        st.subheader("Résultats de la session actuelle")
        for idx, item in enumerate(reversed(st.session_state.scan_history)):
            with st.expander(f"📄 {item['label']}", expanded=(idx==0)):
                if item['meds']:
                    for med in item['meds']:
                        st.markdown(f"**{med.get('nom')}** - {med.get('dosage')}")
                st.info(item['explication'])
            
            if st.button("Effacer tout", key=f"del_scan"):
                st.session_state.scan_history = []
                st.rerun()


# =========================================================
# 2. CHATBOT (REFAIT POUR FLUIDITÉ & PERSISTANCE)
# =========================================================
with tab_chat:
    st.subheader("Posez vos questions santé")
    
    # 1. Afficher l'historique existant
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 2. Gestion de la nouvelle entrée utilisateur
    if prompt := st.chat_input("Exemple : Qu'est-ce que le diabète de type 2 ?"):
        
        # A. Afficher et sauvegarder le message utilisateur
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # B. Générer la réponse Assistant
        with st.chat_message("assistant"):
            # Placeholder pour éviter le vide pendant le calcul backend
            response_placeholder = st.empty()
            
            with st.spinner("Analyse en cours..."):
                try:
                    inputs = {
                        "user_query": prompt,
                        "user_profile": user_profile,
                        "messages": [("user", prompt)] # Simplifié pour le contexte immédiat
                    }
                    
                    # Appel au Graph (Backend)
                    # Note : Si le backend est lent, le spinner tourne.
                    response = graph.invoke(inputs, config={"callbacks": []})
                    
                    # Récupération de la réponse textuelle
                    if response.get("final_recommendation"):
                        final_answer = response["final_recommendation"]
                    elif response.get("simplified_text"):
                        final_answer = response["simplified_text"]
                    else:
                        final_answer = "Désolé, je n'ai pas pu générer une réponse appropriée."
                    
                    # C. Affichage FLUIDE (Streaming simulé)
                    # On utilise write_stream pour l'effet visuel
                    response_placeholder.write_stream(stream_text_generator(final_answer))
                    
                    # Optionnel : Afficher les métriques de manière discrète
                    metrics = response.get("fairness_metrics", {})
                    if metrics:
                        with st.expander("Détails IA (Toxicité/Complexité)"):
                            c1, c2 = st.columns(2)
                            c1.metric("Complexité", f"{metrics.get('complexity_score', 0):.2f}")
                            c2.metric("Toxicité", f"{metrics.get('toxicity_score', 0):.2f}")

                    # D. SAUVEGARDE CRITIQUE
                    # C'est ici que ça corrige le bug de l'onglet : on ajoute à l'historique 
                    # APRÈS la génération complète.
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})
                    
                    # Logging DB
                    log_interaction(
                        user_input=prompt,
                        ai_response=final_answer,
                        source_type="chat",
                        fairness_score=metrics
                    )

                except Exception as e:
                    st.error(f"Une erreur est survenue : {e}")


# =========================================================
# 3. HISTORIQUE GLOBAL (Base de données)
# =========================================================
with tab_hist:
    st.header("Historique des échanges (Base de données)")
    
    col_refresh, col_void = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Actualiser"):
            st.rerun()

    history_data = get_history()
    
    if not history_data:
        st.info("Aucun historique disponible pour le moment.")
    else:
        for item in reversed(history_data):
            content = item.get('content', '')
            meta = item.get('meta', {})
            timestamp = meta.get('timestamp', '')[:16]
            source = meta.get('source', 'unknown')
            
            # Icone selon la source
            icon = "📷" if source == "vision" else "💬"
            
            # Parsing rudimentaire du contenu stocké
            try:
                parts = content.split("| AI:", 1)
                user_text = parts[0].replace("User:", "").strip()
                ai_text = parts[1].strip() if len(parts) > 1 else "..."
            except:
                user_text = "Données brutes"
                ai_text = content

            st.markdown(f"""
            <div class="history-card">
                <div class="history-timestamp">{icon} {timestamp}</div>
                <div class="history-user">Vous : {user_text}</div>
                <div class="history-ai">
                    {ai_text}
                </div>
            </div>
            """, unsafe_allow_html=True)