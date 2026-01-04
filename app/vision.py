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
        # On active le mode 'stream' d'Ollama
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

# --- FONCTION 2 : L'Originale (Pour la compatibilité) ---
def analyze_prescription(image_bytes):
    """
    Fonction classique qui attend la fin et renvoie tout le texte d'un coup.
    Elle utilise la fonction stream ci-dessus pour éviter de dupliquer le code.
    """
    full_text = ""
    # On consomme tout le stream pour reconstituer la phrase
    for chunk in analyze_prescription_stream(image_bytes):
        full_text += chunk
    return full_text

# --- FONCTION 3 : Traitement des Fichiers (Inchangée) ---
def process_file_to_images(uploaded_file):
    # (Copiez-collez votre code existant pour process_file_to_images ici)
    # ... le code avec fitz et PIL ...
    # Je remets le début pour rappel :
    processed_images = []
    try:
        if "pdf" in uploaded_file.type:
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page_num, page in enumerate(doc):
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    b = io.BytesIO()
                    img.save(b, format='JPEG')
                    processed_images.append((f"Page {page_num + 1}", img, b.getvalue()))
        else:
            image = Image.open(uploaded_file)
            if image.mode in ("RGBA", "P"): image = image.convert("RGB")
            b = io.BytesIO()
            image.save(b, format='JPEG')
            processed_images.append(("Image importée", image, b.getvalue()))
            
        return processed_images, None
    except Exception as e:
        return None, f"Erreur fichier : {str(e)}"