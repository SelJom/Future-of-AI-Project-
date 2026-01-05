import os
import shutil
import json
import uvicorn
import traceback
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# --- INTERNAL IMPORTS ---
from app.vision import analyze_prescription_stream, process_file_to_images
from app.graph import graph
from app.config import Config
from app.fairness import FairnessAuditor
from app.llm import get_llm
from app.vector_store import (
    create_session, 
    save_message_to_session, 
    get_session_history, 
    delete_session, 
    get_all_sessions,
    update_session_title # Ensure this is in vector_store.py
)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()

app = FastAPI()
auditor = FairnessAuditor()
llm = get_llm()

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    session_id: str
    message: str
    age: int
    language: str
    literacy_level: str

# --- HELPER: TITLE GENERATION ---
def generate_title(history):
    """Generates a short 3-word title based on the conversation."""
    try:
        # Prepare context
        messages = []
        for msg in history[-4:]: # Use last few messages
            if msg['role'] == 'user': messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant': messages.append(AIMessage(content=msg['content']))
        
        prompt = "Génère un titre de 3-4 mots maximum résumant cette conversation médicale. Réponds uniquement avec le titre. Pour que l'utilisateur se souvienne de la conversation"
        messages.append(HumanMessage(content=prompt))
        
        response = llm.invoke(messages)
        title = response.content.strip().replace('"', '').replace("'", "")
        return title if len(title) < 50 else title[:50]
    except Exception as e:
        print(f"Title Gen Error: {e}")
        return "Conversation Médicale"

# --- ROUTES ---

@app.get("/")
def read_root():
    from fastapi.responses import FileResponse
    return FileResponse('static/index.html')

@app.post("/api/new_session")
def new_session():
    session_id = create_session()
    return {"session_id": session_id}

@app.get("/api/history")
def get_history():
    sessions = get_all_sessions()
    valid_sessions = []
    for k, v in sessions.items():
        if v.get("history") and len(v["history"]) > 0:
            valid_sessions.append({
                "id": k, 
                "title": v.get("title", "Nouvelle conversation"), 
                "timestamp": v.get("timestamp", "")
            })
    sorted_sessions = sorted(valid_sessions, key=lambda x: x['timestamp'], reverse=True)
    return sorted_sessions

@app.get("/api/messages/{session_id}")
def get_messages(session_id: str):
    history = get_session_history(session_id)
    return [msg for msg in history if msg['role'] != 'system']

@app.delete("/api/session/{session_id}")
def remove_session(session_id: str):
    delete_session(session_id)
    return {"status": "deleted"}

@app.delete("/api/delete_all_sessions")
def delete_all_history():
    try:
        sessions = get_all_sessions()
        ids = list(sessions.keys())
        for sid in ids:
            delete_session(sid)
        return {"status": "all_deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    try:
        # 1. Save User Message
        save_message_to_session(req.session_id, "user", req.message)
        
        # 2. Get History
        history = get_session_history(req.session_id)
        
        # 3. LangChain Format
        lc_msgs = []
        for msg in history:
            if msg['role'] == 'user': lc_msgs.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant': lc_msgs.append(AIMessage(content=msg['content']))
            elif msg['role'] == 'system': lc_msgs.append(SystemMessage(content=msg['content']))
            
        lang_instruction = SystemMessage(content=f"IMPORTANT: You must answer strictly in {req.language}. Do not switch languages.")
        lc_msgs.append(lang_instruction)
        
        # 4. Invoke Graph
        user_profile = {
            "age": str(req.age),
            "language": req.language,
            "literacy_level": req.literacy_level,
            "context": "Patient using Health App"
        }
        
        inputs = {
            "messages": lc_msgs,
            "user_profile": user_profile,
            "iteration_count": 0,
            "critique_feedback": ""
        }
        
        response = graph.invoke(inputs)
        ai_text = response["messages"][-1].content
        
        # Audit
        metrics = auditor.audit_text(ai_text)
        
        # 5. Save AI Response
        save_message_to_session(req.session_id, "assistant", ai_text)
        
        # 6. --- AUTO-TITLE GENERATION ---
        # Check if we have roughly 2 exchanges (User + AI + User + AI = 4 messages)
        # We count messages excluding system ones to be safe
        user_ai_msgs = [m for m in history if m['role'] in ['user', 'assistant']]
        # Add the one we just generated
        if len(user_ai_msgs) >= 3 and len(user_ai_msgs) <= 5: 
             # Update title asynchronously (conceptually)
             new_title = generate_title(get_session_history(req.session_id))
             update_session_title(req.session_id, new_title)
        
        return {"response": ai_text, "fairness_metrics": metrics}

    except Exception as e:
        print(f"Chat Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...), 
    session_id: str = Form(...),
    age: int = Form(...),
    language: str = Form(...)
):
    temp_filename = f"temp_{file.filename}"
    try:
        # 1. Save temp file
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Read File Bytes
        with open(temp_filename, "rb") as f:
            file_bytes = f.read()
            
        # 3. Process Image
        images_data, error = process_file_to_images(file_bytes, file.content_type or "application/pdf")
        
        if error: 
            raise HTTPException(status_code=400, detail=error)
            
        # 4. OCR Extraction
        full_text = ""
        if images_data:
            for _, _, img_bytes in images_data:
                for chunk in analyze_prescription_stream(img_bytes):
                    full_text += chunk
        
        # 5. Try to parse JSON for Cards
        meds_data = []
        try:
            start = full_text.find('{')
            end = full_text.rfind('}') + 1
            if start != -1:
                json_str = full_text[start:end]
                parsed = json.loads(json_str)
                if "medicaments" in parsed:
                    meds_data = parsed["medicaments"]
        except Exception:
            pass 

        # 6. AI Explanation
        query = (
            f"You are a pedagogical assistant. Here is raw extracted medical text: {full_text}. "
            f"Structured data found: {json.dumps(meds_data, ensure_ascii=False) if meds_data else 'None'}. "
            f"Explain to a {age} year old patient what this is (meds, frequency, precautions). "
            f"Answer in {language}."
        )
        
        lc_msgs = [HumanMessage(content=query)]
        response = graph.invoke({
            "messages": lc_msgs, 
            "user_profile": {"age":str(age), "language":language, "literacy_level":"Simple"}, 
            "iteration_count":0
        })
        explanation = response["messages"][-1].content

        # 7. Save Context to Session
        save_message_to_session(session_id, "system", f"Uploaded Document Content: {full_text}")
        save_message_to_session(session_id, "assistant", explanation)
        
        # Generate title if it's the first interaction
        update_session_title(session_id, "Analyse Document")
        
        return {
            "extracted_text": full_text, 
            "meds_data": meds_data, 
            "explanation": explanation
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    uvicorn.run("server:app", host="localhost", port=8000, reload=True)