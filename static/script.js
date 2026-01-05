let currentSessionId = null;

window.onload = async () => {
    // 1. Get History
    await loadHistory();
    // 2. Start a new session invisibly
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
    const res = await fetch('/api/new_session', { method: 'POST' });
    const data = await res.json();
    currentSessionId = data.session_id;
    
    // Clear Chat UI
    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">👋</div>
            <h3>Bonjour !</h3>
            <p>Je suis votre assistant santé.</p>
        </div>`;
    
    // Deselect history items
    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
    switchTab('chat');
}

async function loadHistory() {
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

    // Smart "Delete All" Button
    if (sessions.length > 0) {
        const btn = document.createElement('div');
        btn.innerHTML = `<button class="delete-all-btn" onclick="deleteAllSessions()"><i class="fas fa-trash-alt"></i> Tout supprimer</button>`;
        list.appendChild(btn);
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
    
    // 1. INSTANT UPDATE: Add message to UI immediately
    input.value = ''; 
    const empty = document.querySelector('.empty-state');
    if(empty) empty.remove();
    
    addMessage(text, 'user', false); 
    
    // 2. Add loading indicator
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
        
        // 3. Replace loading with response
        document.getElementById(thinkingId).remove();
        addMessage(data.response, 'assistant', true); 
        
        loadHistory(); 
        
    } catch (e) {
        document.getElementById(thinkingId).innerText = "Erreur de connexion.";
    }
}

// --- TYPEWRITER ---
function addMessage(text, role, useTypewriter = false) {
    const box = document.getElementById('chatBox');
    const div = document.createElement('div');
    div.className = `message ${role === 'user' ? 'user' : 'bot'}`;
    
    if (useTypewriter && role === 'bot') {
        box.appendChild(div);
        let i = 0;
        div.innerHTML = "";
        const speed = 10;
        
        function type() {
            if (i < text.length) {
                const char = text.charAt(i);
                div.innerHTML += (char === '\n' ? '<br>' : char);
                i++;
                box.scrollTop = box.scrollHeight; 
                setTimeout(type, speed);
            }
        }
        type();
    } else {
        div.innerHTML = text.replace(/\n/g, '<br>');
        box.appendChild(div);
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

// --- SCANNER ---
function handleFileSelect() {
    const file = document.getElementById('fileInput').files[0];
    if(file) {
        const display = document.getElementById('fileNameDisplay');
        display.innerText = "Fichier : " + file.name;
        display.classList.remove('hidden');
        document.getElementById('analyzeBtn').classList.remove('hidden');
    }
}

async function uploadFile() {
    const file = document.getElementById('fileInput').files[0];
    if(!file) return;
    
    document.getElementById('analyzeBtn').classList.add('hidden');
    document.getElementById('scanLoader').classList.remove('hidden');
    document.getElementById('scanResultSection').classList.add('hidden');
    document.getElementById('medCardsContainer').innerHTML = ""; 
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', currentSessionId);
    formData.append('age', document.getElementById('userAge').value);
    formData.append('language', document.getElementById('userLang').value);
    
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        
        if(!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Upload failed");
        }

        const data = await res.json();
        
        document.getElementById('scanLoader').classList.add('hidden');
        document.getElementById('scanResultSection').classList.remove('hidden');
        
        // 1. Render Cards
        const cardsContainer = document.getElementById('medCardsContainer');
        if (data.meds_data && data.meds_data.length > 0) {
            data.meds_data.forEach(med => {
                const card = document.createElement('div');
                card.className = 'med-card';
                card.innerHTML = `
                    <div class="med-name">${med.nom || '?'}</div>
                    <div class="med-dosage">${med.dosage || ''}</div>
                    <div class="med-posology">${med.posologie || ''}</div>
                `;
                cardsContainer.appendChild(card);
            });
        }
        
        // 2. Typewriter Explanation
        const textContainer = document.getElementById('scanExplanation');
        textContainer.innerHTML = ""; 
        let i = 0;
        function typeScan() {
            if (i < data.explanation.length) {
                textContainer.innerHTML += (data.explanation.charAt(i) === '\n' ? '<br>' : data.explanation.charAt(i));
                i++;
                setTimeout(typeScan, 8);
            }
        }
        typeScan();

        // 3. Raw Content
        document.getElementById('scanRawContent').innerText = data.extracted_text;
        
        loadHistory();
        
    } catch(e) {
        alert("Erreur: " + e.message);
        document.getElementById('scanLoader').classList.add('hidden');
        document.getElementById('analyzeBtn').classList.remove('hidden');
    }
}

// --- DELETE ---
async function deleteSession(sid, e) {
    e.stopPropagation();
    if(!confirm("Supprimer ?")) return;
    await fetch(`/api/session/${sid}`, { method: 'DELETE' });
    if(sid === currentSessionId) startNewSession();
    else loadHistory();
}

async function deleteAllSessions() {
    if(!confirm("⚠️ Attention : Cela va effacer TOUT l'historique. Continuer ?")) return;
    await fetch('/api/delete_all_sessions', { method: 'DELETE' });
    startNewSession(); 
    loadHistory(); 
}

function scrollToBottom() {
    const box = document.getElementById('chatBox');
    box.scrollTop = box.scrollHeight;
}

document.getElementById('userInput').addEventListener('keypress', (e) => {
    if(e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});