from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random

app = FastAPI()

# Allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # can restrict to your GitHub Pages URL later
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GAME VARIABLES ---
connected_clients = []
current_round = None
round_history = []

HOUSE_EDGE = 0.02  # 2% edge
ROUND_DURATION = 10  # seconds

# --- Round Class ---
class Round:
    def __init__(self):
        self.multiplier = 1.0
        self.active = True
        self.bets = {}  # client_id -> bet amount
        self.cashouts = {}  # client_id -> cashout multiplier

    async def run(self):
        global round_history
        for _ in range(ROUND_DURATION * 2):  # update 0.5s
            if not self.active:
                break
            await asyncio.sleep(0.5)
            # simple RNG: increase multiplier with slight randomness + house edge
            self.multiplier *= 1 + random.uniform(0.01, 0.08)
            self.multiplier -= self.multiplier * HOUSE_EDGE
            # broadcast
            data = {"type": "round_update", "multiplier": self.multiplier, "roundOver": False, "balance": None}
            await broadcast(data)
        # end round
        self.active = False
        # calculate wins
        for client_id, bet in self.bets.items():
            cashout = self.cashouts.get(client_id, self.multiplier)
            win = bet * cashout
            data = {"type": "round_update", "multiplier": round(self.multiplier,2), "roundOver": True,
                    "balance": win, "bet": bet, "cashout": round(cashout,2), "win": win}
            round_history.append(data)
            await send_to_client(client_id, data)

async def broadcast(message):
    for client in connected_clients:
        try:
            await client.send_json(message)
        except:
            connected_clients.remove(client)

async def send_to_client(client_id, message):
    for client in connected_clients:
        if id(client) == client_id:
            try:
                await client.send_json(message)
            except:
                connected_clients.remove(client)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    client_id = id(ws)
    try:
        while True:
            data = await ws.receive_json()
            if data["type"] == "place_bet":
                global current_round
                if current_round is None or not current_round.active:
                    current_round = Round()
                    asyncio.create_task(current_round.run())
                current_round.bets[client_id] = data["bet"]
            elif data["type"] == "cash_out":
                if current_round and client_id in current_round.bets:
                    current_round.cashouts[client_id] = current_round.multiplier
    except WebSocketDisconnect:
        connected_clients.remove(ws)
