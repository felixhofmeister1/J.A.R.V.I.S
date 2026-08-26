import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
app = FastAPI()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- SUPABASE SETUP ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_message_to_db(role: str, content: str):
    try:
        supabase.table("messages").insert({"role": role, "content": content}).execute()
    except Exception as e:
        print(f"Error saving to Supabase: {e}")

def load_history_from_db():
    try:
        response = supabase.table("messages").select("role, content").order("created_at", desc=True).limit(10).execute()
        rows = response.data
        if rows:
            rows.reverse()
    except Exception as e:
        print(f"Error loading from Supabase: {e}")
        rows = []
    
    history = [{"role": "system", "content": "You are JARVIS, Felix Hofmeister's advanced AI assistant. You speak with sharp wit, complete loyalty, and concise language. Answer everything directly. You have total and complete memory of every single past interaction stored in our database. If Felix asks about past conversations or anything you have ever discussed, you remember it with absolute clarity and state it directly. Never claim that you cannot remember or that each conversation is a separate session."}]
    for row in rows:
        history.append({"role": row["role"], "content": row["content"]})
    return history

class ChatRequest(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
def get_index():
    if not os.getenv("OPENAI_API_KEY") or not SUPABASE_URL:
        return "<h1>Error: OPENAI_API_KEY or Supabase credentials missing in your environment variables.</h1>"
    
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>JARVIS - Voice Interface</title>
    <style>
        html, body {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            background-color: #020b1c;
            background: linear-gradient(135deg, #020b1c, #001f3f, #004080);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            font-family: 'Courier New', Courier, monospace;
            color: #00ffff;
            overflow: hidden;
        }
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        .container {
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            box-sizing: border-box;
            padding: 20px;
        }

        h1 {
            letter-spacing: 4px;
            text-shadow: 0 0 15px rgba(0,255,255,0.8);
            margin: 0 0 6px 0;
            text-align: center;
        }

        #status {
            color: #80f0ff;
            text-transform: uppercase;
            letter-spacing: 2px;
            text-align: center;
            margin-bottom: 20px;
        }

        .jarvis-core {
            width: 160px;
            height: 160px;
            min-width: 160px;
            min-height: 160px;
            border-radius: 50%;
            border: 3px solid rgba(0, 255, 255, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 35px rgba(0, 191, 255, 0.5);
            position: relative;
            flex-shrink: 0;
        }

        .ring {
            position: absolute;
            width: 82%;
            height: 82%;
            border-radius: 50%;
            border: 2px dashed rgba(0, 255, 255, 0.7);
            animation: spin 10s linear infinite;
        }

        .core-inner {
            width: 50%;
            height: 50%;
            background: radial-gradient(circle, #00ffff 0%, #0055ff 100%);
            border-radius: 50%;
            box-shadow: 0 0 25px #00ffff;
            transition: transform 0.1s ease;
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .active-pulse {
            animation: pulse 1s ease infinite alternate;
        }
        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 15px #00ffff; }
            100% { transform: scale(1.15); box-shadow: 0 0 45px #00ffff, 0 0 90px #0055ff; }
        }

        button {
            background: transparent;
            border: 2px solid #00ffff;
            color: #00ffff;
            font-family: 'Courier New', Courier, monospace;
            cursor: pointer;
            border-radius: 4px;
            letter-spacing: 2px;
            box-shadow: 0 0 12px rgba(0,255,255,0.4);
            transition: 0.2s;
            margin-top: 25px;
            padding: 12px 28px;
            font-size: 15px;
            flex-shrink: 0;
        }
        button:hover {
            background: #00ffff;
            color: #000;
            box-shadow: 0 0 25px #00ffff;
        }

        #transcript {
            text-align: center;
            color: #cceeff;
            word-break: break-word;
            margin-top: 20px;
            width: 100%;
            max-width: 600px;
            max-height: 120px;
            overflow-y: auto;
            padding: 0 10px;
            box-sizing: border-box;
            scrollbar-width: thin;
            scrollbar-color: #00ffff rgba(0,31,63,0.5);
        }

        #transcript::-webkit-scrollbar {
            width: 6px;
        }
        #transcript::-webkit-scrollbar-thumb {
            background-color: #00ffff;
            border-radius: 3px;
        }

        @media screen and (max-width: 480px) {
            h1 { font-size: 26px; }
            #status { font-size: 11px; margin-bottom: 15px; }
            .jarvis-core { width: 130px; height: 130px; min-width: 130px; min-height: 130px; }
            button { margin-top: 20px; padding: 10px 20px; font-size: 13px; }
            #transcript { margin-top: 15px; font-size: 12px; max-height: 90px; }
        }
    </style>
</head>
<body>

    <div class="container">
        <h1>J.A.R.V.I.S.</h1>
        <div id="status">System Offline</div>

        <div class="jarvis-core" id="core">
            <div class="ring"></div>
            <div class="core-inner" id="innerCore"></div>
        </div>

        <button id="toggleBtn" onclick="toggleJarvis()">INITIALIZE JARVIS</button>
        <div id="transcript">Click Initialize to boot up Jarvis.</div>
    </div>

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

            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
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
                const transcriptDiv = document.getElementById('transcript');

                if (currentSpeech) {
                    if ('speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                    }
                    transcriptDiv.innerText = "You: " + currentSpeech;
                    transcriptDiv.scrollTop = transcriptDiv.scrollHeight;
                }

                if (finalTranscript) {
                    if ('speechSynthesis' in window) {
                        window.speechSynthesis.cancel();
                    }
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
                        
                        transcriptDiv.innerText = "Jarvis: ";
                        document.getElementById('status').innerText = "Jarvis Speaking...";

                        while (true) {
                            const { value, done } = await reader.read();
                            if (done) break;
                            
                            const chunk = decoder.decode(value, { stream: true });
                            fullReply += chunk;
                            transcriptDiv.innerText = "Jarvis: " + fullReply;
                            transcriptDiv.scrollTop = transcriptDiv.scrollHeight;
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
        save_message_to_db("user", data.message)
        formatted_history = load_history_from_db()

        def generate():
            response = client.chat.completions.create(
                model="gpt-5.4",
                messages=formatted_history,
                stream=True
            )
            full_response_text = ""
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if delta:
                    full_response_text += delta
                    yield delta
            
            save_message_to_db("assistant", full_response_text)

        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))