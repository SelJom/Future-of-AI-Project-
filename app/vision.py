import ollama
from PIL import Image
import io
import fitz  
from app.config import Config

def analyze_prescription_stream(image_bytes):
    """
    Sends the image to the local AI to extract medication data.
    """
    prompt = """
    You are an expert pharmacist assistant. Analyze this medical image (prescription or medication box).
    
    Task: Extract the following details strictly in JSON format.
    1. Medication Name ("nom")
    2. Dosage ("dosage") - e.g. 1000mg, 500mg
    3. Instructions ("posologie") - e.g. 1 morning and evening, or 1 every 4h with a max of 3 per day...
    
    Output Format (JSON ONLY):
    {
      "medicaments": [
        {
          "nom": "Doliprane", 
          "dosage": "1000mg", 
          "posologie": "1 comprimé en cas de douleur"
        }
      ]
    }
    If the text is completely unreadable, use "INCERTAIN" in the field.
    """
    
    try:
        stream = ollama.chat(
            model=Config.VISION_MODEL_NAME,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [image_bytes]
            }],
            stream=True 
        )
        
        for chunk in stream:
            yield chunk['message']['content']
            
    except Exception as e:
        yield f"Error: {str(e)}"

def analyze_prescription(image_bytes):
    full_text = ""
    for chunk in analyze_prescription_stream(image_bytes):
        full_text += chunk
    return full_text


def process_file_to_images(file_bytes, mime_type):
    """
    Processes raw file bytes into images.
    Args:
        file_bytes (bytes): The file content.
        mime_type (str): The mime type (e.g. 'application/pdf').
    Returns:
        list: [(label, PIL_Image, bytes)]
        str: Error message or None
    """
    processed_images = []
    try:
        # Handle PDF
        if "pdf" in mime_type.lower():
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    b = io.BytesIO()
                    img.save(b, format='JPEG')
                    processed_images.append((f"Page {page_num + 1}", img, b.getvalue()))
        
        # Handle Images
        else:
            image = Image.open(io.BytesIO(file_bytes))
            if image.mode in ("RGBA", "P"): 
                image = image.convert("RGB")
            
            b = io.BytesIO()
            image.save(b, format='JPEG')
            processed_images.append(("Image importée", image, b.getvalue()))
            
        return processed_images, None
    except Exception as e:
        return None, f"Erreur fichier : {str(e)}"