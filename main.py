import streamlit as st
import json
import os
from dotenv import load_dotenv

# --- IMPORTS ---
from app.vision import analyze_prescription, process_file_to_images
# 1. UNCOMMENTED THE GRAPH IMPORT
from app.graph import graph 

# --- CONFIGURATION ---
load_dotenv()
st.set_page_config(page_title="Future of AI - Santé", page_icon="🏥", layout="wide")

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: #f0f2f6; border-radius: 4px; padding: 10px; }
    .stTabs [aria-selected="true"] { background-color: #ffffff; border-bottom: 2px solid #ff4b4b; }
</style>
""", unsafe_allow_html=True)

st.title("🏥 Assistant Médical & Pharmacien IA")
st.markdown("---")

tab_chat, tab_scan = st.tabs(["💬 Assistant Chat", "💊 Scanner Ordonnance"])

# =========================================================
# TAB 1: CHATBOT (Connected to LangGraph)
# =========================================================
with tab_chat:
    st.subheader("Discussion avec l'Assistant")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Posez une question (ex: 'C'est quoi le Doliprane ?' ou 'Essais cliniques diabète')"):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours (Router -> Agents)..."):
                try:
                    # 2. INVOKE THE GRAPH
                    response_state = graph.invoke({"user_query": prompt})
                    
                    # 3. EXTRACT THE RIGHT ANSWER BASED ON AGENT PATH
                    # Your graph has two paths: 'Literacy' (Simplifier) and 'Matching' (Matcher)
                    final_answer = ""
                    
                    if response_state.get("final_recommendation"):
                        # Case: Clinical Trial Matcher
                        final_answer = f"**Résultat Recherche Clinique :**\n\n{response_state['final_recommendation']}"
                    
                    elif response_state.get("simplified_text"):
                        # Case: Health Literacy (Simplification)
                        final_answer = f"**Explication Simplifiée :**\n\n{response_state['simplified_text']}"
                        
                        # Add Critique/Fairness if available
                        if response_state.get("literacy_critique"):
                            final_answer += f"\n\n---\n*Note Critique Médicale : {response_state['literacy_critique']}*"
                        
                        if response_state.get("fairness_metrics"):
                            tox = response_state['fairness_metrics'].get('toxicity_score', 0)
                            final_answer += f"\n*Score Toxicité : {tox}/10*"

                    else:
                        final_answer = "Désolé, je n'ai pas pu générer de réponse (Erreur de Graph)."

                    st.markdown(final_answer)
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})

                except Exception as e:
                    error_msg = f"Erreur système : {str(e)}"
                    st.error(error_msg)

# =========================================================
# TAB 2: VISION SCANNER (Llama 3.2 Vision)
# =========================================================
with tab_scan:
    st.subheader("Numérisation et Analyse d'Ordonnance")
    
    col_upload, col_info = st.columns([2, 1])
    with col_info:
        st.info("ℹ️ **Modèle actif :** Llama 3.2 Vision\n\nAnalyse locale sur GPU (RTX 5070 Ti).")

    uploaded_file = st.file_uploader("Déposez votre ordonnance", type=['png', 'jpg', 'jpeg', 'pdf'])

    if uploaded_file:
        images_data, error = process_file_to_images(uploaded_file)
        
        if error:
            st.error(error)
        elif images_data:
            if st.button("🚀 Analyser le document", type="primary"):
                progress_bar = st.progress(0)
                
                for index, (label, img_pil, img_bytes) in enumerate(images_data):
                    st.markdown("---")
                    c1, c2 = st.columns([1, 1])
                    
                    with c1:
                        st.image(img_pil, caption=label, use_container_width=True)
                    
                    with c2:
                        with st.spinner(f"Lecture de {label}..."):
                            raw_result = analyze_prescription(img_bytes)
                            try:
                                start = raw_result.find('{')
                                end = raw_result.rfind('}') + 1
                                if start != -1 and end != -1:
                                    json_obj = json.loads(raw_result[start:end])
                                    st.success("✅ Données Extraites")
                                    st.json(json_obj)
                                else:
                                    st.warning("⚠️ Résultat brut (JSON introuvable)")
                                    st.write(raw_result)
                            except:
                                st.warning("⚠️ Erreur de formatage")
                                st.write(raw_result)
                    progress_bar.progress((index + 1) / len(images_data))