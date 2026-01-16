// -----------------------------
// Mersenne Twister RNG
// -----------------------------
class MT19937 {
    constructor(seed = Date.now()) {
        this.mt = new Array(624);
        this.index = 624;
        this.mt[0] = seed >>> 0;
        for (let i = 1; i < 624; i++) {
            this.mt[i] = (0x6c078965 * (this.mt[i-1] ^ (this.mt[i-1] >>> 30)) + i) >>> 0;
        }
    }
    generate() {
        if (this.index >= 624) this.twist();
        let y = this.mt[this.index];
        y ^= y >>> 11;
        y ^= (y << 7) & 0x9d2c5680;
        y ^= (y << 15) & 0xefc60000;
        y ^= y >>> 18;
        this.index++;
        return y >>> 0;
    }
    random() {
        return this.generate() / 0x100000000;
    }
    twist() {
        for (let i = 0; i < 624; i++) {
            let y = (this.mt[i] & 0x80000000) + (this.mt[(i+1)%624] & 0x7fffffff);
            this.mt[i] = this.mt[(i + 397) % 624] ^ (y >>> 1);
            if (y % 2 !== 0) this.mt[i] ^= 0x9908b0df;
        }
        this.index = 0;
    }
}

// -----------------------------
// Game Variables
// -----------------------------
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const mt = new MT19937();
let planeImg = new Image();
planeImg.src = "assets/plane.png";

let running = false;
let multiplier = 1.0;
let crashMultiplier = 0;
let planeX = 50;
let planeY = canvas.height - 50;
let history = [];
let houseEdge = 0.01;
let mode = "demo";

// -----------------------------
// Controls
// -----------------------------
document.getElementById("startBtn").addEventListener("click", () => {
    running = true;
    multiplier = 1.0;
    crashMultiplier = getMultiplier();
    planeY = canvas.height - 50;
    mode = document.getElementById("modeSelect").value;
    console.log("Next crash multiplier:", crashMultiplier.toFixed(2));
});
document.getElementById("cashOutBtn").addEventListener("click", () => {
    if(running){
        running = false;
        console.log("Cashed out at", multiplier.toFixed(2) + "x");
        history.unshift(multiplier.toFixed(2) + "x");
        if(history.length>10) history.pop();
        updateHistory();
    }
});

// -----------------------------
// Multiplier RNG
// -----------------------------
function getMultiplier() {
    let r = mt.random();
    let m = (1 + r*15) * (1 - houseEdge); // house edge applied
    return parseFloat(m.toFixed(2));
}

// -----------------------------
// Draw Previous Multipliers
// -----------------------------
function updateHistory(){
    document.getElementById("history").innerText = "Previous multipliers: " + history.join(", ");
}

// -----------------------------
// Game Loop
// -----------------------------
function gameLoop(){
    ctx.clearRect(0,0,canvas.width,canvas.height);

    // Update multiplier
    if(running){
        multiplier += multiplier * 0.03;
        planeY = canvas.height - 50 - Math.pow(multiplier*4,1.05);
        if(multiplier >= crashMultiplier){
            running = false;
            console.log("Crashed at", crashMultiplier.toFixed(2) + "x");
            history.unshift(crashMultiplier.toFixed(2) + "x");
            if(history.length>10) history.pop();
            updateHistory();
        }
    }

    // Draw crash line
    let crashX = 50 + crashMultiplier * 30;
    ctx.strokeStyle = "red";
    ctx.beginPath();
    ctx.moveTo(crashX,0);
    ctx.lineTo(crashX,canvas.height);
    ctx.stroke();

    // Draw plane
    if(planeImg.complete){
        ctx.drawImage(planeImg, planeX, Math.max(0, planeY), 50,50);
    } else {
        // fallback triangle
        ctx.fillStyle = "yellow";
        ctx.beginPath();
        ctx.moveTo(planeX, planeY);
        ctx.lineTo(planeX-10, planeY+20);
        ctx.lineTo(planeX+10, planeY+20);
        ctx.closePath();
        ctx.fill();
    }

    // Draw multiplier bar
    ctx.fillStyle = "green";
    ctx.fillRect(50, canvas.height-30, Math.min(multiplier*20, canvas.width-100), 20);

    // Draw multiplier text
    ctx.fillStyle = "white";
    ctx.font = "24px Arial";
    ctx.fillText("Multiplier: " + multiplier.toFixed(2) + "x", canvas.width/2 - 80, 40);

    requestAnimationFrame(gameLoop);
}

planeImg.onload = () => { gameLoop(); }
