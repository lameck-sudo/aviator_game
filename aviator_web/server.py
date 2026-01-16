from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import asyncio
import json
import random
import time
import redis.asyncio as redis  # official redis asyncio
import numpy as np
from sklearn.linear_model import LinearRegression

app = FastAPI()
app.mount("/", StaticFiles(directory="web", html=True), name="web")

# ----------------------
# Redis connection
# ----------------------
REDIS_HOST = "localhost"
REDIS_PORT = 6379
redis_client = None

# ----------------------
# WebSocket connections
# ----------------------
connections = []

# ----------------------
# Game settings
# ----------------------
round_duration = 6  # seconds
round_interval = 2  # seconds between rounds
house_edge = 0.02   # optional house edge multiplier

# ----------------------
# AI Predictor
# ----------------------
def ai_predict(history):
    if len(history) < 5:
        return 1.0  # default prediction
    X = np.arange(len(history)).reshape(-1,1)
    y = np.array(history)
    model = LinearRegression().fit(X, y)
    return float(model.predict([[len(history)]]))

# ----------------------
# Helper functions
# ----------------------
async def broadcast(message: dict):
    for ws in connections:
        try:
            await ws.send_text(json.dumps(message))
        except:
            connections.remove(ws)

async def init_redis():
    global redis_client
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

async def get_user(user_id):
    user = await redis_client.hgetall(f"user:{user_id}")
    if not user:
        await redis_client.hset(f"user:{user_id}", mapping={"balance":1000,"bet":0,"cashed_out":0})
        user = await redis_client.hgetall(f"user:{user_id}")
    return {k:int(v) for k,v in user.items()}

async def update_user(user_id, field, value):
    await redis_client.hset(f"user:{user_id}", field, int(value))

async def add_history(multiplier):
    await redis_client.lpush("history", multiplier)
    await redis_client.ltrim("history", 0, 99)  # keep last 100 rounds
    return await redis_client.lrange("history", 0, 19)  # return last 20

# ----------------------
# WebSocket endpoint
# ----------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connections.append(ws)
    user_id = None
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg["action"] == "register":
                user_id = msg["user_id"]
                user = await get_user(user_id)
                await ws.send_text(json.dumps({"action":"update_balance","balance":user["balance"]}))

            elif msg["action"] == "bet" and user_id:
                user = await get_user(user_id)
                amount = msg["amount"]
                betting_open = await redis_client.get("betting_open")
                if amount > user["balance"]:
                    await ws.send_text(json.dumps({"action":"error","message":"Insufficient balance"}))
                    continue
                if betting_open != "1":
                    await ws.send_text(json.dumps({"action":"error","message":"Betting closed"}))
                    continue
                await update_user(user_id, "balance", user["balance"]-amount)
                await update_user(user_id, "bet", amount)
                await update_user(user_id, "cashed_out", 0)
                await ws.send_text(json.dumps({"action":"bet_confirmed","amount":amount}))

            elif msg["action"] == "cashout" and user_id:
                user = await get_user(user_id)
                if user["cashed_out"] == 1:
                    continue
                multiplier = float(await redis_client.get("current_multiplier"))
                payout = user["bet"] * multiplier
                await update_user(user_id, "balance", user["balance"] + payout)
                await update_user(user_id, "cashed_out", 1)
                await ws.send_text(json.dumps({"action":"cashed_out","payout":payout}))

    except WebSocketDisconnect:
        connections.remove(ws)

# ----------------------
# Game loop
# ----------------------
async def game_loop():
    while True:
        # Start round
        await redis_client.set("betting_open",1)
        await redis_client.set("current_multiplier",1.0)
        await broadcast({"action":"round_start","duration":round_duration})

        multiplier = 1.0
        ticks = int(round_duration*20)  # 50ms ticks
        for _ in range(ticks):
            await asyncio.sleep(0.05)
            multiplier += random.uniform(0.01,0.05)  # house edge
            await redis_client.set("current_multiplier", multiplier)
            await broadcast({"action":"update_multiplier","multiplier":round(multiplier,2)})

        # End round
        await redis_client.set("betting_open",0)
        last20 = await add_history(multiplier)
        # AI Predictor
        history_floats = list(map(float,last20))
        prediction = ai_predict(history_floats)
        await broadcast({"action":"round_end","final_multiplier":round(multiplier,2),
                         "history":history_floats,"prediction":round(prediction,2)})

        await asyncio.sleep(round_interval)

# ----------------------
# Startup event
# ----------------------
@app.on_event("startup")
async def startup_event():
    await init_redis()
    asyncio.create_task(game_loop())

