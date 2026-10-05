from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

VECTOR_STORE_DIR = (
    Path(__file__).resolve().parent.parent / "vector_store"
)

INDEX_PATH = VECTOR_STORE_DIR / "index.faiss"
CHUNKS_PATH = VECTOR_STORE_DIR / "chunks.npy"


def load_retriever():
    # Load embedding model
    model = SentenceTransformer(MODEL_NAME)

    # Load saved FAISS index
    index = faiss.read_index(str(INDEX_PATH))

    # Load saved text chunks
    chunks = np.load(
        CHUNKS_PATH,
        allow_pickle=True,
    ).tolist()

    return model, index, chunks


def retrieve(query: str, top_k: int = 1):
    model, index, chunks = load_retriever()

    # Convert question into embedding
    query_embedding = model.encode([query])

    query_embedding = np.array(
        query_embedding
    ).astype("float32")

    # Search FAISS
    distances, indices = index.search(
        query_embedding,
        top_k,
    )

    results = []

    for distance, index_position in zip(
        distances[0],
        indices[0],
    ):
        results.append(
            {
                "text": chunks[index_position],
                "distance": float(distance),
            }
        )

    return results


if __name__ == "__main__":

    question = "What does readmission mean?"

    results = retrieve(question, top_k=1)

    print("Question:", question)
    print()

    for result in results:
        print("Retrieved document:")
        print(result["text"])
        print()
        print("Distance:", result["distance"])