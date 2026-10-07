from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


DOCUMENT_PATH = Path(__file__).parent / "clinical_reference.txt"


def load_documents():
    text = DOCUMENT_PATH.read_text(encoding="utf-8")

    document = Document(
        page_content=text,
        metadata={
            "source": DOCUMENT_PATH.name,
            "document_type": "clinical_reference",
        },
    )

    return [document]


def split_documents(documents):
    chunks = []
    for doc in documents:
        paragraphs = [
            paragraph.strip()
            for paragraph in doc.page_content.split("\n\n")
            if paragraph.strip()
        ]
        for paragraph in paragraphs:
            chunks.append(
                Document(
                    page_content=paragraph,
                    metadata=doc.metadata.copy(),
                )
            )
    return chunks


if __name__ == "__main__":
    documents = load_documents()
    chunks = split_documents(documents)

    print("Documents loaded:", len(documents))
    print("Chunks created:", len(chunks))

    for i, chunk in enumerate(chunks, start=1):
        print(f"\n--- Chunk {i} ---")
        print(chunk.page_content)
        print("Metadata:", chunk.metadata)