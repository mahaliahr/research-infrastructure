import sounddevice as sd
import numpy as np
import tempfile
import subprocess
import ollama
import os
import logger

# Start session
text_log, json_log = logger.init_session()

# Audio recording settings
SAMPLE_RATE = 16000  # matches Whisper's default
CHANNELS = 1
DURATION = 15  # seconds per recording snippet

# Paths to whisper.cpp binary and model
WHISPER_CLI = "/Users/mhenryrichards/Library/CloudStorage/OneDrive-UniversityoftheArtsLondon/PhD Onedrive/Supervisor-Bot/whisper.cpp/build/bin/whisper-cli"
MODEL_PATH = "/Users/mhenryrichards/Library/CloudStorage/OneDrive-UniversityoftheArtsLondon/PhD Onedrive/Supervisor-Bot/whisper.cpp/models/ggml-base.en.bin"

# model
OLLAMA_MODEL = "zephyr:7b"

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
    print("📝 Transcribing with Whisper.cpp...")
    with open("whisper_timings.log", "a") as logf, open("whisper_debug.log", "a") as debugf:
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

def query_ollama(transcript):
    prompt = f"""{PERSONA}

Here is important background context about the student's PhD:
{PHD_CONTEXT}

Here is the most recent part of the conversation:
{transcript}

Now, respond as if you were in the room as a fellow supervisor.
- Be concise and natural, no longer than 3–4 sentences.
- Do not summarize; instead, respond directly to the content of the conversation.
- Engage in a reflective and supportive way, adding insight from your technical/AI expertise when useful.
- Your tone should be collegial and conversational, not formal or evaluative.
"""

    conv_response = ollama.chat(OLLAMA_MODEL, messages=[{"role": "user", "content": prompt}])
    conv_text = conv_response["message"]["content"]

    # Structured summary (silent log only)
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

    # Log the structured summary silently (no printing)
    logger.log_json(json_log, "structured_summary", {"summary": log_text})
    logger.log_text(text_log, "structured_summary", log_text)

    return conv_text

if __name__ == "__main__":
    print("Press Ctrl+C to stop.")
    try:
        while True:
            audio = record_audio()
            wav_path = save_temp_wav(audio)
            transcript = transcribe(wav_path)
            print(f"\n🗣 Transcript:\n{transcript}")
            feedback = query_ollama(transcript)
            print("\n🤖 AI Supervisor Feedback:\n")
            print(feedback)
            print("\n" + "-"*50 + "\n")

            # Clean up
            os.remove(wav_path)
            os.remove(wav_path + ".txt")

            # Example logging (disabled in your snippet but left here for clarity)
            person_text = transcript
            bot_reply = feedback
            # logger.log_text(text_log, "person", person_text)
            # logger.log_json(json_log, "person_speech", {"text": person_text})
            # logger.log_text(text_log, "bot", bot_reply)
            # logger.log_json(json_log, "bot_interjection", {"reply": bot_reply})
    except KeyboardInterrupt:
        print("\nSession ended.")
