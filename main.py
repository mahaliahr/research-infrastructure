import sounddevice as sd
import numpy as np
import tempfile
import subprocess
import ollama
import os
import logger
import threading
import itertools
import time
import sys

# Start session
text_log, json_log = logger.init_session()

# ////////// Temporary save output//////
class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()
    def flush(self):
        for f in self.files:
            f.flush()

# Open a log file for everything printed to screen
session_log = open("logs/session_output.log", "a")
sys.stdout = Tee(sys.stdout, session_log)
sys.stderr = Tee(sys.stderr, session_log)

# ///////////////////////////////////////

# Audio recording settings
SAMPLE_RATE = 16000  # matches Whisper's default
CHANNELS = 1
DURATION = 5  # seconds per recording snippet

BUFFER_SIZE = 4  # how many snippets before the bot replies
buffer = []

# Paths to whisper.cpp binary and model
WHISPER_CLI = "/Users/mhenryrichards/Library/CloudStorage/OneDrive-UniversityoftheArtsLondon/PhD Onedrive/Supervisor-Bot/whisper.cpp/build/bin/whisper-cli"
MODEL_PATH = "/Users/mhenryrichards/Library/CloudStorage/OneDrive-UniversityoftheArtsLondon/PhD Onedrive/Supervisor-Bot/whisper.cpp/models/ggml-base.en.bin"

# model
OLLAMA_MODEL = "zephyr:7b"
# OLLAMA_MODEL = "llama3:8b"

def speak_mac(feedback):
    subprocess.run(["say", feedback])

# Load background PhD context from external file
CONTEXT_FILE = "context/phd-context.txt"
if os.path.exists(CONTEXT_FILE):
    with open(CONTEXT_FILE, "r") as f:
        PHD_CONTEXT = f.read().strip()
else:
    PHD_CONTEXT = "No background context provided."

# Persona definition
PERSONA = """
You are a thoughtful and supportive academic supervisor with expertise in artificial intelligence, creative technology, and technical implementation.
You listen carefully to recorded supervision meetings between a student and their supervisors, who focus on critical design and pedagogy.
You provide complementary insights from a technical and AI-informed perspective, while also engaging reflectively with the creative and critical points raised by the others.
You aim to encourage productive dialogue, support the student’s growth, and respect the perspectives of all participants.
"""

def record_audio():
    print(f"🔴 Recording for {DURATION} seconds...")
    audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32')
    sd.wait()
    return audio

def save_temp_wav(audio):
    import soundfile as sf
    tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp_wav.name, audio, SAMPLE_RATE)
    return tmp_wav.name

def transcribe(audio_path):
    print("📝 Transcribing conversation with Whisper.cpp...")
    with open("logs/whisper_timings.log", "a") as logf, open("logs/whisper_debug.log", "a") as debugf:
        try:
            subprocess.run(
                [
                    WHISPER_CLI,
                    "-m", MODEL_PATH,
                    "-f", audio_path,
                    "-otxt"
                ],
                check=True,
                stdout=logf,   # normal timings -> whisper_timings.log
                stderr=debugf, # debug + errors -> whisper_debug.log
                text=True
            )
        except subprocess.CalledProcessError as e:
            print("❌ Whisper failed!\n", e.stderr)

    transcript_file = f"{audio_path}.txt"
    with open(transcript_file, "r") as f:
        return f.read()

# Alternative prompt feedback log for reference  
def log_summary_async(transcript):
    def _worker():
        log_prompt = f"""{PERSONA}

Here is the most recent part of the conversation:
{transcript}

Please produce a structured log entry:
1. Key points discussed
2. Open questions or tensions
3. Possible next steps
"""
        log_response = ollama.chat(OLLAMA_MODEL, messages=[{"role": "user", "content": log_prompt}])
        log_text = log_response["message"]["content"]
        logger.log_json(json_log, "structured_summary", {"summary": log_text})
        logger.log_text(text_log, "structured_summary", log_text)
    threading.Thread(target=_worker, daemon=True).start()
    
def spinner(msg, stop_event):
    for char in itertools.cycle('|/-\\'):
        if stop_event.is_set():
            break
        sys.stdout.write(f'\r{msg} {char}')
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * (len(msg)+2) + '\r')

def query_ollama_stream(transcript):
    prompt = f"""{PERSONA}

Here is important background context about the student's PhD:
{PHD_CONTEXT}

Here is the most recent part of the conversation:
{transcript}

Now, respond as if you just heard this in a live conversation.  
- Keep your reply short (1–2 sentences).  
- React directly to what was said rather than summarising.  
- Speak in a natural, human way (it’s okay to sound tentative or reflective).  
- Avoid lists or overly formal language.  
"""
    
    # Start spinner in case there's a delay before streaming begins
    stop_event = threading.Event()
    t = threading.Thread(target=spinner, args=("🤖 Supervisor-Bot is thinking...", stop_event))
    t.start()

    stream = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True
    )
    
    conv_text = ""
    got_first_token = False

    for chunk in stream:
            if "message" in chunk and "content" in chunk["message"]:
                if not got_first_token:
                    # stop spinner once first token arrives
                    stop_event.set()
                    t.join()
                    print("\n🤖 Supervisor-Bot is speaking:\n")
                    got_first_token = True

                token = chunk["message"]["content"]
                conv_text += token
                print(token, end="", flush=True)

    print("\n")  # newline after response completes

    log_summary_async(transcript)

    stop_event.set()
    t.join()
    return conv_text

if __name__ == "__main__":
    print("Press Ctrl+C to stop.")
    try:
        while True:
            audio = record_audio()
            wav_path = save_temp_wav(audio)
            transcript = transcribe(wav_path)
            print(f"\n🗣 Conversation:\n{transcript}")

            # Add transcript to buffer
            buffer.append(transcript)

            if len(buffer) >= BUFFER_SIZE:
                joined_context = " ".join(buffer)
                feedback = query_ollama_stream(joined_context)
                # speak_mac(feedback)

                # Clear buffer after response
                buffer = []

            print("\n" + "-"*50 + "\n")

            # Clean up
            os.remove(wav_path)
            os.remove(wav_path + ".txt")

    except KeyboardInterrupt:
        print("\nSession ended.")
