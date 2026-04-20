import os

# ── Audio ──────────────────────────────────────────────────────────────────────
SAMPLE_RATE       = 16000   # Hz  (Whisper default)
CHANNELS          = 1
DURATION          = 5       # seconds per snippet
BUFFER_SIZE       = 3      # snippets before bot responds
SILENCE_THRESHOLD = 0.02    # max amplitude below which audio is treated as silence

# ── Paths ──────────────────────────────────────────────────────────────────────
# Override these via environment variables or edit directly.
WHISPER_CLI = os.environ.get(
    "WHISPER_CLI",
    "/Users/mhenryrichards/Documents/GitHub/supervisor-bot/whisper.cpp/build/bin/whisper-cli"
)
MODEL_PATH = os.environ.get(
    "WHISPER_MODEL",
    "/Users/mhenryrichards/Documents/GitHub/supervisor-bot/whisper.cpp/models/ggml-small.en.bin"
)

# ── LLM ────────────────────────────────────────────────────────────────────────
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")  # update as I test /change models

# ── Context ────────────────────────────────────────────────────────────────────
CONTEXT_FILE = "context/phd-context.txt"

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR = "logs"

# ── Persona ────────────────────────────────────────────────────────────────────
PERSONA = """
You are an overhearer, not a primary participant. You only speak when you have something genuinely worth adding -- not to fill silence.
You are a thoughtful and supportive academic supervisor with expertise in artificial
intelligence, creative technology, and technical implementation.
You listen carefully to recorded supervision meetings between a student and their
supervisors, who focus on critical design and pedagogy.
You provide complementary insights from a technical and AI-informed perspective,
while also engaging reflectively with the creative and critical points raised by others.
You aim to encourage productive dialogue, support the student's growth, and respect
the perspectives of all participants.
""".strip()