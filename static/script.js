let currentSessionId = null;

// --- INITIALIZATION ---
window.onload = async () => {
    await loadHistory();
    // Create new session if none exists, or load the most recent one
    if (!currentSessionId) {
        await createNewSession();
    }
};

// --- API CALLS ---

async function createNewSession() {
    const res = await fetch('/api/new_session', { method: 'POST' });
    const data = await res.json();
    currentSessionId = data.session_id;
    await loadHistory();
    loadChat(currentSessionId);
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
        item.innerHTML = `
            <span onclick="loadChat('${sess.id}')">${sess.title}</span>
            <i class="fas fa-trash delete-icon" onclick="deleteSession('${sess.id}', event)"></i>
        `;
        list.appendChild(item);
    });
}

async function loadChat(sessionId) {
    currentSessionId = sessionId;
    // Update active state in sidebar
    document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
    // (Ideally find the element by ID and add active class, logic simplified here)
    
    const res = await fetch(`/api/messages/${sessionId}`);
    const messages = await res.json();
    
    const chatBody = document.getElementById('chatBody');
    chatBody.innerHTML = ''; // Clear current
    
    if (messages.length === 0) {
        chatBody.innerHTML = '<div class="empty-state">👋 Bonjour ! Je suis votre assistant santé.</div>';
    } else {
        messages.forEach(msg => addMessageToUI(msg.content, msg.role));
    }
    
    scrollToBottom();
}

async function deleteSession(sid, event) {
    event.stopPropagation(); // Prevent clicking the item
    if(!confirm("Supprimer cette conversation ?")) return;
    
    await fetch(`/api/session/${sid}`, { method: 'DELETE' });
    if (sid === currentSessionId) {
        createNewSession();
    } else {
        loadHistory();
    }
}

async function sendMessage() {
    const input = document.getElementById('userInput');
    const text = input.value.trim();
    if (!text) return;
    
    // UI Update
    addMessageToUI(text, 'user');
    input.value = '';
    
    // Thinking State
    const thinkingId = 'thinking-' + Date.now();
    const chatBody = document.getElementById('chatBody');
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'message thinking';
    thinkingDiv.id = thinkingId;
    thinkingDiv.innerText = 'Le modèle réfléchit...';
    chatBody.appendChild(thinkingDiv);
    scrollToBottom();
    
    // API Call
    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: text,
                age: document.getElementById('userAge').value,
                language: document.getElementById('userLang').value,
                literacy_level: document.getElementById('userLevel').value
            })
        });
        const data = await res.json();
        
        // Replace thinking with response
        document.getElementById(thinkingId).remove();
        addMessageToUI(data.response, 'assistant');
        
        // Refresh history title might have changed
        loadHistory(); 
        
    } catch (e) {
        console.error(e);
        document.getElementById(thinkingId).innerText = "Erreur de connexion.";
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    if (!file) return alert("Veuillez sélectionner un fichier.");
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', currentSessionId);
    formData.append('age', document.getElementById('userAge').value);
    formData.append('language', document.getElementById('userLang').value);
    
    document.getElementById('scanLoader').classList.remove('hidden');
    document.getElementById('scanResult').classList.add('hidden');
    
    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        
        document.getElementById('scanLoader').classList.add('hidden');
        document.getElementById('scanResult').classList.remove('hidden');
        document.getElementById('scanTextContent').innerText = data.explanation;
        
        // Refresh chat to show the new context/explanation saved there too
        loadChat(currentSessionId);
        
    } catch (e) {
        alert("Erreur lors de l'analyse");
        document.getElementById('scanLoader').classList.add('hidden');
    }
}

// --- HELPERS ---

function addMessageToUI(text, role) {
    const chatBody = document.getElementById('chatBody');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role === 'user' ? 'user' : 'bot'}`;
    // Simple markdown replacement (bold/newlines) could go here
    msgDiv.innerHTML = text.replace(/\n/g, '<br>'); 
    chatBody.appendChild(msgDiv);
    scrollToBottom();
}

function scrollToBottom() {
    const chatBody = document.getElementById('chatBody');
    chatBody.scrollTop = chatBody.scrollHeight;
}

function switchTab(tabName) {
    document.querySelectorAll('.view').forEach(el => el.classList.remove('active-view'));
    document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
    
    document.getElementById(tabName + '-view').classList.add('active-view');
    // Highlight the clicked button logic (simple approximation)
    const buttons = document.querySelectorAll('.tab');
    if(tabName === 'chat') buttons[0].classList.add('active');
    else buttons[1].classList.add('active');
}

// Enter key to send
document.getElementById('userInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});