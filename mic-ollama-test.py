import sounddevice as sd
import numpy as np
import tempfile
import subprocess
import ollama
import os

# Persona definition
PERSONA = """
You are a thoughtful and supportive academic supervisor with expertise in artificial intelligence, creative technology, and technical implementation.
You listen carefully to recorded supervision meetings between a student and their supervisors, who focus on critical design and pedagogy.
You provide complementary insights from a technical and AI-informed perspective, while also engaging reflectively with the creative and critical points raised by the others.
You aim to encourage productive dialogue, support the student’s growth, and respect the perspectives of all participants.
"""

# Audio recording settings
SAMPLE_RATE = 16000  # matches Whisper's default
CHANNELS = 1
DURATION = 15  # seconds per recording snippet

def record_audio():
    print(f"🎙 Recording for {DURATION} seconds...")
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
    subprocess.run([
        "./main",  # path to whisper.cpp executable
        "-m", "models/ggml-base.en.bin",
        "-f", audio_path,
        "-otxt"
    ], check=True)
    transcript_file = f"{audio_path}.txt"
    with open(transcript_file, "r") as f:
        return f.read()

def query_ollama(transcript):
    prompt = f"""{PERSONA}

From the conversation snippet below:
1. Summarize the main points.
2. Identify any gaps or next steps.
3. Offer constructive feedback in 3–4 sentences.

--- Conversation ---
{transcript}
--- End Transcript ---
"""

    response = ollama.chat(model="llama3:8b", messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]

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
            os.remove(wav_path)  # clean up temp files
            os.remove(wav_path + ".txt")
    except KeyboardInterrupt:
        print("\nSession ended.")
