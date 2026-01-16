// -----------------------
// WebSocket connection
// -----------------------
const ws = new WebSocket(`ws://${window.location.host}/ws`);
let userId = 'user_' + Math.floor(Math.random()*1000000); // temporary unique user id
let balance = 1000;
let currentMultiplier = 1.0;
let roundActive = false;
let currentBet = 0;
let cashoutEnabled = false;
let history = [];

// DOM elements
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const balanceEl = document.getElementById('balance');
const betInput = document.getElementById('betAmount');
const placeBetBtn = document.getElementById('placeBet');
const cashoutBtn = document.getElementById('cashout');
const timerEl = document.getElementById('timer');
const historyList = document.getElementById('historyList');

// Assets
const plane = new Image();
plane.src = 'assets/plane.png';
let planeY = canvas.height - 100;

// -----------------------
// WebSocket events
// -----------------------
ws.onopen = () => {
    ws.send(JSON.stringify({action:"register", user_id:userId}));
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    switch(msg.action){
        case "update_balance":
            balance = msg.balance;
            balanceEl.textContent = `Balance: $${balance.toFixed(2)}`;
            break;

        case "bet_confirmed":
            currentBet = msg.amount;
            cashoutEnabled = true;
            break;

        case "error":
            alert(msg.message);
            break;

        case "round_start":
            roundActive = true;
            currentMultiplier = 1.0;
            cashoutEnabled = true;
            timerEl.textContent = `Next Round: ${msg.duration}s`;
            break;

        case "update_multiplier":
            currentMultiplier = msg.multiplier;
            break;

        case "round_end":
            roundActive = false;
            cashoutEnabled = false;
            currentBet = 0;
            history = msg.history;
            updateHistory();
            break;

        case "cashed_out":
            balance = balance + msg.payout;
            balanceEl.textContent = `Balance: $${balance.toFixed(2)}`;
            currentBet = 0;
            cashoutEnabled = false;
            break;
    }
};

// -----------------------
// Betting events
// -----------------------
placeBetBtn.onclick = () => {
    if(!roundActive){
        const bet = parseFloat(betInput.value);
        if(bet <= 0 || bet > balance){
            alert("Invalid bet amount!");
            return;
        }
        ws.send(JSON.stringify({action:"bet", user_id:userId, amount: bet}));
    } else {
        alert("Betting closed, round started!");
    }
};

cashoutBtn.onclick = () => {
    if(cashoutEnabled && roundActive && currentBet > 0){
        ws.send(JSON.stringify({action:"cashout", user_id:userId}));
    }
};

// -----------------------
// History update
// -----------------------
function updateHistory(){
    historyList.innerHTML = '';
    history.slice(0,20).forEach(h=>{
        const li = document.createElement('li');
        li.textContent = `Round x${h.toFixed(2)}`;
        historyList.appendChild(li);
    });
}

// -----------------------
// Game loop animation
// -----------------------
function gameLoop(){
    ctx.clearRect(0,0,canvas.width,canvas.height);

    // Animate plane
    if(roundActive){
        planeY -= 2 * currentMultiplier; 
    } else {
        planeY += 5; // fall back to start
        if(planeY > canvas.height - 100) planeY = canvas.height - 100;
    }

    ctx.drawImage(plane, canvas.width/2 - 50, planeY, 100, 50);

    // Draw multiplier on canvas
    ctx.fillStyle = "#fff";
    ctx.font = "24px Arial";
    ctx.fillText(`Multiplier: x${currentMultiplier.toFixed(2)}`, 10, 30);

    requestAnimationFrame(gameLoop);
}

gameLoop();
