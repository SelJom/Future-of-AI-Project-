import streamlit as st
import json
import os
from dotenv import load_dotenv

from app.vision import analyze_prescription, process_file_to_images
from app.graph import graph 

# --- CONFIGURATION ---
load_dotenv()
st.set_page_config(page_title="Future of AI - Santé", page_icon="🏥", layout="wide")

# Custom CSS for a professional look
st.markdown("""
<style>
    .stChatInput {border-radius: 20px;}
    .stStatus {border-radius: 10px;}
    div[data-testid="stExpander"] {background-color: #f9f9f9; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: SETTINGS & DEV MODE ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063822.png", width=80)
    st.title("Profil Patient")
    
    # 1. Inclusivity Settings
    user_age = st.slider("Âge du patient", min_value=5, max_value=100, value=30)
    literacy_mode = st.select_slider(
        "Niveau de compréhension", 
        options=["Enfant", "Adolescent", "Adulte", "Senior", "Expert Médical"],
        value="Adulte"
    )
    
    st.divider()
    
    # 2. Developer Mode
    st.subheader("Zone Technique")
    dev_mode = st.toggle("🛠️ Mode Développeur", value=False)
    if dev_mode:
        st.info("Le mode développeur affiche les logs bruts, les JSON et les étapes des agents.")

# --- MAIN LAYOUT ---
st.title("🏥 Assistant de Santé IA")

# Initialization of Session State
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Bonjour ! Je suis votre assistant médical. Vous pouvez scanner une ordonnance ou me poser des questions de santé."}
    ]
if "document_context" not in st.session_state:
    st.session_state.document_context = ""

# Tabs
tab_chat, tab_scan = st.tabs(["💬 Discussion", "📷 Scanner & Analyse"])

# =========================================================
# TAB 1: DISCUSSION (Chatbot)
# =========================================================
with tab_chat:
    # Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Posez votre question ici..."):
        
        # 1. User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Assistant Response
        with st.chat_message("assistant"):
            
            # VISUALIZATION: Agent Communication
            # We use st.status to show the "Thinking" process professionally
            status_text = "Analyse en cours..."
            if dev_mode:
                status_text = "Router -> Agent de Simplification -> Critique..."
                
            with st.status(status_text, expanded=dev_mode) as status:
                try:
                    # Invoke Graph with User Profile & Document Context
                    response_state = graph.invoke({
                        "user_query": prompt,
                        "user_age": user_age,
                        "literacy_level": literacy_mode,
                        "active_document_context": st.session_state.document_context
                    })
                    
                    if dev_mode:
                        st.write("🔧 **Debug Graph State:**")
                        st.json(response_state)
                    
                    status.update(label="Réponse générée !", state="complete", expanded=False)
                    
                    # 3. Format Answer
                    final_answer = ""
                    
                    # Case A: Clinical Match
                    if response_state.get("final_recommendation"):
                        final_answer = response_state['final_recommendation']
                    
                    # Case B: Literacy/Explanation
                    elif response_state.get("simplified_text"):
                        final_answer = response_state['simplified_text']
                        
                        # Add Fairness/Critique details (Only in Dev Mode or if critical)
                        if dev_mode and response_state.get("literacy_critique"):
                            with st.expander("🧐 Critique Médicale (Interne)"):
                                st.write(response_state['literacy_critique'])
                                st.metric("Toxicité", response_state['fairness_metrics'].get('toxicity_score', 0))

                    else:
                        final_answer = "Je n'ai pas pu générer de réponse. Veuillez reformuler."

                    st.markdown(final_answer)
                    st.session_state.messages.append({"role": "assistant", "content": final_answer})

                except Exception as e:
                    st.error("Une erreur est survenue.")
                    if dev_mode:
                        st.error(f"Details: {e}")

# =========================================================
# TAB 2: SCANNER (Vision)
# =========================================================
with tab_scan:
    col_up, col_desc = st.columns([2, 1])
    with col_desc:
        st.info("Importez une ordonnance (PDF/Photo). L'IA va l'analyser et l'ajouter à la conversation.")

    uploaded_file = st.file_uploader("Fichier", type=['png', 'jpg', 'jpeg', 'pdf'], label_visibility="collapsed")

    if uploaded_file:
        images_data, error = process_file_to_images(uploaded_file)
        
        if error:
            st.error(error)
        elif images_data:
            if st.button("🚀 Analyser et Discuter", type="primary"):
                
                full_extraction = []
                progress = st.progress(0)
                
                for i, (label, img_pil, img_bytes) in enumerate(images_data):
                    st.image(img_pil, caption=label, width=300)
                    
                    with st.spinner(f"Lecture de {label}..."):
                        raw_result = analyze_prescription(img_bytes)
                        full_extraction.append(raw_result)
                    
                    progress.progress((i + 1) / len(images_data))
                
                # --- INTEGRATION LOGIC ---
                # Combine all extracted pages into one context string
                combined_context = "\n".join(full_extraction)
                st.session_state.document_context = combined_context
                
                # Add a system notification to chat
                sys_msg = "📄 **Document Analysé.** Je l'ai lu. Vous pouvez maintenant me poser des questions (effets secondaires, posologie, etc.)."
                st.session_state.messages.append({"role": "assistant", "content": sys_msg})
                
                st.success("Analyse terminée ! Allez dans l'onglet 'Discussion' pour poser vos questions.")
                
                if dev_mode:
                    with st.expander("Voir le JSON brut extrait"):
                        st.text(combined_context)