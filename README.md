
# Future-of-AI-Project

---

## 1. Architecture Technique Globale

L’approche recommandée est un **Pipeline Modulaire Asynchrone**.  
Plutôt qu’un modèle monolithique qui fait tout, le processus est divisé en **étapes distinctes**, ce qui permet de remplacer un module (ex : OCR) sans impacter le reste du système.

### 🔁 Le Pipeline (Input → Output)

- **Ingestion & Nettoyage (OCR / Parsing)**  
  Conversion du document *(PDF / Image)* en **texte brut structuré**.

- **Extraction Médicale (Expert Agent)**  
  Identification des entités médicales *(médicaments, dosages, pathologies)* **sans simplification**.

- **Adaptation & Traduction (Translator Agent)**  
  Reformulation selon le **profil utilisateur** *(langue, niveau de littératie)*.

- **Vérification (Guardian Agent)**  
  Comparaison critique entre l’Extraction et l’Adaptation pour **éviter les hallucinations**.

- **Interface Utilisateur**  
  Présentation claire et accessible du résultat final.

---

## 2. Stack Technologique Recommandée

- **Langage** : **Python 3.10+**  
  Standard de facto pour l’IA et le NLP.

- **Backend / API** : **FastAPI**  
  **Pourquoi ?**
  - Asynchrone et très performant  
  - Validation native via **Pydantic** (crucial pour les données médicales)  
  - Documentation automatique (**Swagger UI**)

- **Orchestration LLM** : **LangChain** ou **LangGraph**  
  **Pourquoi ?**
  - Gestion des prompts  
  - Mémoire conversationnelle  
  - Enchaînement et coordination des agents

- **Frontend (MVP)** : **Streamlit**  
  **Pourquoi ?**
  - Interface web rapide en pur Python  
  - Idéal pour un projet étudiant  
  - Évite la complexité de React/Vue

---

## 3. Choix des Modèles (Contrainte Budget Étudiant)

### A. Compréhension Médicale & Extraction

- **Choix recommandé (API gratuit / freemium)**  
  - **Gemini 2.5 Flash (Google)**  (il y a aussi MedPalm à tester)
  - **GPT-4o-mini (OpenAI)**  

  **Justification :**
  - Coût très faible voire gratuit  
  - Excellent raisonnement  
  - Très grande fenêtre de contexte (documents longs)

- **Alternative Open-Source (Local)**  
  - **BioMistral-7B**

  **Justification :**
  - Modèle spécialisé médical  
  - Basé sur Mistral  

  **Contrainte :**
  - Nécessite un **GPU** (Colab ou machine puissante)  
  - Peu adapté à un backend web simple  
  👉 **API recommandée pour le MVP**

---

### B. Simplification & Adaptation

- **Choix recommandé**
  - **Llama 3 (via Groq)**  
  - **Gemini 1.5 Flash**

**Justification :**
- Groq : inférence **ultra-rapide** et gratuite (actuellement)  
- Llama 3 : excellent suivi des **instructions de style et de ton**

---

## 4. Stratégie Multi-Agent (Architecture Idéale)

Pour garantir la **sécurité médicale**, une architecture **Multi-Agent** est la plus robuste.  
Elle sépare clairement la **connaissance médicale** de la **pédagogie**.

### 🧠 Rôles des Agents

#### 🩺 Agent Extracteur — *« Le Médecin »*

- **Tâche** :
  - Lecture du texte brut
  - Extraction dans un **JSON strict** :
    - diagnostic  
    - médicaments  
    - posologie  
    - signes_alarme  

- **Règles** :
  - Aucune simplification  
  - Aucun ajout  
  - Jargon médical conservé

- **Prompt système** :
  > *« Tu es un expert médical. Extrais les faits cliniques exacts. Ne résume pas, n’invente rien. »*

---

#### 📚 Agent Traducteur — *« Le Pédagogue »*

- **Tâche** :
  - Reçoit le JSON médical  
  - Reçoit le **profil utilisateur** *(ex : “Niveau CM2, Langue Espagnol”)*  
  - Génère le texte final adapté

- **Prompt système** :
  > *« Tu es un médiateur en santé. Utilise des analogies simples. Explique “Hypertension” par “Tension artérielle élevée”. Ton ton doit être empathique. »*

---

#### 💊 Agent Critique — *« Le Pharmacien »* *(Optionnel mais recommandé)*

- **Tâche** :
  - Compare la sortie du Traducteur avec le JSON de l’Extracteur

- **Vérifications** :
  - Le dosage est-il conservé ? *(ex : 500 mg)*  
  - Les termes médicaux sont-ils correctement traduits ?  

- **Action** :
  - En cas d’erreur → **renvoi pour correction**

---

## 5. Gestion du Contexte et de la Mémoire

Dans une application médicale, la mémoire doit être gérée avec **extrême prudence**.

### ✅ Ce qui est stocké (Session State)

- Profil utilisateur *(langue, niveau d’étude)*  
- Document en cours de traitement  
- Historique immédiat de Q/R sur ce document

### ❌ Ce qui n’est PAS stocké (ou anonymisé)

- Données personnelles identifiables *(PII)* :
  - Nom  
  - Adresse  
  - Numéro de dossier  

**Pourquoi ?**
- Sécurité des données  
- Conformité **RGPD / HIPAA**  
- Un MVP étudiant ne garantit pas une persistance sécurisée

### 🛠️ Implémentation Technique

- **LangChain Memory**
  - `ConversationBufferWindowMemory`
  - Fenêtre glissante courte *(k = 5 échanges)*  
  - Suffisant pour les questions de clarification

---

## 6. Biais et Stratégies de Mitigation

### ⚠️ Identification des Biais

- **Biais socio-éducatif**  
  Risque de ton infantilisant pour les niveaux faibles

- **Biais culturel**  
  Analogies occidentales non universelles

- **Biais linguistique**  
  Perte de nuance lors de la traduction

---

### ✅ Stratégies de Mitigation

- **System Prompting – Persona**
  - Rôle imposé : *Respectful Health Advocate*
  - Interdiction explicite du ton infantilisant

- **Few-Shot Prompting (Exemples)**

  - ❌ *Mauvais* :  
    > « Prends tes bobos-pilules. »

  - ✅ *Bon* :  
    > « Prenez ce médicament pour aider votre cœur à battre plus régulièrement. »

- **Disclaimer Automatique**
  > *« Ceci est une aide à la lecture générée par IA. En cas de doute, référez-vous toujours au document original ou à votre médecin. »*

---

## 7. Approche Progressive (MVP)

### 🟢 Semaine 1–2 : MVP Monolithique

- Un seul appel LLM *(Gemini)*  
- Input : texte copié-collé  
- Output : texte simplifié  
- Interface : **CLI Python**

---

### 🟡 Semaine 3–4 : Intégration & OCR

- OCR avec **Tesseract / PyMuPDF**  
- API **FastAPI**  
- Interface **Streamlit** basique

---

### 🔵 Semaine 5–6 : Multi-Agent & Robustesse

- Séparation Extracteur / Traducteur  
- Gestion des erreurs *(document illisible, champs manquants)*  
- Mise en place de **tests de biais**

---
```
