import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import random, sqlite3, hashlib, time

# --- Flask Setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'aviator_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Database Setup ---
conn = sqlite3.connect("aviator.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            balance REAL)""")
c.execute("""CREATE TABLE IF NOT EXISTS rounds(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crash_point REAL,
            timestamp REAL)""")
c.execute("""CREATE TABLE IF NOT EXISTS cashouts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            round_id INTEGER,
            multiplier REAL,
            amount REAL)""")
conn.commit()

# --- Game Variables ---
multiplier = 1.0
crash_point = 0
round_active = False
round_id = 0
round_history = []

players = {}  # sid -> {user_id, cashout}
TICK = 0.05
HOUSE_EDGE = 0.85

# --- Helpers ---
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def generate_crash():
    return 1 + (random.random()*10)**0.7 * HOUSE_EDGE

def get_user_balance(user_id):
    c.execute("SELECT balance FROM users WHERE id=?",(user_id,))
    res = c.fetchone()
    return res[0] if res else 0

def update_user_balance(user_id, amount):
    balance = get_user_balance(user_id) + amount
    c.execute("UPDATE users SET balance=? WHERE id=?",(balance,user_id))
    conn.commit()
    return balance

# --- Game Loop ---
def game_loop():
    global multiplier, crash_point, round_active, round_id, round_history
    while True:
        if not round_active:
            multiplier = 1.0
            crash_point = generate_crash()
            round_active = True
            round_id += 1
            for p in players.values():
                p["cashout"] = None
            socketio.emit("new_round", {"round_id": round_id, "crash_point": crash_point})
            print(f"New round #{round_id} | Crash at x{crash_point:.2f}")

        multiplier += 0.01*(1 + multiplier/10)
        socketio.emit("multiplier_update", {"multiplier": round(multiplier,2), "round_id": round_id})
        
        if multiplier >= crash_point:
            round_active = False
            round_history.append(round(crash_point,2))
            if len(round_history) > 50:
                round_history.pop(0)
            socketio.emit("round_crash", {"crash_point": round(crash_point,2), "round_id": round_id})
            c.execute("INSERT INTO rounds(crash_point,timestamp) VALUES (?,?)",(crash_point,time.time()))
            conn.commit()
            eventlet.sleep(5)
        eventlet.sleep(TICK)

# --- Routes ---
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Aviator Multiplayer</title>
<style>
body{margin:0;font-family:sans-serif;background:#111;color:#0ff;display:flex;justify-content:center;align-items:center;height:100vh;flex-direction:column;}
.container{background:#000;border:2px solid #0ff;border-radius:20px;padding:30px;width:400px;box-shadow:0 0 25px #0ff;text-align:center;}
h1{margin-bottom:20px;}
p{margin:5px 0;color:#0ff;}
input{padding:10px;margin:10px 0;width:90%;border-radius:10px;border:none;}
button{padding:12px 20px;margin:10px 0;background:linear-gradient(45deg,#0ff,#00f);color:#000;border:none;border-radius:12px;cursor:pointer;font-weight:bold;transition:0.2s;}
button:hover{transform:scale(1.05);box-shadow:0 0 15px #0ff;}
.warning{color:#f00;font-weight:bold;margin-bottom:10px;}
.about{color:#0f0;margin-bottom:10px;font-size:0.9em;}
</style>
</head>
<body>
<div class="container">
<h1>Aviator Multiplayer</h1>
<div class="warning">
⚠️ This is a demo game. Play responsibly. License required.
</div>
<div class="about">
Developed by Lameck Mukabana.
</div>
<button onclick="window.location.href='/login'">Login</button>
<button onclick="window.location.href='/register'">Create Account</button>
</div>
</body>
</html>
""")

@app.route("/register", methods=["GET","POST"])
def register():
    msg=""
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        if not username or not password:
            msg="Enter both fields"
        else:
            try:
                c.execute("INSERT INTO users(username,password,balance) VALUES(?,?,?)",
                          (username,hash_password(password),1000))
                conn.commit()
                return redirect(url_for("login"))
            except:
                msg="Username exists"
    return render_template_string("""
<div style="background:#000;color:#0ff;padding:20px;border-radius:15px;width:400px;margin:auto;text-align:center;margin-top:50px;">
<h2>Register</h2>
<form method="post">
<input name="username" placeholder="Username"><br>
<input type="password" name="password" placeholder="Password"><br>
<button type="submit">Register</button>
</form>
<p style="color:#f00;">{{msg}}</p>
<a href="{{url_for('login')}}">Already have account? Login</a>
</div>
""", msg=msg)

@app.route("/login", methods=["GET","POST"])
def login():
    msg=""
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]
        c.execute("SELECT id,password FROM users WHERE username=?",(username,))
        res=c.fetchone()
        if res and res[1]==hash_password(password):
            session["user_id"]=res[0]
            session["username"]=username
            return redirect(url_for("game"))
        else:
            msg="Invalid credentials"
    return render_template_string("""
<div style="background:#000;color:#0ff;padding:20px;border-radius:15px;width:400px;margin:auto;text-align:center;margin-top:50px;">
<h2>Login</h2>
<form method="post">
<input name="username" placeholder="Username"><br>
<input type="password" name="password" placeholder="Password"><br>
<button type="submit">Login</button>
</form>
<p style="color:#f00;">{{msg}}</p>
<a href="{{url_for('register')}}">No account? Register</a>
</div>
""", msg=msg)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# --- SocketIO Events ---
@socketio.on("connect")
def connect():
    if "user_id" in session:
        players[request.sid] = {"user_id": session["user_id"], "cashout": None}
        emit("init", {"balance": get_user_balance(session["user_id"]),
                      "history": round_history})

@socketio.on("disconnect")
def disconnect():
    if request.sid in players:
        del players[request.sid]

@socketio.on("cashout")
def cashout(data):
    sid=request.sid
    if sid not in players: return
    if not round_active: return
    if players[sid]["cashout"] is not None: return
    bet=float(data.get("bet",0))
    mult=float(data.get("multiplier",1))
    user_id = players[sid]["user_id"]
    balance=get_user_balance(user_id)
    if bet>balance: return
    win=bet*mult
    balance=update_user_balance(user_id,-bet+win)
    players[sid]["cashout"]=mult
    c.execute("INSERT INTO cashouts(user_id,round_id,multiplier,amount) VALUES (?,?,?,?)",
              (user_id,round_id,mult,win))
    conn.commit()
    emit("cashout_result",{"balance":balance,"win":win})

# --- Game Page ---
@app.route("/game")
def game():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template_string(""" 
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aviator Multiplayer</title>
<script src="https://cdn.socket.io/4.7.1/socket.io.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
body{margin:0;font-family:sans-serif;background:#111;color:#0ff;display:flex;flex-direction:column;align-items:center;}
h1{margin:20px;}
.panel-row{display:flex;gap:20px;justify-content:center;margin-bottom:20px;flex-wrap:wrap;}
.panel{background:#000;border:2px solid #0ff;border-radius:15px;padding:15px;min-width:220px;text-align:center;box-shadow:0 0 15px #0ff;}
button{padding:12px 25px;margin-top:10px;background:linear-gradient(45deg,#0ff,#00f);color:#000;border:none;border-radius:12px;cursor:pointer;font-weight:bold;transition:0.2s;}
button:hover{transform:scale(1.1);box-shadow:0 0 15px #0ff;}
#message{color:#f00;margin-top:5px;font-weight:bold;}
canvas{background:#000;border-radius:10px;}
#plane{position:absolute;top:50%;left:0;width:50px;height:50px;transition: left 0.05s linear;}
</style>
</head>
<body>
<h1>Welcome, {{session['username']}}</h1>
<a href="{{url_for('logout')}}">Logout</a>

<div class="panel-row">
  <div class="panel">
    <div>Balance: $<span id="balance">0</span></div>
    <label>Bet $<input type="number" id="betInput" value="100" min="1"></label>
    <button id="placeBetBtn">Place Bet</button>
    <div id="currentBet">Current Bet: $0</div>
  </div>
  <div class="panel">
    <div>Multiplier: x<span id="multiplier">1.00</span></div>
    <div id="message"></div>
    <button id="cashoutBtn">Cash Out</button>
  </div>
</div>

<div style="position:relative;width:800px;height:200px;">
  <canvas id="historyChart" width="800" height="200"></canvas>
  <img id="plane" src="https://i.ibb.co/yR7m0qk/plane.png">
</div>

<script>
const socket=io();
let balance=0,currentMultiplier=1,currentBet=0;
let roundActive=false;

const balanceEl=document.getElementById("balance");
const multiplierEl=document.getElementById("multiplier");
const messageEl=document.getElementById("message");
const betInput=document.getElementById("betInput");
const cashoutBtn=document.getElementById("cashoutBtn");
const placeBetBtn=document.getElementById("placeBetBtn");
const currentBetEl=document.getElementById("currentBet");
const planeEl=document.getElementById("plane");

let historyData=[],historyLabels=[];
const ctx=document.getElementById("historyChart").getContext("2d");
const historyChart=new Chart(ctx,{type:'line',data:{labels:[],datasets:[{label:'Crash Multiplier',data:[],borderColor:'#0ff',backgroundColor:'rgba(0,255,255,0.2)',tension:0.3,fill:true}]},options:{responsive:false,scales:{y:{beginAtZero:true}}}});

socket.on("init",data=>{
    balance=data.balance;
    balanceEl.textContent=balance.toFixed(2);
    historyData=data.history;
    historyLabels=historyData.map((_,i)=>i+1);
    updateChart();
});

socket.on("new_round",data=>{
    roundActive=true;
    messageEl.textContent="New round started!";
    planeEl.style.left="0px";
});

socket.on("multiplier_update",data=>{
    currentMultiplier=data.multiplier;
    multiplierEl.textContent=currentMultiplier.toFixed(2);
    const percent=currentMultiplier/10;
    planeEl.style.left=Math.min(750, percent*800/10)+"px";
});

socket.on("round_crash",data=>{
    roundActive=false;
    messageEl.textContent="Flew away! x"+data.crash_point.toFixed(2);
    historyData.push(data.crash_point);
    if(historyData.length>50) historyData.shift();
    historyLabels=historyData.map((_,i)=>i+1);
    updateChart();
});

socket.on("cashout_result",data=>{
    balance=data.balance;
    balanceEl.textContent=balance.toFixed(2);
    messageEl.textContent="Cashed out: $"+data.win.toFixed(2);
    currentBet=0;
    currentBetEl.textContent="Current Bet: $0";
});

// --- Manual Bet ---
placeBetBtn.addEventListener("click", ()=>{
    if(!roundActive){
        messageEl.textContent="Wait for the next round!";
        return;
    }
    let bet=parseFloat(betInput.value);
    if(bet>0 && bet<=balance){
        currentBet=bet;
        currentBetEl.textContent="Current Bet: $"+currentBet.toFixed(2);
        messageEl.textContent="Bet placed!";
    } else {
        messageEl.textContent="Invalid bet!";
    }
});

// --- Cashout ---
cashoutBtn.addEventListener("click", ()=>{
    if(currentBet<=0){
        messageEl.textContent="Place a bet first!";
        return;
    }
    socket.emit("cashout",{"multiplier":currentMultiplier,"bet":currentBet});
});
function updateChart(){
    historyChart.data.labels=historyLabels;
    historyChart.data.datasets[0].data=historyData;
    historyChart.update();
}
</script>
</body>
</html>
""")

# --- Start game ---
socketio.start_background_task(game_loop)

if __name__=="__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
