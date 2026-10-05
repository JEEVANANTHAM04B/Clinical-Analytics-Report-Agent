from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_embedding_model():
    model = SentenceTransformer(MODEL_NAME)
    return model


if __name__ == "__main__":
    model = load_embedding_model()

    texts = [
        "Length of stay is the number of days a patient remains admitted.",
        "Readmission means a patient is admitted again after discharge.",
    ]

    embeddings = model.encode(texts)

    print("Embedding model loaded successfully")
    print("Number of texts:", len(texts))
    print("Embedding shape:", embeddings.shape)
    print("First vector dimensions:", len(embeddings[0]))