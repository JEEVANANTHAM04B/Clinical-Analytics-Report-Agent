from pathlib import Path

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

VECTOR_STORE_DIR = (
    Path(__file__).resolve().parent.parent
    / "vector_store"
    / "langchain_store"
)


def create_retriever():
    embeddings = HuggingFaceEmbeddings(
        model_name=MODEL_NAME,
        model_kwargs={"device": "cpu"},
    )

    vector_store = FAISS.load_local(
        str(VECTOR_STORE_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )

    return vector_store.as_retriever(
        search_kwargs={"k": 1}
    )


if __name__ == "__main__":

    retriever = create_retriever()

    question = "What does readmission mean?"

    documents = retriever.invoke(question)

    print("Question:", question)
    print()

    for document in documents:
        print("Retrieved document:")
        print(document.page_content)
        print()
        print("Metadata:")
        print(document.metadata)