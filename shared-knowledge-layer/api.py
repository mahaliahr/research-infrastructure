import ollama
import chromadb
from fastapi import FastAPI
from pydantic import BaseModel

COLLECTION_NAME = "phd_notes"

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(COLLECTION_NAME)

app = FastAPI()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


def embed_text(text):
    response = ollama.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]


@app.post("/context")
def get_context(request: QueryRequest):
    query_embedding = embed_text(request.query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=request.top_k
    )

    chunks = []
    for i in range(len(results["documents"][0])):
        chunks.append({
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i]["source"],
            "heading": results["metadatas"][0][i]["heading"],
            "distance": results["distances"][0][i]
        })

    return {"query": request.query, "results": chunks}


@app.get("/health")
def health():
    return {"status": "ok", "chunks": collection.count()}