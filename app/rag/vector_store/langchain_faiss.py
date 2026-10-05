from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from app.rag.documents.document_loader import (
    load_documents,
    split_documents,
)


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

VECTOR_STORE_DIR = (
    Path(__file__).resolve().parent / "langchain_store"
)


def build_vector_store():
    # Load and split documents
    documents = load_documents()
    chunks = split_documents(documents)

    # Create Hugging Face embeddings
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME
    )

    # Create LangChain FAISS vector store
    vector_store = FAISS.from_documents(
        chunks,
        embeddings,
    )

    # Save locally
    vector_store.save_local(
        str(VECTOR_STORE_DIR)
    )

    print("LangChain FAISS vector store created")
    print("Documents:", len(documents))
    print("Chunks:", len(chunks))
    print("Vector store:", VECTOR_STORE_DIR)


if __name__ == "__main__":
    build_vector_store()