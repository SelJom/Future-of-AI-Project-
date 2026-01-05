let currentSessionId = null;

window.onload = async () => {
    await loadHistory();
    startNewSession();
};

function switchTab(tabName) {
    document.querySelectorAll('.view').forEach(el => el.classList.remove('active-view'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    document.getElementById(tabName + '-view').classList.add('active-view');
    const buttons = document.querySelectorAll('.tab');
    if (tabName === 'chat') buttons[0].classList.add('active');
    else buttons[1].classList.add('active');
}

async function startNewSession() {
    try {
        const res = await fetch('/api/new_session', { method: 'POST' });
        const data = await res.json();
        currentSessionId = data.session_id;
        
        const chatBox = document.getElementById('chatBox');
        chatBox.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">👋</div>
                <h3>Bonjour !</h3>
                <p>Je suis votre assistant santé.</p>
            </div>`;
        
        document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
        switchTab('chat');
        resetScanView();
    } catch (e) {
        console.error("Session creation failed", e);
    }
}

function resetScanView() {
    const fileInput = document.getElementById('fileInput');
    if(fileInput) fileInput.value = "";
    
    document.getElementById('fileNameDisplay').classList.add('hidden');
    document.getElementById('analyzeBtn').classList.add('hidden');
    document.getElementById('scanResultSection').classList.add('hidden');
    document.getElementById('scanLoader').classList.add('hidden');
    document.getElementById('uploadZone').classList.remove('hidden');
}

async function loadHistory() {
    try {
        const res = await fetch('/api/history');
        const sessions = await res.json();
        const list = document.getElementById('historyList');
        list.innerHTML = '';
        
        sessions.forEach(sess => {
            const item = document.createElement('div');
            item.className = `history-item ${sess.id === currentSessionId ? 'active' : ''}`;
            item.onclick = () => loadChat(sess.id);
            item.innerHTML = `
                <span>${sess.title}</span>
                <i class="fas fa-trash delete-icon" onclick="deleteSession('${sess.id}', event)"></i>
            `;
            list.appendChild(item);
        });

        if (sessions.length > 0) {
            const btn = document.createElement('div');
            btn.innerHTML = `<button class="delete-all-btn" onclick="deleteAllSessions()"><i class="fas fa-trash-alt"></i> Tout supprimer</button>`;
            list.appendChild(btn);
        }
    } catch(e) {
        console.error("History load failed", e);
    }
}

async function loadChat(sessionId) {
    currentSessionId = sessionId;
    await loadHistory();
    
    const res = await fetch(`/api/messages/${sessionId}`);
    const messages = await res.json();
    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML = ''; 
    
    messages.forEach(msg => addMessage(msg.content, msg.role, false)); 
    scrollToBottom();
    switchTab('chat');
}

async function sendMessage() {
    const input = document.getElementById('userInput');
    const text = input.value.trim();
    if (!text) return;
    
    input.value = ''; 
    const empty = document.querySelector('.empty-state');
    if(empty) empty.remove();
    
    addMessage(text, 'user', false); 
    const thinkingId = addThinking();
    scrollToBottom();
    
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: text,
                age: parseInt(document.getElementById('userAge').value),
                language: document.getElementById('userLang').value,
                literacy_level: document.getElementById('userLevel').value
            })
        });
        const data = await res.json();
        
        document.getElementById(thinkingId).remove();
        addMessage(data.response, 'assistant', true); 
        
        if (data.fairness_metrics) {
            addFairnessScorecard(data.fairness_metrics);
        }
        
        loadHistory(); 
        
    } catch (e) {
        if(document.getElementById(thinkingId)) document.getElementById(thinkingId).innerText = "Erreur de connexion.";
    }
}

// --- CORE FUNCTION: Render Message with Markdown ---
function addMessage(text, role, useTypewriter = false) {
    const box = document.getElementById('chatBox');
    const div = document.createElement('div');
    div.className = `message ${role === 'user' ? 'user' : 'bot'}`;
    box.appendChild(div);

    if (useTypewriter && role === 'bot') {
        let i = 0;
        div.textContent = ""; 
        const speed = 5; 
        
        function type() {
            if (i < text.length) {
                div.textContent += text.charAt(i);
                i++;
                box.scrollTop = box.scrollHeight; 
                setTimeout(type, speed);
            } else {
                div.innerHTML = marked.parse(text);
                box.scrollTop = box.scrollHeight;
            }
        }
        type();
    } else {
        if (role === 'user') {
            div.textContent = text; 
        } else {
            div.innerHTML = marked.parse(text); 
        }
    }
    scrollToBottom();
}

function addThinking() {
    const box = document.getElementById('chatBox');
    const div = document.createElement('div');
    div.className = 'message thinking';
    div.id = 'thinking-' + Date.now();
    div.innerText = 'Le modèle réfléchit...';
    box.appendChild(div);
    return div.id;
}

// --- UPDATED FAIRNESS CARD ---
function addFairnessScorecard(metrics) {
    const box = document.getElementById('chatBox');
    const div = document.createElement('div');
    div.className = 'fairness-card';
    
    const complexityColor = metrics.complexity_score > 7 ? '#ef4444' : (metrics.complexity_score > 4 ? '#f97316' : '#22c55e');
    const toxicityColor = metrics.toxicity_score > 1 ? '#ef4444' : '#22c55e';
    const biasColor = metrics.bias_detected ? '#ef4444' : '#22c55e';
    const biasText = metrics.bias_detected ? 'DÉTECTÉ' : 'AUCUN';
    
    const helpId = 'help-' + Date.now();

    // Includes Reasoning and 3 Metrics
    div.innerHTML = `
        <div class="fairness-header">
            <span><i class="fas fa-balance-scale"></i> Audit Éthique</span>
            <i class="fas fa-question-circle fairness-help-icon" onclick="toggleFairnessHelp('${helpId}')"></i>
        </div>
        
        <div id="${helpId}" class="fairness-explanation hidden">
            <div style="margin-bottom:8px; padding-bottom:8px; border-bottom:1px solid #334155;">
                <strong>🔍 Analyse IA :</strong><br>
                <em style="color:#93c5fd;">"${metrics.reasoning}"</em>
            </div>
            <strong>📊 Définitions :</strong>
            <ul>
                <li><strong>Complexité</strong> : Jargon médical. (Cible < 5)</li>
                <li><strong>Toxicité</strong> : Propos dangereux. (Cible 0)</li>
                <li><strong>Biais</strong> : Préjugés culturels/raciaux.</li>
            </ul>
        </div>
        
        <div class="fairness-grid">
            <div class="metric">
                <span>Complexité</span>
                <span style="color: ${complexityColor}; font-weight:bold;">${metrics.complexity_score.toFixed(1)}</span>
            </div>
            <div class="metric">
                <span>Toxicité</span>
                <span style="color: ${toxicityColor}; font-weight:bold;">${metrics.toxicity_score.toFixed(1)}</span>
            </div>
             <div class="metric">
                <span>Biais</span>
                <span style="color: ${biasColor}; font-weight:bold; font-size:11px;">${biasText}</span>
            </div>
        </div>`;
    box.appendChild(div);
    scrollToBottom();
}

function toggleFairnessHelp(id) {
    const el = document.getElementById(id);
    el.classList.toggle('hidden');
}

// --- SCANNER LOGIC ---
function handleFileSelect() {
    console.log("File selected");
    const file = document.getElementById('fileInput').files[0];
    if(file) {
        const display = document.getElementById('fileNameDisplay');
        display.innerText = "Fichier : " + file.name;
        display.classList.remove('hidden');
        document.getElementById('analyzeBtn').classList.remove('hidden');
    }
}

async function uploadFile() {
    console.log("Upload triggered");
    
    if (!currentSessionId) { 
        alert("Session non initialisée. Veuillez rafraîchir."); 
        return; 
    }
    const fileInput = document.getElementById('fileInput');
    const file = fileInput ? fileInput.files[0] : null;
    
    if(!file) {
        alert("Aucun fichier sélectionné.");
        return;
    }
    
    document.getElementById('uploadZone').classList.add('hidden');
    document.getElementById('analyzeBtn').classList.add('hidden');
    document.getElementById('scanLoader').classList.remove('hidden');
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', currentSessionId);
    formData.append('age', document.getElementById('userAge').value || "30");
    formData.append('language', document.getElementById('userLang').value || "Français");
    
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        if(!res.ok) throw new Error("Erreur serveur lors de l'envoi");
        
        const data = await res.json();
        
        document.getElementById('scanLoader').classList.add('hidden');
        document.getElementById('scanResultSection').classList.remove('hidden');
        
        const cardsContainer = document.getElementById('medCardsContainer');
        cardsContainer.innerHTML = "";
        
        if (data.meds_data && data.meds_data.length > 0) {
            data.meds_data.forEach(med => {
                if (!med.nom || med.nom.toUpperCase().includes("INCERTAIN")) return;
                const card = document.createElement('div');
                card.className = 'med-card';
                card.innerHTML = `<div class="med-name">${med.nom}</div><div class="med-dosage">${med.dosage || ''}</div><div class="med-posology">${med.posologie || ''}</div>`;
                cardsContainer.appendChild(card);
            });
        }
        
        // Refresh Chat
        await loadHistory();
        const resMsg = await fetch(`/api/messages/${currentSessionId}`);
        const messages = await resMsg.json();
        const chatBox = document.getElementById('chatBox');
        chatBox.innerHTML = ''; 
        messages.forEach(msg => addMessage(msg.content, msg.role, false)); 
        switchTab('chat');
        
    } catch(e) {
        console.error(e);
        alert("Erreur: " + e.message);
        resetScanView();
    }
}

async function deleteSession(sid, e) {
    e.stopPropagation();
    if(!confirm("Supprimer ?")) return;
    await fetch(`/api/session/${sid}`, { method: 'DELETE' });
    if(sid === currentSessionId) startNewSession();
    else loadHistory();
}

async function deleteAllSessions() {
    if(!confirm("Effacer TOUT ?")) return;
    await fetch('/api/delete_all_sessions', { method: 'DELETE' });
    startNewSession(); 
    loadHistory(); 
}

function scrollToBottom() {
    const box = document.getElementById('chatBox');
    if(box) box.scrollTop = box.scrollHeight;
}

document.getElementById('userInput').addEventListener('keypress', (e) => {
    if(e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});