from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.rag.documents.document_loader import load_documents, split_documents


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

VECTOR_STORE_DIR = Path(__file__).parent


def build_vector_store():
    # 1. Load documents
    documents = load_documents()

    # 2. Split documents into chunks
    chunks = split_documents(documents)

    # 3. Load embedding model
    model = SentenceTransformer(MODEL_NAME)

    # 4. Convert chunks into embeddings
    texts = [chunk.page_content for chunk in chunks]

    embeddings = model.encode(texts)
    embeddings = np.array(embeddings).astype("float32")

    # 5. Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)

    # 6. Add embeddings
    index.add(embeddings)

    # 7. Save FAISS index
    index_path = VECTOR_STORE_DIR / "index.faiss"
    faiss.write_index(index, str(index_path))

    # Save chunk information separately
    chunks_path = VECTOR_STORE_DIR / "chunks.npy"

    np.save(
        chunks_path,
        np.array(texts, dtype=object),
        allow_pickle=True,
    )

    print("RAG vector store created successfully")
    print("Documents:", len(documents))
    print("Chunks:", len(chunks))
    print("Vectors:", index.ntotal)
    print("Vector dimension:", index.d)
    print("FAISS index:", index_path)
    print("Chunks file:", chunks_path)


if __name__ == "__main__":
    build_vector_store()