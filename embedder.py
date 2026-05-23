import os
import hashlib
import re
import chromadb
import ollama

VAULT_PATH = os.path.expanduser("~/Documents/GitHub/research-notes/src/site/notes")  
COLLECTION_NAME = "phd_notes"

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(COLLECTION_NAME)


def get_file_hash(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return hashlib.md5(f.read().encode()).hexdigest()


def chunk_by_heading(text, source):
    chunks = []
    current_heading = "intro"
    current_lines = []

    for line in text.splitlines():
        if re.match(r"^#{1,3} ", line):
            if current_lines:
                chunks.append({
                    "heading": current_heading,
                    "text": "\n".join(current_lines).strip()
                })
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append({
            "heading": current_heading,
            "text": "\n".join(current_lines).strip()
        })

    # Split any chunks that are too long
    MAX_CHARS = 1500
    final_chunks = []
    for chunk in chunks:
        if len(chunk["text"]) <= MAX_CHARS:
            if len(chunk["text"]) > 40:
                final_chunks.append(chunk)
        else:
            words = chunk["text"].split()
            current, part = [], 0
            for word in words:
                current.append(word)
                if len(" ".join(current)) > MAX_CHARS:
                    final_chunks.append({
                        "heading": f"{chunk['heading']} (part {part})",
                        "text": " ".join(current[:-1])
                    })
                    current = [word]
                    part += 1
            if current:
                final_chunks.append({
                    "heading": f"{chunk['heading']} (part {part})",
                    "text": " ".join(current)
                })

    return final_chunks

def embed_text(text):
    response = ollama.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]


def process_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    file_hash = get_file_hash(filepath)
    filename = os.path.relpath(filepath, VAULT_PATH)
    chunks = chunk_by_heading(text, filename)

    # Remove any existing chunks from this file
    existing = collection.get(where={"source": filename})
    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    if not chunks:
        return

    ids, embeddings, documents, metadatas = [], [], [], []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{file_hash}_{i}"
        combined = f"{chunk['heading']}\n\n{chunk['text']}"
        ids.append(chunk_id)
        embeddings.append(embed_text(combined))
        documents.append(combined)
        metadatas.append({
            "source": filename,
            "heading": chunk["heading"],
            "hash": file_hash
        })

    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    print(f"Embedded {len(chunks)} chunks from {filename}")


def scan_vault():
    for root, _, files in os.walk(VAULT_PATH):
        for file in files:
            if file.endswith(".md"):
                process_file(os.path.join(root, file))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        print(f"Embedding single file: {filepath}")
        process_file(filepath)
        print("Done.")
    else:
        print("Scanning vault...")
        scan_vault()
        print("Done.")