import os
import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import openai
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- DATABASE SETUP ---
DB_FILE = "jarvis.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_message_to_db(role: str, content: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def load_history_from_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM messages")
    rows = cursor.fetchall()
    conn.close()
    
    # Always ensure the system prompt is first
    history = [{"role": "system", "content": "You are JARVIS, Felix Hofmeister's advanced AI assistant. You speak with sharp wit, complete loyalty, and concise language. Answer everything directly."}]
    for row in rows:
        history.append({"role": row[0], "content": row[1]})
    return history

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []

@app.get("/", response_class=HTMLResponse)
def get_index():
    if not os.getenv("OPENAI_API_KEY"):
        return "<h1>Error: OPENAI_API_KEY is missing in your .env file.</h1>"
    
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>JARVIS - Voice Interface</title>
    <style>
        html {
            background-color: #020b1c;
            height: 100%;
        }
        body {
            margin: 0;
            min-height: 100vh;
            background: linear-gradient(135deg, #020b1c, #001f3f, #004080);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px 20px;
            box-sizing: border-box;
            font-family: 'Courier New', Courier, monospace;
            color: #00ffff;
            overflow-y: auto;
        }
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        h1 {
            letter-spacing: 3px;
            text-shadow: 0 0 10px rgba(0,255,255,0.7);
            margin-bottom: 5px;
        }
        #status {
            font-size: 14px;
            color: #80f0ff;
            margin-bottom: 30px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .jarvis-core {
            width: 150px;
            height: 150px;
            min-width: 150px;
            min-height: 150px;
            border-radius: 50%;
            border: 3px solid rgba(0, 255, 255, 0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 30px rgba(0, 191, 255, 0.4);
            position: relative;
        }
        .ring {
            position: absolute;
            width: 130px;
            height: 130px;
            border-radius: 50%;
            border: 2px dashed rgba(0, 255, 255, 0.6);
            animation: spin 10s linear infinite;
        }
        .core-inner {
            width: 80px;
            height: 80px;
            background: radial-gradient(circle, #00ffff 0%, #0055ff 100%);
            border-radius: 50%;
            box-shadow: 0 0 20px #00ffff;
            transition: transform 0.1s ease;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .active-pulse {
            animation: pulse 1s ease infinite alternate;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 10px #00ffff; }
            100% { transform: scale(1.15); box-shadow: 0 0 40px #00ffff, 0 0 80px #0055ff; }
        }

        button {
            margin-top: 40px;
            background: transparent;
            border: 2px solid #00ffff;
            color: #00ffff;
            padding: 12px 30px;
            font-size: 16px;
            font-family: 'Courier New', Courier, monospace;
            cursor: pointer;
            border-radius: 4px;
            letter-spacing: 2px;
            box-shadow: 0 0 10px rgba(0,255,255,0.3);
            transition: 0.2s;
        }
        button:hover {
            background: #00ffff;
            color: #000;
            box-shadow: 0 0 25px #00ffff;
        }
        #transcript {
            margin-top: 25px;
            max-width: 600px;
            text-align: center;
            font-size: 14px;
            color: #cceeff;
            min-height: 40px;
            padding: 0 20px;
            word-break: break-word;
        }
    </style>
</head>
<body>

    <h1>J.A.R.V.I.S.</h1>
    <div id="status">System Offline</div>

    <div class="jarvis-core" id="core">
        <div class="ring"></div>
        <div class="core-inner" id="innerCore"></div>
    </div>

    <button id="toggleBtn" onclick="toggleJarvis()">INITIALIZE JARVIS</button>
    <div id="transcript">Click Initialize to boot up Jarvis.</div>

    <script>
        let recognition = null;
        let isRunning = false;
        let britishMaleVoice = null;

        function loadVoices() {
            if (!('speechSynthesis' in window)) return;
            const voices = window.speechSynthesis.getVoices();
            britishMaleVoice = voices.find(v => 
                (v.lang === 'en-GB' || v.lang.includes('en_GB')) && 
                (v.name.toLowerCase().includes('male') || v.name.toLowerCase().includes('daniel') || v.name.toLowerCase().includes('oliver') || v.name.toLowerCase().includes('george') || v.name.toLowerCase().includes('uk'))
            ) || voices.find(v => v.lang === 'en-GB' || v.lang.includes('en_GB')) 
              || voices.find(v => v.name.toLowerCase().includes('uk english') && v.name.toLowerCase().includes('male'))
              || voices[0];
        }

        if ('speechSynthesis' in window) {
            window.speechSynthesis.onvoiceschanged = loadVoices;
            loadVoices();
        }

        function toggleJarvis() {
            if (!isRunning) {
                if ('speechSynthesis' in window) {
                    window.speechSynthesis.cancel();
                    const unlockUtterance = new SpeechSynthesisUtterance("");
                    window.speechSynthesis.speak(unlockUtterance);
                }
                startJarvis();
            } else {
                stopJarvis();
            }
        }

        function startJarvis() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                alert("Speech recognition is not supported in this browser. Try Chrome.");
                return;
            }

            recognition = new SpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = true;
            recognition.lang = 'en-US';

            recognition.onstart = () => {
                document.getElementById('status').innerText = "Listening...";
                document.getElementById('innerCore').classList.add('active-pulse');
            };

            recognition.onresult = async (event) => {
                let interimTranscript = '';
                let finalTranscript = '';

                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }

                const currentSpeech = finalTranscript || interimTranscript;
                if (currentSpeech) {
                    document.getElementById('transcript').innerText = "You: " + currentSpeech;
                }

                if (finalTranscript) {
                    document.getElementById('status').innerText = "Processing...";

                    try {
                        const response = await fetch('/chat', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ message: finalTranscript })
                        });
                        
                        if (!response.ok) throw new Error("Server error");

                        const reader = response.body.getReader();
                        const decoder = new TextDecoder();
                        let fullReply = "";
                        
                        document.getElementById('transcript').innerText = "Jarvis: ";
                        document.getElementById('status').innerText = "Jarvis Speaking...";

                        while (true) {
                            const { value, done } = await reader.read();
                            if (done) break;
                            
                            const chunk = decoder.decode(value, { stream: true });
                            fullReply += chunk;
                            document.getElementById('transcript').innerText = "Jarvis: " + fullReply;
                        }

                        speak(fullReply);

                    } catch (err) {
                        console.error(err);
                        document.getElementById('status').innerText = "Error communicating with server.";
                    }
                }
            };

            recognition.onerror = (event) => {
                console.error(event.error);
                document.getElementById('status').innerText = "Listening paused. Click core to speak.";
            };

            recognition.onend = () => {
                if (isRunning) {
                    try { recognition.start(); } catch(e) {}
                }
            };

            isRunning = true;
            document.getElementById('toggleBtn').innerText = "DISCONNECT";
            document.getElementById('status').innerText = "Jarvis Online";
            recognition.start();
        }

        function speak(text) {
            if (!('speechSynthesis' in window)) return;
            
            window.speechSynthesis.cancel();
            loadVoices();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            utterance.pitch = 0.85;

            if (britishMaleVoice) {
                utterance.voice = britishMaleVoice;
            }

            utterance.onstart = () => {
                document.getElementById('status').innerText = "Jarvis Speaking...";
            };
            utterance.onend = () => {
                document.getElementById('status').innerText = "Listening...";
            };

            window.speechSynthesis.speak(utterance);
        }

        function stopJarvis() {
            isRunning = false;
            if (recognition) recognition.stop();
            if ('speechSynthesis' in window) window.speechSynthesis.cancel();
            document.getElementById('innerCore').classList.remove('active-pulse');
            document.getElementById('status').innerText = "System Offline";
            document.getElementById('toggleBtn').innerText = "INITIALIZE JARVIS";
            document.getElementById('transcript').innerText = "Session terminated.";
        }
    </script>
</body>
</html>
"""

@app.post("/chat")
def chat(data: ChatRequest):
    try:
        # Save user message to SQLite database
        save_message_to_db("user", data.message)

        # Pull complete chat history dynamically from SQLite database
        formatted_history = load_history_from_db()

        def generate():
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=formatted_history,
                stream=True
            )
            full_response_text = ""
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_response_text += delta
                    yield delta
            
            # Save assistant response to SQLite database once generation finishes
            save_message_to_db("assistant", full_response_text)

        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))