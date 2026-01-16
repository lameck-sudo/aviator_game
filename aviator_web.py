from flask import Flask, render_template_string
import random

app = Flask(__name__)

# ----- HTML template -----
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Aviator Web Simulator</title>
    <style>
        body { font-family: Arial; text-align: center; background: #f0f0f0; }
        #plane { font-size: 2em; }
        #multiplier { font-size: 1.5em; color: green; }
        #crash { font-size: 2em; color: red; display: none; }
        button { font-size: 1.2em; padding: 10px 20px; margin-top: 20px; }
    </style>
</head>
<body>
    <h1>🚀 Aviator Web Simulator</h1>
    <div id="plane">✈</div>
    <div id="multiplier">Multiplier: 1.0x</div>
    <div id="crash">💥 CRASH!</div>
    <button onclick="startGame()">Start Game</button>

    <script>
        let multiplier = 1.0;
        let crashNumber = Math.floor(Math.random()*20)+10;
        let running = false;
        let interval;

        function startGame() {
            multiplier = 1.0;
            crashNumber = Math.floor(Math.random()*20)+10;
            running = true;
            document.getElementById("crash").style.display = "none";

            if(interval) clearInterval(interval);

            interval = setInterval(() => {
                if(!running) return;

                multiplier += 0.1;
                document.getElementById("multiplier").innerText = "Multiplier: " + multiplier.toFixed(1) + "x";

                if(Math.floor(multiplier) === crashNumber) {
                    document.getElementById("crash").style.display = "block";
                    running = false;
                    clearInterval(interval);
                }
            }, 200);
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
