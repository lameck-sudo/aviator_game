import asyncio
import random
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow frontend to connect from any origin (GitHub Pages / local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Connected clients
clients = []

# House edge setup
HOUSE_EDGE = 0.02  # 2%

# Multiplier probabilities
MULTIPLIER_RANGES = {
    "low": (1.1, 2.0),
    "medium": (2.0, 5.0),
    "rare": (5.0, 100.0)
}
PROBABILITIES = {
    "low": 0.6,
    "medium": 0.3,
    "rare": 0.1
}

def generate_multiplier():
    """Generate a multiplier based on probabilities and house edge"""
    r = random.random()
    if r < PROBABILITIES["low"]:
        m = random.uniform(*MULTIPLIER_RANGES["low"])
    elif r < PROBABILITIES["low"] + PROBABILITIES["medium"]:
        m = random.uniform(*MULTIPLIER_RANGES["medium"])
    else:
        m = random.uniform(*MULTIPLIER_RANGES["rare"])
    # Apply house edge
    return round(m * (1 - HOUSE_EDGE), 2)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            # Wait for client message
            data = await websocket.receive_text()
            if data == "start_game":
                multiplier = generate_multiplier()
                await websocket.send_text(str(multiplier))
    except WebSocketDisconnect:
        clients.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
