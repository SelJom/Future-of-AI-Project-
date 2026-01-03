import streamlit as st
import json
import os
from dotenv import load_dotenv

# --- IMPORTS DE VOTRE APPLICATION ---
# Assurez-vous que ces fichiers existent bien dans votre dossier app/
from app.vision import analyze_prescription, process_file_to_images

# Importez ici votre graph existant. 
# Si votre logique de chat est dans app/graph.py, décommentez la ligne suivante :
# from app.graph import graph 

# --- CONFIGURATION ---
load_dotenv()
st.set_page_config(page_title="Future of AI - Santé", page_icon="🏥", layout="wide")

# --- CSS PERSONNALISÉ (Optionnel) ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px 4px 0 0; gap: 1px; padding-top: 10px; padding-bottom: 10px; }
    .stTabs [aria-selected="true"] { background-color: #ffffff; border-bottom: 2px solid #ff4b4b; }
</style>
""", unsafe_allow_html=True)

# --- TIRE & HEADER ---
st.title("🏥 Assistant Médical & Pharmacien IA")
st.markdown("---")

# --- STRUCTURE EN ONGLETS ---
tab_chat, tab_scan = st.tabs(["💬 Assistant Chat", "💊 Scanner Ordonnance"])

# =========================================================
# ONGLET 1 : VOTRE CHATBOT (LangGraph / RAG)
# =========================================================
with tab_chat:
    st.subheader("Discussion avec l'Assistant")
    
    # -----------------------------------------------------
    # ICI : COLLEZ VOTRE LOGIQUE DE CHAT EXISTANTE
    # -----------------------------------------------------
    
    # Exemple de structure standard Streamlit (à adapter selon votre code actuel)
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Afficher l'historique
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Zone de saisie
    if prompt := st.chat_input("Posez une question sur vos documents..."):
        # 1. Afficher le message utilisateur
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Appeler votre Graph / LLM
        with st.chat_message("assistant"):
            with st.spinner("Réflexion en cours..."):
                # --- REMPLACEZ CECI PAR L'APPEL A VOTRE GRAPH ---
                # response = graph.invoke({"question": prompt})
                # final_answer = response['answer'] 
                
                # Pour le test (si le graph n'est pas encore relié) :
                final_answer = "Ceci est une réponse simulée. Reliez votre 'app.graph' ici."
                # ------------------------------------------------
                
                st.markdown(final_answer)
        
        st.session_state.messages.append({"role": "assistant", "content": final_answer})


# =========================================================
# ONGLET 2 : SCANNER D'ORDONNANCE (Vision Llama 3.2)
# =========================================================
with tab_scan:
    st.subheader("Numérisation et Analyse d'Ordonnance")
    
    col_upload, col_info = st.columns([2, 1])
    
    with col_info:
        st.info("ℹ️ **Modèle actif :** Llama 3.2 Vision\n\nCe module utilise votre carte graphique locale pour lire les ordonnances (PDF ou Photos) et extraire les médicaments au format JSON.")

    with col_upload:
        uploaded_file = st.file_uploader("Déposez votre ordonnance ou photo de médicament", type=['png', 'jpg', 'jpeg', 'pdf'])

    if uploaded_file:
        # Traitement du fichier via le module vision
        images_data, error = process_file_to_images(uploaded_file)
        
        if error:
            st.error(error)
        elif images_data:
            # Bouton d'action
            if st.button("🚀 Lancer l'analyse IA", type="primary"):
                
                # Barre de progression globale
                progress_bar = st.progress(0)
                total_images = len(images_data)
                
                for index, (label, img_pil, img_bytes) in enumerate(images_data):
                    st.markdown("---")
                    c1, c2 = st.columns([1, 1])
                    
                    # Colonne gauche : Image
                    with c1:
                        st.image(img_pil, caption=f"Source : {label}", use_container_width=True)
                    
                    # Colonne droite : Résultat
                    with c2:
                        st.markdown(f"**Analyse de {label}...**")
                        with st.spinner("Lecture des caractères manuscrits..."):
                            raw_result = analyze_prescription(img_bytes)
                            
                            # Nettoyage et affichage du JSON
                            try:
                                # Chercher les accolades JSON dans la réponse du LLM
                                start = raw_result.find('{')
                                end = raw_result.rfind('}') + 1
                                if start != -1 and end != -1:
                                    json_obj = json.loads(raw_result[start:end])
                                    st.success("✅ Lecture terminée")
                                    st.json(json_obj)
                                else:
                                    st.warning("⚠️ Format non structuré détecté")
                                    st.text_area("Résultat brut", raw_result, height=200)
                            except json.JSONDecodeError:
                                st.warning("⚠️ Erreur de parsing JSON")
                                st.text_area("Résultat brut", raw_result, height=200)
                    
                    # Mise à jour de la barre de progression
                    progress_bar.progress((index + 1) / total_images)