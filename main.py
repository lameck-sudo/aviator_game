from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio, random

app = FastAPI()

# Allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with your GitHub Pages URL for security
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients = {}  # ws_id -> {"ws": WebSocket, "balance": float}
current_round = None
round_history = []

HOUSE_EDGE = 0.02
ROUND_DURATION = 12  # seconds
TICK_INTERVAL = 0.5   # seconds

# --- Round Class ---
class Round:
    def __init__(self):
        self.multiplier = 1.0
        self.active = True
        self.bets = {}        # ws_id -> bet amount
        self.cashouts = {}    # ws_id -> cashout multiplier

    async def run(self):
        global round_history
        ticks = int(ROUND_DURATION / TICK_INTERVAL)
        for _ in range(ticks):
            if not self.active:
                break
            await asyncio.sleep(TICK_INTERVAL)
            # RNG multiplier growth with house edge
            growth = random.uniform(0.01, 0.15)
            # Rare chance for high multiplier
            if random.random() < 0.05: growth *= 3
            self.multiplier *= (1 + growth)
            self.multiplier -= self.multiplier * HOUSE_EDGE
            await self.broadcast(update_only=True)
        # End round
        self.active = False
        # Settle bets
        for ws_id, bet in self.bets.items():
            cashout = self.cashouts.get(ws_id, self.multiplier)
            win = bet * cashout
            # Update client balance
            if ws_id in connected_clients:
                connected_clients[ws_id]["balance"] += win
            data = {
                "type": "round_update",
                "multiplier": round(self.multiplier,2),
                "roundOver": True,
                "balance": connected_clients[ws_id]["balance"] if ws_id in connected_clients else 0,
                "bet": bet,
                "cashout": round(cashout,2),
                "win": round(win,2)
            }
            await self.send_to_client(ws_id, data)
            round_history.append(data)

    async def broadcast(self, update_only=False):
        msg = {"type": "round_update", "multiplier": round(self.multiplier,2), "roundOver": False}
        for ws_id, info in connected_clients.items():
            if info["ws"].client_state.name != "CONNECTED": continue
            if update_only and ws_id not in self.bets: continue
            try:
                await info["ws"].send_json(msg)
            except:
                connected_clients.pop(ws_id, None)

    async def send_to_client(self, ws_id, msg):
        if ws_id in connected_clients:
            try:
                await connected_clients[ws_id]["ws"].send_json(msg)
            except:
                connected_clients.pop(ws_id, None)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_id = id(ws)
    connected_clients[ws_id] = {"ws": ws, "balance": 1000.0}
    try:
        while True:
            data = await ws.receive_json()
            if data["type"] == "place_bet":
                global current_round
                if current_round is None or not current_round.active:
                    current_round = Round()
                    asyncio.create_task(current_round.run())
                if ws_id in current_round.bets:
                    # prevent double betting in same round
                    await ws.send_json({"type":"error","message":"Already bet this round"})
                    continue
                bet = data["bet"]
                # check balance
                if bet <= 0 or bet > connected_clients[ws_id]["balance"]:
                    await ws.send_json({"type":"error","message":"Invalid bet"})
                    continue
                connected_clients[ws_id]["balance"] -= bet
                current_round.bets[ws_id] = bet
            elif data["type"] == "cash_out":
                if current_round and ws_id in current_round.bets and ws_id not in current_round.cashouts:
                    current_round.cashouts[ws_id] = current_round.multiplier
    except WebSocketDisconnect:
        connected_clients.pop(ws_id, None)
