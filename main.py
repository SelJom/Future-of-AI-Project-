import streamlit as st
import json
import sys
import os
import time
from dotenv import load_dotenv
import streamlit.components.v1 as components

# --- NEW IMPORTS FOR MESSAGE CONVERSION ---
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# --- BACKEND IMPORTS ---
try:
    from app.vision import analyze_prescription_stream, process_file_to_images
    from app.graph import graph 
    from app.config import Config
    from app.vector_store import (
        get_all_sessions, 
        create_session, 
        save_message_to_session, 
        get_session_history,
        delete_session,       
        update_session_title  
    )
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from app.vision import analyze_prescription_stream, process_file_to_images
    from app.graph import graph
    from app.config import Config
    from app.vector_store import (
        get_all_sessions, 
        create_session, 
        save_message_to_session, 
        get_session_history,
        delete_session, 
        update_session_title
    )

# --- CONFIGURATION ---
load_dotenv()
st.set_page_config(page_title="Assistant Santé IA", page_icon="⚕️", layout="wide")

# --- HELPER: SCROLL TO BOTTOM JS ---
def scroll_to_bottom():
    js = f"""
    <script>
    function scroll() {{
        var chatBox = window.parent.document.querySelector('.chat-body');
        if (chatBox) {{
            chatBox.scrollTop = chatBox.scrollHeight;
        }}
    }}
    scroll();
    setTimeout(scroll, 100); 
    </script>
    """
    components.html(js, height=0, width=0)

# --- INITIALISATION SESSION STATE ---
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = create_session()

if "scan_history" not in st.session_state:
    st.session_state.scan_history = []

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Discuter"

# --- HELPER: GENERATE TITLE ---
def generate_chat_title(messages):
    try:
        lc_msgs = []
        for m in messages:
            if m["role"] == "user": lc_msgs.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant": lc_msgs.append(AIMessage(content=m["content"]))
        
        lc_msgs.append(HumanMessage(content="Génère un titre de 3 mots maximum résumant notre conversation. Réponds uniquement avec le titre."))
        
        inputs = {
            "messages": lc_msgs,
            "language": "Français",
            "complexity_prompt": "Simple"
        }
        response = graph.invoke(inputs)
        new_title = response["messages"][-1].content.strip().replace('"', '').replace("'", "")
        return new_title if len(new_title) < 50 else new_title[:50]
    except:
        return "Conversation Médicale"

# --- CSS ---
st.markdown("""
<style>
/* =========================
   VARIABLES & COLORS
========================= */
:root {
    --chat-width: 700px;
    --page-bg: #0f172a;
    --card-bg: #020617;
    --text-body: #e2e8f0;
    --text-chat: #1e293b;
    --primary: #3b82f6; 
    --chat-surface: #020617;
    --bot-bg: #1e293b;
}

/* =========================
   GLOBAL RESET
========================= */
.stApp {
    background-color: var(--page-bg);
    color: var(--text-body);
}

/* Remove default Streamlit padding */
.block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

h1, h2, h3, p, span, label {
    color: var(--text-body);
}

/* =========================
   TABS WITH SMOOTH TRANSITIONS
========================= */
.stTabs [data-baseweb="tab-list"] { 
    display:flex; 
    width:100%; 
    gap:8px; 
    background-color:#020617; 
    padding:10px; 
    border-radius:10px; 
}

.stTabs [data-baseweb="tab"] { 
    flex:1 1 0; 
    height:50px; 
    border-radius:8px; 
    padding:0; 
    font-size:16px; 
    font-weight:500; 
    color:#9ca3af; 
    background:transparent; 
    display:flex; 
    align-items:center; 
    justify-content:center; 
    transition: all 0.3s ease;
}

.stTabs [data-baseweb="tab"]:hover { 
    background-color:#1e293b; 
    color:#f9fafb; 
}

.stTabs [aria-selected="true"] { 
    background:#1e293b; 
    color:#f9fafb!important; 
}

/* Smooth tab content transitions */
.stTabs [data-baseweb="tab-panel"] {
    animation: fadeIn 0.4s ease-in-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* =========================
   MEDICAL CARDS
========================= */
.med-card { 
    background: #1e293b; 
    padding: 15px; 
    border-radius: 12px; 
    margin-bottom: 10px; 
    border: 1px solid #334155;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}
.med-name { color: #f8fafc; font-size: 16px; font-weight: 700; }
.med-dosage { color: #60a5fa; font-weight: 600; font-size: 14px; }
.med-posology { color: #94a3b8; font-style: italic; font-size: 13px; }

.status-box { 
    padding: 8px 16px; 
    border-radius: 6px; 
    font-size: 14px; 
    font-weight: 500;
    margin-bottom: 15px;
    display: inline-block;
}
.status-scanning { background: #2563eb; color: white; }
.status-analyzing { background: #8b5cf6; color: white; }

/* =========================
   CHAT CARD (The Chat Box)
========================= */
.chat-container {
    width: 100%;
    max-width: var(--chat-width);
    height: 65vh;
    margin: 0 auto;
    margin-top: 20px;
    margin-bottom: 100px;
    background-color: var(--card-bg);
    border-radius: 12px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #334155;
}

.chat-header {
    background-color: #f8fafc;
    padding: 15px 20px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
}

.chat-header h3 {
    color: var(--text-chat) !important;
    margin: 0;
    font-size: 18px;
    font-weight: 600;
}

.chat-header span {
    color: #64748b !important;
    font-size: 12px;
}

.chat-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 15px;
    background-color: var(--chat-surface);
}

.chat-body::-webkit-scrollbar { width: 8px; }
.chat-body::-webkit-scrollbar-track { background: #020617; }
.chat-body::-webkit-scrollbar-thumb { background: #475569; border-radius: 4px; }
.chat-body::-webkit-scrollbar-thumb:hover { background: #64748b; }

.empty-state {
    text-align: center;
    color: #94a3b8;
    margin-top: 50px;
    font-size: 16px;
}

/* =========================
   MESSAGES
========================= */
.message-row {
    display: flex;
    width: 100%;
}

.row-user { justify-content: flex-end; }
.row-bot { justify-content: flex-start; }

.message-bubble {
    max-width: 80%;
    padding: 10px 16px;
    border-radius: 18px;
    font-size: 15px;
    line-height: 1.5;
    word-wrap: break-word;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.user-bubble {
    background-color: var(--primary);
    color: white !important;
    border-bottom-right-radius: 2px;
}

.bot-bubble {
    background-color: var(--bot-bg);
    color: #e2e8f0 !important;
    border: 1px solid #334155;
    border-bottom-left-radius: 2px;
}

.thinking-bubble {
    background-color: #1e293b;
    color: #94a3b8 !important;
    font-style: italic;
    border: 1px solid #334155;
    border-bottom-left-radius: 2px;
    animation: pulse 1.5s infinite ease-in-out;
}

@keyframes pulse {
    0% { opacity: 0.6; }
    50% { opacity: 1; }
    100% { opacity: 0.6; }
}

/* =========================
   INPUT FIELD (FIXED & DARK) - NO SCROLLBAR
========================= */
[data-testid="stBottom"] {
    background-color: transparent;
    pointer-events: none;
}

[data-testid="stChatInput"] {
    pointer-events: auto;
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%);
    width: 100% !important;
    max-width: var(--chat-width) !important;
    z-index: 9999;
}

/* Adjust input position when sidebar is open */
@media (min-width: 769px) {
    .stApp[data-testid="stApp"]:has([data-testid="stSidebar"][aria-expanded="true"]) [data-testid="stChatInput"] {
        left: calc(50% + 168px);
    }
}

[data-testid="stChatInput"] textarea {
    background-color: #1e293b !important;
    color: #e2e8f0 !important;
    border: 1px solid #334155 !important;
    border-radius: 12px !important;
    padding: 12px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
    resize: none !important;
    overflow: hidden !important;
    overflow-y: hidden !important;
    overflow-x: hidden !important;
    max-height: 100px !important;
    min-height: 45px !important;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.5);
}

[data-testid="stChatInput"] textarea::placeholder {
    color: #64748b !important;
}

/* Remove scrollbar from input */
[data-testid="stChatInput"] textarea::-webkit-scrollbar {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
}

[data-testid="stChatInput"] textarea {
    -ms-overflow-style: none !important;
    scrollbar-width: none !important;
}

/* Mobile Responsiveness */
@media (max-width: 768px) {
    :root { --chat-width: 95%; }
    
    [data-testid="stChatInput"] {
        left: 50% !important;
    }
}

/* SIDEBAR BUTTON FIX */
div[data-testid="stButton"] button p {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h2>🧠 MediMind</h2>", unsafe_allow_html=True)
    
    if st.button("➕ Nouvelle Discussion", type="primary", use_container_width=True):
        st.session_state.current_session_id = create_session()
        st.session_state.active_tab = "Discuter"
        st.rerun()
    
    st.divider()

    with st.expander("👤 Profil Patient", expanded=False):
        age = st.number_input("Âge", min_value=0, max_value=120, value=30)
        langue = st.selectbox("Langue préférée", ["Français", "English", "Arabe", "Espagnol"], index=0)
        etudes = st.selectbox("Niveau", ["Simple", "Intermédiaire", "Expert"], index=1)
        
        complexity_prompt = Config.COMPLEXITY_LEVELS.get(etudes, "Explique simplement")

    st.divider()
    
    st.subheader("Historique")
    sessions = get_all_sessions()
    sorted_ids = sorted(sessions.keys(), key=lambda k: sessions[k].get('timestamp', 0), reverse=True)
    
    with st.container(height=400):
        for sid in sorted_ids:
            s_data = sessions[sid]
            if not s_data.get('history'): continue
            title = s_data.get('title', 'Nouvelle conversation')
            
            c1, c2 = st.columns([0.85, 0.15])
            with c1:
                b_type = "primary" if sid == st.session_state.current_session_id else "secondary"
                if st.button(title, key=f"btn_{sid}", type=b_type, help=title, use_container_width=True):
                    st.session_state.current_session_id = sid
                    st.session_state.active_tab = "Discuter"  # Switch to chat tab
                    st.rerun()
            with c2:
                with st.popover("⋮", use_container_width=True):
                    if st.button("🗑️ Supprimer la conversation", key=f"del_{sid}"):
                        delete_session(sid)
                        if st.session_state.current_session_id == sid:
                            st.session_state.current_session_id = create_session()
                        st.rerun()

# --- MAIN LOGIC ---
st.title("Assistant Santé")

# Create tabs with controlled selection
tab_labels = ["Scanner une ordonnace", "Discuter"]
default_index = 1 if st.session_state.active_tab == "Discuter" else 0

tab_scan, tab_chat = st.tabs(tab_labels)

# --- TAB 1: SCANNER ---
with tab_scan:
    # Update active tab when this tab is viewed
    st.session_state.active_tab = "Scanner une ordonnace"
    
    st.subheader("Lecture et Explication d'Ordonnance")
    uploaded_file = st.file_uploader("Image ou PDF", type=['png', 'jpg', 'jpeg', 'pdf'])
    
    start_analysis = False
    
    if uploaded_file:
        if st.button("Lancer l'analyse complète", type="primary"):
            start_analysis = True

        if start_analysis:
            images_data, error = process_file_to_images(uploaded_file)
            
            if error:
                st.error(error)
            elif images_data:
                p_bar = st.progress(0, text="Démarrage...")
                
                full_session_context = []

                for i, (label, img_pil, img_bytes) in enumerate(images_data):
                    st.markdown("---")
                    col_img, col_process = st.columns([1, 2])
                    
                    with col_img:
                        st.image(img_pil, caption=label, use_container_width=True)
                    
                    with col_process:
                        status_placeholder = st.empty()

                        status_placeholder.markdown("<div class='status-box status-scanning'>Lecture du document en cours...</div>", unsafe_allow_html=True)
                        
                        full_extracted_text = ""
                        for chunk in analyze_prescription_stream(img_bytes):
                            full_extracted_text += chunk
                        
                        full_session_context.append(full_extracted_text)

                        meds_found = []
                        try:
                            start = full_extracted_text.find('{')
                            end = full_extracted_text.rfind('}') + 1
                            if start != -1:
                                json_data = json.loads(full_extracted_text[start:end])
                                if "medicaments" in json_data:
                                    meds_found = json_data["medicaments"]
                                    
                                    for med in meds_found:
                                        st.markdown(f"""
                                        <div class="med-card">
                                            <div class="med-name">{med.get('nom', '?')}</div>
                                            <div class="med-dosage">{med.get('dosage', '')}</div>
                                            <div class="med-posology">{med.get('posologie', '')}</div>
                                        </div>
                                        """, unsafe_allow_html=True)
                        except:
                            st.warning("Mode texte brut (Format non reconnu)")

                        status_placeholder.markdown("<div class='status-box status-analyzing'>Analyse médicale en cours...</div>", unsafe_allow_html=True)
                        
                        if meds_found:
                            context_text = f"Liste des médicaments extraits : {json.dumps(meds_found, ensure_ascii=False)}."
                        else:
                            context_text = f"Texte brut extrait : {full_extracted_text}"
                        
                        query_for_ai = (
                            f"Tu es un assistant pédagogique. Voici le contenu brut extrait d'une ordonnance : {context_text}. "
                            f"Ton objectif est d'expliquer au patient à quoi servent ces médicaments de manière générale et éducative. "
                            f"Ne fais pas de diagnostic. Adresse-toi à un patient de {age} ans. "
                            f"Réponds en {langue}."
                        )

                        with st.spinner("Rédaction de l'explication..."):
                            lc_msgs = [HumanMessage(content=query_for_ai)]
                            
                            inputs = {
                                "messages": lc_msgs,
                                "language": langue,
                                "complexity_prompt": complexity_prompt
                            }
                            
                            response = graph.invoke(inputs)
                            final_text = response["messages"][-1].content
                            
                            st.markdown(f"""
                            <div style='background: #1e293b; color: #e2e8f0; padding: 20px; border-radius: 12px; border-left: 4px solid #3b82f6;'>
                                {final_text}
                            </div>
                            """, unsafe_allow_html=True)

                            save_message_to_session(st.session_state.current_session_id, "system", f"Analyse Document: {context_text}")
                            save_message_to_session(st.session_state.current_session_id, "assistant", f"Explication automatique: {final_text}")

                        status_placeholder.empty()

                    p_bar.progress((i + 1) / len(images_data))
                
                st.success("Analyse terminée ! Retrouvez le contexte dans l'onglet Discussion.")

# --- TAB 2: CHAT ---
with tab_chat:
    # Update active tab when this tab is viewed
    st.session_state.active_tab = "Discuter"
    
    current_history = get_session_history(st.session_state.current_session_id)

    # Start the chat container
    st.markdown('''
    <div class="chat-container">
        <div class="chat-header">
            <h3>Assistant</h3>
            <span>(Active)</span>
        </div>
        <div class="chat-body">
    ''', unsafe_allow_html=True)

    if not current_history:
        st.markdown('<div class="empty-state">👋 Ready to help!</div>', unsafe_allow_html=True)
    else:
        for msg in current_history:
            if msg["role"] == "system":
                continue
            
            if msg["role"] == "user":
                st.markdown(f'''
                <div class="message-row row-user">
                    <div class="message-bubble user-bubble">{msg["content"]}</div>
                </div>
                ''', unsafe_allow_html=True)
            elif msg["role"] == "assistant":
                st.markdown(f'''
                <div class="message-row row-bot">
                    <div class="message-bubble bot-bubble">{msg["content"]}</div>
                </div>
                ''', unsafe_allow_html=True)
        
        # Show thinking bubble if last message is from user
        if current_history[-1]["role"] == "user":
            st.markdown('''
            <div class="message-row row-bot">
                <div class="message-bubble thinking-bubble">Le modèle réfléchit...</div>
            </div>
            ''', unsafe_allow_html=True)

    # Close container
    st.markdown('''
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    scroll_to_bottom()

    # --- USER INPUT ---
    if prompt := st.chat_input("Posez votre question..."):
        save_message_to_session(st.session_state.current_session_id, "user", prompt)
        st.rerun()

    # --- PROCESS AI RESPONSE ---
    if current_history and current_history[-1]["role"] == "user":
        try:
            lc_msgs = []
            for m in current_history:
                if m["role"] == "user":
                    lc_msgs.append(HumanMessage(content=m["content"]))
                elif m["role"] == "assistant":
                    lc_msgs.append(AIMessage(content=m["content"]))
                elif m["role"] == "system":
                    lc_msgs.append(SystemMessage(content=m["content"]))

            inputs = {
                "messages": lc_msgs,
                "language": langue,
                "complexity_prompt": complexity_prompt
            }

            response = graph.invoke(inputs)
            ai_msg_content = response["messages"][-1].content

            save_message_to_session(st.session_state.current_session_id, "assistant", ai_msg_content)

            if len(current_history) < 5:
                upd_history = get_session_history(st.session_state.current_session_id)
                new_t = generate_chat_title(upd_history)
                update_session_title(st.session_state.current_session_id, new_t)

            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")