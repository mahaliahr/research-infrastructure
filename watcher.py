import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os

VAULT_PATH = os.path.expanduser("~/Documents/GitHub/research-notes/src/site/notes")  


class VaultHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith(".md"):
            print(f"Change detected: {event.src_path}")
            self.reembed(event.src_path)

    def on_created(self, event):
        if event.src_path.endswith(".md"):
            print(f"New file: {event.src_path}")
            self.reembed(event.src_path)

    def reembed(self, filepath):
        subprocess.run(["python3", "embedder.py", filepath], check=True)


if __name__ == "__main__":
    print(f"Watching vault at {VAULT_PATH}")
    observer = Observer()
    observer.schedule(VaultHandler(), VAULT_PATH, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()