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
    update_session_title 
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
    try:
        messages = []
        for msg in history[-4:]: 
            if msg['role'] == 'user': messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant': messages.append(AIMessage(content=msg['content']))
        
        prompt = "Génère un titre de 3-4 mots maximum résumant cette conversation médicale ou ce document. Réponds uniquement avec le titre."
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
        history = get_session_history(req.session_id)
        
        # 2. Build Message List
        lc_msgs = []
        lang_instruction = SystemMessage(content=f"IMPORTANT: You must answer strictly in {req.language}. Do not switch languages.")
        lc_msgs.append(lang_instruction)

        for msg in history:
            if msg['role'] == 'user': lc_msgs.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant': lc_msgs.append(AIMessage(content=msg['content']))
            elif msg['role'] == 'system': lc_msgs.append(SystemMessage(content=msg['content']))
        
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
        
        metrics = auditor.audit_text(ai_text)
        save_message_to_session(req.session_id, "assistant", ai_text)
        
        # Auto-Title
        user_ai_msgs = [m for m in history if m['role'] in ['user', 'assistant']]
        if len(user_ai_msgs) >= 3 and len(user_ai_msgs) <= 5: 
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
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        with open(temp_filename, "rb") as f:
            file_bytes = f.read()
            
        images_data, error = process_file_to_images(file_bytes, file.content_type or "application/pdf")
        
        if error: 
            raise HTTPException(status_code=400, detail=error)
            
        full_text = ""
        if images_data:
            for _, _, img_bytes in images_data:
                for chunk in analyze_prescription_stream(img_bytes):
                    full_text += chunk
        
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

        # --- KEYWORD PROMPT ---
        query = (
             f"You are a medical assistant for a {age} year old patient. Language: {language}.\n"
            f"CONTEXT: Raw Text: \"{full_text}\". Structured Data: {json.dumps(meds_data, ensure_ascii=False) if meds_data else 'None'}.\n\n"
            f"TASK 1: Write a clear, reassuring, and educational explanation for the patient about this document. "
            f"Explain the purpose, usage, and precautions. Do NOT include technical details and adapt your structure based on the age of the person.\n\n"
            f"TASK 2: Extract key medical entities into a valid JSON object at the very end.\n"
            f"Categories (Use {language}): 'Médicament', 'Dosage', 'Fréquence', 'Symptôme', 'Type'. or other categories you highlight and think the user should know\n"
            f"If multiple values exist, combine them (e.g. 'Doliprane, Advil').\n\n"
            f"NO INTRODUCTIONS: Do NOT say Hello, I am Doctor X, Here is a response, or As an AI, directly start with the explanation content\n"
            f"REQUIRED OUTPUT FORMAT:\n"
            f"[Your Explanation Here]\n"
            f"||DATA||\n"
            f"{{ \"Category\": \"Value\" }}"
        )
        
        lc_msgs = [HumanMessage(content=query)]
        response = graph.invoke({
            "messages": lc_msgs, 
            "user_profile": {"age":str(age), "language":language, "literacy_level":"Simple"}, 
            "iteration_count":0
        })
        
        raw_response = response["messages"][-1].content
        
        # --- PARSE ---
        explanation = raw_response
        keywords = []
        
        if "||DATA||" in raw_response:
            parts = raw_response.split("||DATA||")
            explanation = parts[0].strip()
            try:
                json_part = parts[1].strip()
                s = json_part.find('{')
                e = json_part.rfind('}') + 1
                if s != -1 and e != -1:
                    json_str = json_part[s:e]
                    data_obj = json.loads(json_str)
                    keywords = [f"{k} : {v}" for k, v in data_obj.items()]
            except Exception as e:
                print(f"Keyword Parsing Error: {e}")
        
        save_message_to_session(session_id, "system", f"Uploaded Document Content: {full_text}")
        save_message_to_session(session_id, "assistant", explanation)
        
        # Title Logic
        history = get_session_history(session_id)
        user_msgs = [m for m in history if m['role'] == 'user']
        if not user_msgs:
            new_title = generate_title(history)
            update_session_title(session_id, new_title)
        
        return {
            "extracted_text": full_text, 
            "meds_data": meds_data, 
            "explanation": explanation,
            "keywords": keywords
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    uvicorn.run("server:app", host="localhost", port=8000, reload=True)