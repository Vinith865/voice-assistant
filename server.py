from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import Response
import httpx, base64

app = FastAPI()

SARVAM_API_KEY  = "your_sarvam_key_here"
OPENROUTER_KEY  = "your_openrouter_key_here"
FREE_MODEL      = "meta-llama/llama-3.1-8b-instruct:free"

LANG_NAMES = {
    "hi-IN":"Hindi","ta-IN":"Tamil","te-IN":"Telugu",
    "kn-IN":"Kannada","ml-IN":"Malayalam","en-IN":"English",
    "bn-IN":"Bengali","gu-IN":"Gujarati","mr-IN":"Marathi",
    "pa-IN":"Punjabi","od-IN":"Odia"
}

# ── STT ──────────────────────────────────────────────
def sarvam_stt(audio_bytes: bytes, language: str) -> str:
    try:
        r = httpx.post(
            "https://api.sarvam.ai/speech-to-text",
            headers={"api-subscription-key": SARVAM_API_KEY},
            files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            data={"model": "saarika:v2", "language_code": language},
            timeout=20
        )
        print(f"[STT RAW] {r.text}")
        return r.json().get("transcript", "")
    except Exception as e:
        print(f"[STT ERROR] {e}")
        return ""

# ── LLM ──────────────────────────────────────────────
def openrouter_chat(prompt: str, lang_name: str) -> str:
    try:
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
            },
            json={
                "model": FREE_MODEL,
                "messages": [
                    {"role": "system", "content": f"You are a helpful voice assistant. Reply concisely in {lang_name}. Keep reply under 3 sentences."},
                    {"role": "user",   "content": prompt}
                ],
                "max_tokens": 200
            },
            timeout=30
        )
        print(f"[LLM RAW] {r.text}")
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return "Sorry, I could not process that."

# ── TTS ──────────────────────────────────────────────
def sarvam_tts(text: str, language: str) -> bytes:
    try:
        r = httpx.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={
                "api-subscription-key": SARVAM_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "inputs": [text],
                "target_language_code": language,
                "speaker": "meera",
                "model": "bulbul:v2",
                "enable_preprocessing": True
            },
            timeout=20
        )
        print(f"[TTS STATUS] {r.status_code}")
        audio_b64 = r.json()["audios"][0]
        return base64.b64decode(audio_b64)
    except Exception as e:
        print(f"[TTS ERROR] {e}")
        return b""

# ── ENDPOINTS ─────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "Voice Assistant Server Running"}

@app.get("/ping")
def ping():
    return {"status": "alive"}

@app.post("/chat")
async def chat(
    audio: UploadFile,
    language: str = Form(default="hi-IN")
):
    audio_bytes = await audio.read()
    print(f"[CHAT] Received {len(audio_bytes)} bytes, lang={language}")

    transcript = sarvam_stt(audio_bytes, language)
    print(f"[TRANSCRIPT] {transcript}")

    if not transcript.strip():
        return Response(status_code=204)

    lang_name = LANG_NAMES.get(language, "English")
    reply     = openrouter_chat(transcript, lang_name)
    print(f"[REPLY] {reply}")

    wav_bytes = sarvam_tts(reply, language)
    if not wav_bytes:
        return Response(status_code=500)

    return Response(content=wav_bytes, media_type="audio/wav")
