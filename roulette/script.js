const prizes = [
    { text: "Relatório de Inteligência", icon: "📊", desc: "Acesso a um relatório executivo real de prospecção do motor CheckLeads.", color: "#FF6B00" },
    { text: "Consultoria Strategy", icon: "💎", desc: "30 min para desenhar sua arquitetura neural de vendas sem custos de IA.", color: "#1a1a1c" },
    { text: "Copo Laranja Elite", icon: "🥤", desc: "O troféu oficial dos gestores que dominam o CheckLeads.", color: "#FF6B00" },
    { text: "Copo Preto Executive", icon: "🥤", desc: "A estética Apple/SaaS aplicada ao seu dia a dia.", color: "#1a1a1c" },
    { text: "Scripts High-Ticket", icon: "🔥", desc: "Modelos de mensagens executivas para converter leads B2B de alto escalão.", color: "#FF6B00" },
    { text: "Diagnóstico de Funil", icon: "⚙️", desc: "Mapeamento de gargalos no seu processo usando nossa metodologia Strategy.", color: "#1a1a1c" },
    { text: "Checklist: Escala Pura", icon: "🚀", desc: "O guia de engenharia para escalar vendas sem depender de ferramentas caras.", color: "#FF6B00" },
    { text: "Auditoria de Leads", icon: "🔍", desc: "Análise manual de 10 leads do seu nicho usando nosso motor de busca real.", color: "#1a1a1c" }
];

const wheel = document.getElementById('wheel');
const spinBtn = document.getElementById('spinBtn');
const modal = document.getElementById('modal');
const modalTitle = document.getElementById('modalTitle');
const modalDesc = document.getElementById('modalDesc');
const closeModal = document.getElementById('closeModal');
const leadGate = document.getElementById('leadGate');
const unlockBtn = document.getElementById('unlockBtn');
const leadName = document.getElementById('leadName');
const leadPhone = document.getElementById('leadPhone');

// CONFIGURAÇÃO: Seu WhatsApp para receber os leads
const SEU_WHATSAPP = "5511999999999"; // Ex: 5511988887777

// CONFIGURAÇÃO: URL do seu Webhook (n8n, Node.js ou Evolution API Proxy) na sua VPS
const WEBHOOK_URL = window.ROULETTE_WEBHOOK_URL || "/webhook/roleta";

// Audio Context for ticking sound
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
function playTick() {
    const oscillator = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(150, audioCtx.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.1);
    gainNode.gain.setValueAtTime(0.1, audioCtx.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.1);
    oscillator.connect(gainNode);
    gainNode.connect(audioCtx.destination);
    oscillator.start();
    oscillator.stop(audioCtx.currentTime + 0.1);
}

let currentRotation = 0;
const segmentAngle = 360 / prizes.length;

// Generate Conic Gradient and Labels
const gradientParts = prizes.map((prize, i) => {
    return `${prize.color} ${i * segmentAngle}deg ${(i + 1) * segmentAngle}deg`;
});
// Add a subtle white border between segments
wheel.style.background = `conic-gradient(#fff 0deg, ${gradientParts.join(', ')})`;
wheel.style.backgroundImage = `conic-gradient(
    #ffffff22 0deg 1px, 
    transparent 1px), 
    conic-gradient(${gradientParts.join(', ')})`;

prizes.forEach((prize, i) => {
    const label = document.createElement('div');
    label.className = 'segment-label';
    // Ajuste de -90 graus para começar no topo (12h) em vez da direita (3h)
    label.style.transform = `translateY(-50%) rotate(${i * segmentAngle + (segmentAngle / 2) - 90}deg)`;
    
    const text = document.createElement('div');
    text.className = 'segment-text';
    text.innerHTML = `<span>${prize.icon}</span> <span>${prize.text}</span>`;
    
    label.appendChild(text);
    wheel.appendChild(label);
});

spinBtn.addEventListener('click', () => {
    if (spinBtn.disabled) return;
    
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }

    spinBtn.disabled = true;
    
    // 1. Sorteia o prêmio ANTES de girar
    const winningIndex = Math.floor(Math.random() * prizes.length);
    const winner = prizes[winningIndex];

    // 2. Calcula a rotação necessária
    // O ponteiro está no topo (0deg). 
    // Para o winningIndex ficar no topo, o wheel deve girar CCW (-) por:
    // (winningIndex * segmentAngle) + (segmentAngle / 2)
    const extraSpins = Math.floor(Math.random() * 5) + 8; // 8 a 12 voltas
    const targetSegmentRotation = (winningIndex * segmentAngle) + (segmentAngle / 2);
    
    // A rotação total acumulada para garantir que o giro seja fluido e não volte
    const newRotation = (extraSpins * 360) + targetSegmentRotation;
    
    // Ajuste para garantir que sempre gire para frente em relação à rotação atual
    const rotationToApply = Math.ceil(currentRotation / 360) * 360 + newRotation;
    currentRotation = rotationToApply;

    wheel.style.transform = `rotate(-${currentRotation}deg)`;
    
    // 3. Efeito sonoro sincronizado
    let lastTickAngle = 0;
    const startTime = performance.now();
    const duration = 5000;
    
    function animateTicks() {
        const now = performance.now();
        const elapsed = now - startTime;
        if (elapsed < duration) {
            const progress = elapsed / duration;
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const currentAngle = (currentRotation * easeOut);
            
            if (Math.floor(currentAngle / segmentAngle) > Math.floor(lastTickAngle / segmentAngle)) {
                playTick();
                lastTickAngle = currentAngle;
            }
            requestAnimationFrame(animateTicks);
        }
    }
    animateTicks();

    // 4. Mostra o resultado após o tempo da transição CSS (5s)
    setTimeout(() => {
        showWinner(winner);
        spinBtn.disabled = false;
    }, 5000);
});

function showWinner(prize) {
    localStorage.setItem('userWon', JSON.stringify(prize));
    
    // Notifica o Webhook que o usuário GANHOU e qual foi o prêmio
    const leadInfo = JSON.parse(localStorage.getItem('leadInfo') || "{}");
    fetch(WEBHOOK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            event: 'prize_won',
            prize: prize.text,
            lead: leadInfo
        })
    }).catch(err => console.log("Webhook Win Error:", err));

    confetti({
        particleCount: 150,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#FF6B00', '#ffffff', '#000000']
    });

    document.querySelector('.prize-icon').textContent = prize.icon;
    modalTitle.textContent = prize.text;
    modalDesc.textContent = prize.desc;
    
    // Configura o link do WhatsApp
    const message = encodeURIComponent(`Olá! Acabei de ganhar o prêmio: *${prize.text}* na roleta e gostaria de resgatar!`);
    closeModal.onclick = () => {
        window.open(`https://wa.me/${SEU_WHATSAPP}?text=${message}`, '_blank');
        modal.classList.remove('active');
    };

    modal.classList.add('active');
}

// Lógica do Lead Gate
unlockBtn.addEventListener('click', () => {
    if (leadName.value.length < 3 || leadPhone.value.length < 10) {
        alert("Por favor, preescha seu nome e WhatsApp corretamente.");
        return;
    }
    
    const leadData = {
        name: leadName.value,
        phone: leadPhone.value,
        timestamp: new Date().toISOString()
    };
    
    // Salva o lead localmente
    localStorage.setItem('leadInfo', JSON.stringify(leadData));
    
    // Envia o Lead para o seu Webhook na VPS (Evolution API Flow)
    fetch(WEBHOOK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            event: 'lead_captured',
            ...leadData
        })
    })
    .then(() => console.log("Lead enviado com sucesso!"))
    .catch(err => console.error("Erro ao enviar lead:", err));
    
    // Oculta o gate
    leadGate.classList.add('hidden');
});

// Verifica se já girou ao carregar a página
window.onload = () => {
    const previousWin = localStorage.getItem('userWon');
    if (previousWin) {
        const prize = JSON.parse(previousWin);
        leadGate.classList.add('hidden');
        spinBtn.disabled = true;
        showWinner(prize);
    }
};



