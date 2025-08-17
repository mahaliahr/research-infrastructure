#!/usr/bin/env python3
import subprocess
import sys
import os

# Paths to whisper.cpp binary and model
WHISPER_CLI = "/Users/mhenryrichards/Library/CloudStorage/OneDrive-UniversityoftheArtsLondon/PhD Onedrive/Supervisor-Bot/whisper.cpp/build/bin/whisper-cli"
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
    try:
        subprocess.run([
            WHISPER_CLI,
            "-m", MODEL_PATH,
            "-f", audio_file,
            "-otxt"
        ], check=True)
    except FileNotFoundError:
        print(f"❌ Error: Whisper binary not found at {WHISPER_CLI}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Whisper failed with error code {e.returncode}")
        sys.exit(1)

    transcript_file = f"{audio_file}.txt"
    if not os.path.exists(transcript_file):
        print(f"❌ Error: Transcript file {transcript_file} not created.")
        sys.exit(1)

    with open(transcript_file, "r") as f:
        return f.read()

# --- if I need to debug
# def transcribe(audio_file):
#     print(f"Transcribing {audio_file}...")
#
#     transcript_file = f"{audio_file}.txt"
#
#     try:
#         result = subprocess.run([
#             WHISPER_CLI,
#             "-m", MODEL_PATH,
#             "-f", audio_file,
#             "-otxt"
#         ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
#
#         print(">>> Whisper stdout:\n", result.stdout.decode('utf-8'))
#         print(">>> Whisper stderr:\n", result.stderr.decode('utf-8'))
#
#         if os.path.exists(transcript_file):
#             with open(transcript_file, "r") as f:
#                 content = f.read().strip()
#                 print(">>> Transcript content:\n", content[:200], "..." if len(content) > 200 else "")
#                 return content
#         else:
#             print("No transcript file created at:", transcript_file)
#             return ""
#     except subprocess.CalledProcessError as e:
#         print("Whisper failed!")
#         print("stderr:\n", e.stderr.decode('utf-8') if e.stderr else "None")
#         return ""


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

    try:
        result = subprocess.run(
            ["ollama", "run", "llama3:8b"],
            input=prompt.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print(">>> Ollama stderr:\n", result.stderr.decode('utf-8'))
        print(">>> Ollama raw stdout:\n", result.stdout.decode('utf-8'))
        return result.stdout.decode('utf-8')
    except subprocess.CalledProcessError as e:
        print("Ollama call failed!")
        print("stderr:\n", e.stderr.decode('utf-8') if e.stderr else "None")
        return ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python supervisor.py <audiofile.wav>")
        sys.exit(1)

    audio_file = sys.argv[1]

    if not os.path.exists(audio_file):
        print(f"❌ Error: Audio file {audio_file} does not exist.")
        sys.exit(1)

    transcript = transcribe(audio_file)
    feedback = query_ollama(transcript)

    print("\n--- AI Supervisor Feedback ---\n")
    print(feedback)
