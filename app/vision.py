import ollama
from PIL import Image
import io
import fitz  
from app.config import Config

def analyze_prescription(image_bytes):
    """
    Sends the image to the local AI to extract medication data.
    """
    prompt = """
    You are an expert pharmacist assistant. Analyze this medical image (prescription or medication box).
    
    Task: Extract the following details strictly in JSON format.
    1. Medication Name ("nom")
    2. Dosage ("dosage") - e.g. 1000mg, 500mg
    3. Instructions ("posologie") - e.g. 1 morning and evening
    
    Output Format (JSON ONLY):
    {
      "medicaments": [
        {
          "nom": "Doliprane", 
          "dosage": "1000mg", 
          "posologie": "1 comprimé en cas de fièvre"
        }
      ]
    }
    If the text is completely unreadable, use "INCERTAIN" in the field.
    """
    
    try:
        response = ollama.chat(
            model=Config.VISION_MODEL_NAME,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [image_bytes]
            }]
        )
        return response['message']['content']
    except Exception as e:
        return f"Error Vision AI: {str(e)}"

def process_file_to_images(uploaded_file):
    """
    Converts uploaded PDF or Image files into Bytes for the AI.
    Uses PyMuPDF (fitz) for PDFs to ensure scalability.
    """
    processed_images = []
    
    try:
        # A. HANDLE PDF (Portable Method)
        if "pdf" in uploaded_file.type:
            # Read the PDF stream directly from memory
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    # Render page to image (dpi=200 is optimal for speed/accuracy)
                    pix = page.get_pixmap(dpi=200)
                    
                    # Convert to PIL Image
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Convert to Bytes for Ollama
                    b = io.BytesIO()
                    img.save(b, format='JPEG')
                    processed_images.append((f"Page {page_num + 1}", img, b.getvalue()))

        # B. HANDLE STANDARD IMAGES (JPG/PNG)
        else:
            image = Image.open(uploaded_file)
            # Fix transparency issues if present
            if image.mode in ("RGBA", "P"): 
                image = image.convert("RGB")
                
            b = io.BytesIO()
            image.save(b, format='JPEG')
            processed_images.append(("Image importée", image, b.getvalue()))
            
        return processed_images, None

    except Exception as e:
        return None, f"Erreur de lecture du fichier : {str(e)}"