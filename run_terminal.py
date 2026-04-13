"""
run_terminal.py
Optional standalone terminal runner — preserves the v1 feel for when you
don't need the web UI. Uses the same pipeline and config as the server.
"""

import itertools
import os
import sys
import threading
import time

import logger as log_module
import pipeline
from config import BUFFER_SIZE

# ── Tee stdout → log file ─────────────────────────────────────────────────────
class Tee:
    def __init__(self, *files):
        self.files = files
    def write(self, obj):
        for f in self.files: f.write(obj); f.flush()
    def flush(self):
        for f in self.files: f.flush()

os.makedirs("logs", exist_ok=True)
_session_log = open("logs/terminal_output.log", "a")
sys.stdout = Tee(sys.stdout, _session_log)
sys.stderr = Tee(sys.stderr, _session_log)


# ── Spinner ───────────────────────────────────────────────────────────────────
def spinner(msg, stop_event):
    for char in itertools.cycle('|/-\\'):
        if stop_event.is_set(): break
        sys.stdout.write(f'\r{msg} {char}')
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * (len(msg) + 2) + '\r')


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    text_log, json_log = log_module.init_session()
    snippet_buffer = []

    print("Supervisor-Bot v1.5 — terminal mode")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            audio    = pipeline.record_audio()
            wav_path = pipeline.save_temp_wav(audio)
            transcript = pipeline.transcribe(wav_path)
            pipeline.cleanup_wav(wav_path)

            if transcript:
                snippet_buffer.append(transcript)
                print(f"\n🗣  {transcript}")
                log_module.log_text(text_log, "person", transcript)
                log_module.log_json(json_log, "transcript", {"text": transcript})

            if len(snippet_buffer) >= BUFFER_SIZE:
                joined = " ".join(snippet_buffer)

                stop_ev = threading.Event()
                t = threading.Thread(
                    target=spinner,
                    args=("🤖 Supervisor-Bot is thinking…", stop_ev)
                )
                t.start()

                full_reply = ""
                got_first  = False
                for token in pipeline.query_ollama_stream(joined):
                    if not got_first:
                        stop_ev.set(); t.join()
                        print("\n🤖 Supervisor-Bot:\n")
                        got_first = True
                    print(token, end="", flush=True)
                    full_reply += token

                print("\n\n" + "─" * 50 + "\n")

                log_module.log_text(text_log, "bot", full_reply)
                log_module.log_json(json_log, "bot_end", {"reply": full_reply})
                pipeline.log_summary_async(joined, text_log, json_log)

                snippet_buffer = []
                stop_ev.set()

    except KeyboardInterrupt:
        print("\nSession ended.")


if __name__ == "__main__":
    main()
