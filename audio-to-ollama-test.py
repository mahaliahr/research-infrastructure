#!/usr/bin/env python3
import subprocess
import sys
import os

# Paths to whisper.cpp binary and model
WHISPER_MAIN = "/Users/mhenryrichards/Library/CloudStorage/OneDrive-UniversityoftheArtsLondon/PhD Onedrive/Supervisor-Bot/whisper.cpp/build/bin/main"
MODEL_PATH = "/Users/mhenryrichards/Library/CloudStorage/OneDrive-UniversityoftheArtsLondon/PhD Onedrive/Supervisor-Bot/whisper.cpp/models/ggml-base.en.bin"

# Persona definition
PERSONA = """
You are a thoughtful and supportive academic supervisor with expertise in artificial intelligence, creative technology, and technical implementation.
You listen carefully to recorded supervision meetings between a student and their supervisors, who focus on critical design and pedagogy.
You provide complementary insights from a technical and AI-informed perspective, while also engaging reflectively with the creative and critical points raised by the others.
You aim to encourage productive dialogue, support the student’s growth, and respect the perspectives of all participants.
"""

def transcribe(audio_file):
    print(f"Transcribing {audio_file}...")
    subprocess.run([
        WHISPER_MAIN,
        "-m", MODEL_PATH,
        "-f", audio_file,
        "-otxt"
    ], check=True)
    transcript_file = f"{audio_file}.txt"
    with open(transcript_file, "r") as f:
        return f.read()

def query_ollama(transcript):
    prompt = f"""{PERSONA}

From the conversation transcript below:
1. Summarize the main points raised by the supervisors and the student.
2. Identify any gaps, unanswered questions, or possible next steps.
3. Offer constructive feedback in 3–4 sentences.

--- Conversation Transcript ---
{transcript}
--- End Transcript ---

Keep your response under 200 words."""

    result = subprocess.run(
        ["ollama", "run", "llama3:8b"],
        input=prompt.encode('utf-8'),
        stdout=subprocess.PIPE
    )
    return result.stdout.decode('utf-8')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python supervisor.py <audiofile.wav>")
        sys.exit(1)

    audio_file = sys.argv[1]
    transcript = transcribe(audio_file)
    feedback = query_ollama(transcript)

    print("\n--- AI Supervisor Feedback ---\n")
    print(feedback)
