import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Import your existing backend logic
# Ensure the 'app' folder is in the same directory
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

# Mount the static folder to serve HTML/CSS/JS
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- DATA MODELS ---
class ChatRequest(BaseModel):
    session_id: str
    message: str
    age: int
    language: str
    literacy_level: str

# --- ROUTES ---

@app.get("/")
def read_root():
    """Serve the main page."""
    from fastapi.responses import FileResponse
    return FileResponse('static/index.html')

@app.post("/api/new_session")
def new_session():
    """Create a new chat session."""
    session_id = create_session()
    return {"session_id": session_id}

@app.get("/api/history")
def get_history():
    """Get all sessions for the sidebar."""
    sessions = get_all_sessions()
    # Sort by timestamp (newest first)
    sorted_sessions = sorted(
        [{"id": k, "title": v.get("title", "Nouvelle conversation"), "timestamp": v.get("timestamp", 0)} 
         for k, v in sessions.items()],
        key=lambda x: x['timestamp'], 
        reverse=True
    )
    return sorted_sessions

@app.get("/api/messages/{session_id}")
def get_messages(session_id: str):
    """Get message history for a specific session."""
    history = get_session_history(session_id)
    # Filter out system messages for the UI if desired
    return [msg for msg in history if msg['role'] != 'system']

@app.delete("/api/session/{session_id}")
def remove_session(session_id: str):
    delete_session(session_id)
    return {"status": "deleted"}

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    """Handle text chat interaction."""
    try:
        # 1. Save User Message
        save_message_to_session(req.session_id, "user", req.message)
        
        # 2. Get History
        history = get_session_history(req.session_id)
        
        # 3. Convert to LangChain format
        lc_msgs = []
        # Add Image Trigger Instruction
        IMAGE_INSTRUCTION = "Assess if the users would be able to understand response better with the use of diagrams and trigger them by adding the [Image of X] tag."
        lc_msgs.append(SystemMessage(content=IMAGE_INSTRUCTION))

        for msg in history:
            if msg['role'] == 'user': lc_msgs.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant': lc_msgs.append(AIMessage(content=msg['content']))
            elif msg['role'] == 'system': lc_msgs.append(SystemMessage(content=msg['content']))
            
        # 4. Prepare Context
        complexity = Config.COMPLEXITY_LEVELS.get(req.literacy_level, "Simple")
        
        inputs = {
            "messages": lc_msgs,
            "language": req.language,
            "complexity_prompt": complexity
        }
        
        # 5. Run Graph
        response = graph.invoke(inputs)
        ai_text = response["messages"][-1].content
        
        # 6. Save AI Message
        save_message_to_session(req.session_id, "assistant", ai_text)
        
        return {"response": ai_text}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...), 
    session_id: str = Form(...),
    age: int = Form(...),
    language: str = Form(...)
):
    """Handle image upload and OCR."""
    temp_filename = f"temp_{file.filename}"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process Image (Reusing your backend logic)
        images_data, error = process_file_to_images(temp_filename)
        
        if error:
            raise HTTPException(status_code=400, detail=error)
            
        # OCR extraction
        full_text = ""
        for _, _, img_bytes in images_data:
            for chunk in analyze_prescription_stream(img_bytes):
                full_text += chunk
        
        # AI Explanation
        query = f"Tu es un assistant pédagogique. Voici le contenu brut : {full_text}. Explique à un patient de {age} ans ce que c'est (fréquence, max/jour). Langue: {language}."
        
        lc_msgs = [HumanMessage(content=query)]
        response = graph.invoke({"messages": lc_msgs, "language": language, "complexity_prompt": "Simple"})
        explanation = response["messages"][-1].content

        # Save Context
        save_message_to_session(session_id, "system", f"Uploaded Document: {full_text}")
        save_message_to_session(session_id, "assistant", explanation)
        
        return {"extracted_text": full_text, "explanation": explanation}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)