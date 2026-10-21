
from app.gemini_client import EMBEDDING_DIMENSIONS, embed_texts


BATCH_SIZE = 50


def generate_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate an embedding vector for one text.
    """

    if not isinstance(text, str):
        raise TypeError("Text must be a string")

    if not text.strip():
        raise ValueError("Text cannot be empty")

    try:
        return embed_texts([text], task_type)[0]
    except Exception as error:
        raise RuntimeError("Failed to generate embedding. Check Gemini availability and configuration.") from error


def generate_embeddings(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """
    Generate embedding vectors for multiple texts.
    """

    if not isinstance(texts, list):
        raise TypeError("Texts must be provided as a list")

    if not texts:
        return []

    for text in texts:
        if not isinstance(text, str):
            raise TypeError(
                "Every item in texts must be a string"
            )

        if not text.strip():
            raise ValueError(
                "Texts cannot contain empty strings"
            )

    try:
        embeddings = []
        for start in range(0, len(texts), BATCH_SIZE):
            embeddings.extend(embed_texts(texts[start:start + BATCH_SIZE], task_type))
        return embeddings
    except Exception as error:
        raise RuntimeError("Failed to generate embeddings. Check Gemini availability and configuration.") from error


# Document and query vectors share model dimensions but use distinct task types.