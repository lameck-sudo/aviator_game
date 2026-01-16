from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import random
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

history = []
round_number = 1

user_balance = 1000  # starting coins

with open("static/index.html") as f:
    html_content = f.read()

@app.get("/")
async def get():
    return HTMLResponse(html_content)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global history, round_number, user_balance
    await ws.accept()

    crash_multiplier = round(random.uniform(1.0, 1_000_000.0), 2)
    current_multiplier = 1.0
    user_bet = 0
    cashed_out = False

    await ws.send_json({
        "type": "init",
        "round": round_number,
        "history": history,
        "balance": user_balance
    })

    while True:
        try:
            msg = await ws.receive_json()
            if msg.get("action") == "deposit":
                user_balance += float(msg.get("amount", 0))
                await ws.send_json({"type": "balance_update", "balance": user_balance})
            elif msg.get("action") == "bet":
                bet_amount = float(msg.get("amount", 0))
                if bet_amount <= user_balance:
                    user_balance -= bet_amount
                    user_bet = bet_amount
                    cashed_out = False
                await ws.send_json({"type": "balance_update", "balance": user_balance})
            elif msg.get("action") == "cashout" and not cashed_out:
                payout = round(user_bet * current_multiplier, 2)
                user_balance += payout
                user_bet = 0
                cashed_out = True
                await ws.send_json({"type": "balance_update", "balance": user_balance, "cashed_out": payout})

            # update multiplier
            current_multiplier = round(current_multiplier + random.uniform(0.05, 100.0), 2)

            # crash
            if current_multiplier >= crash_multiplier:
                history.append(crash_multiplier)
                await ws.send_json({
                    "type": "crash",
                    "multiplier": crash_multiplier,
                    "history": history
                })
                round_number += 1
                crash_multiplier = round(random.uniform(1.0, 1_000_000.0), 2)
                current_multiplier = 1.0
                user_bet = 0
                cashed_out = False
                await asyncio.sleep(1)
                await ws.send_json({
                    "type": "reset",
                    "round": round_number,
                    "multiplier": current_multiplier,
                    "history": history,
                    "balance": user_balance
                })
            else:
                await ws.send_json({"type": "update", "multiplier": current_multiplier})

            await asyncio.sleep(0.5)

        except:
            break
