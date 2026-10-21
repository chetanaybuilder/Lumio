
import chromadb

from app.config import CHROMA_DIR
from app.gemini_client import EMBEDDING_DIMENSIONS

COLLECTION_NAME = "lumio_chunks"


def get_collection():
    """
    Initialize ChromaDB and return Lumio's collection.
    """

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    return collection


def store_chunks(
    document_id: str,
    chunks: list[dict],
    embeddings: list[list[float]],
    session_id: str,
) -> int:
    """
    Store text chunks, embeddings, and metadata in ChromaDB.
    Returns the number of chunks stored.
    """

    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError(
            "A valid document ID is required"
        )

    if len(chunks) != len(embeddings):
        raise ValueError(
            "The number of chunks must match the number of embeddings"
        )

    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for index, chunk in enumerate(chunks):
        text = chunk.get("text")

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"Chunk {index} has missing or empty text"
            )

        embedding = embeddings[index]

        if not embedding:
            raise ValueError(
                f"Chunk {index} has an empty embedding"
            )

        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Chunk {index} must have a {EMBEDDING_DIMENSIONS}-dimensional embedding"
            )

        chunk_id = f"{document_id}_chunk_{index}"

        source_pages = chunk.get("source_pages", [])
        section = chunk.get("section", "Unknown section")

        ids.append(chunk_id)
        documents.append(text)

        metadatas.append({
            "document_id": document_id,
            "session_id": session_id,
            "section": str(section),
            "source_pages": ",".join(
                str(page) for page in source_pages
            )
        })

    collection = get_collection()

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    return len(ids)


def query_chunks(session_id: str, document_id: str, embedding: list[float], limit: int = 6) -> list[dict]:
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError("Query embedding has an invalid dimension")
    result = get_collection().query(
        query_embeddings=[embedding],
        n_results=limit,
        where={"$and": [{"session_id": session_id}, {"document_id": document_id}]},
        include=["documents", "metadatas", "distances"],
    )
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    return [
        {"text": text, "metadata": metadata, "distance": distance}
        for text, metadata, distance in zip(documents, metadatas, distances)
    ]


def delete_document(document_id: str, session_id: str) -> None:
    """
    Delete all stored chunks belonging to one document.
    """

    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError(
            "A valid document ID is required"
        )

    collection = get_collection()

    collection.delete(where={"$and": [{"document_id": document_id}, {"session_id": session_id}]})


def clear_all_chunks() -> None:
    collection = get_collection()
    while identifiers := collection.get(limit=500, include=[])["ids"]:
        collection.delete(ids=identifiers)


# Every retrieval and cleanup operation is scoped to a session and document.