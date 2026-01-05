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
from app.vector_store import (
    create_session, 
    save_message_to_session, 
    get_session_history, 
    delete_session, 
    get_all_sessions
)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()

app = FastAPI()

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

# --- ROUTES ---

@app.get("/")
def read_root():
    from fastapi.responses import FileResponse
    return FileResponse('static/index.html')

@app.post("/api/new_session")
def new_session():
    """Creates a session ID but creates no file entry yet."""
    session_id = create_session()
    return {"session_id": session_id}

@app.get("/api/history")
def get_history():
    """Returns ONLY sessions that have messages."""
    sessions = get_all_sessions()
    
    # Filter: Only keep sessions with > 0 messages
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
    """Deletes ALL conversations."""
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
        IMAGE_INSTRUCTION = "Assess if the users would be able to understand response better with the use of diagrams and trigger them by adding the [Image of X] tag."
        lc_msgs.append(SystemMessage(content=IMAGE_INSTRUCTION))

        for msg in history:
            if msg['role'] == 'user': lc_msgs.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant': lc_msgs.append(AIMessage(content=msg['content']))
            elif msg['role'] == 'system': lc_msgs.append(SystemMessage(content=msg['content']))
            
        # FORCE LANGUAGE: Add explicit instruction at the end
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
        
        # 5. Save AI Response
        save_message_to_session(req.session_id, "assistant", ai_text)
        
        return {"response": ai_text}

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
            
        # Reset file cursor so other functions can read it if needed
        file.file.seek(0)
            
        # 2. Process Image - FIX: Pass the file object directly
        # Because vision.py checks "file.type", we must pass the UploadFile object.
        images_data, error = process_file_to_images(file)
        
        if error: 
            raise HTTPException(status_code=400, detail=error)
            
        # 3. OCR Extraction
        full_text = ""
        if images_data:
            for _, _, img_bytes in images_data:
                for chunk in analyze_prescription_stream(img_bytes):
                    full_text += chunk
        
        # 4. Try to parse JSON for Cards
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

        # 5. AI Explanation
        query = (
            f"Tu es un assistant pédagogique. Voici le contenu brut extrait : {full_text}. "
            f"Données structurées : {json.dumps(meds_data, ensure_ascii=False) if meds_data else 'Aucune'}. "
            f"Explique à un patient de {age} ans ce que c'est (médicaments, fréquence, précautions). "
            f"Réponds en {language}."
        )
        
        lc_msgs = [HumanMessage(content=query)]
        response = graph.invoke({
            "messages": lc_msgs, 
            "user_profile": {"age":str(age), "language":language, "literacy_level":"Simple"}, 
            "iteration_count":0
        })
        explanation = response["messages"][-1].content

        # 6. Save Context
        save_message_to_session(session_id, "system", f"Uploaded Document Content: {full_text}")
        save_message_to_session(session_id, "assistant", explanation)
        
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