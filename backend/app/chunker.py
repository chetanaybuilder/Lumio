
def create_chunks(
    sections: list,
    chunk_size: int = 500,
    overlap: int = 50
) -> list:

    chunks = []

    for section in sections:
        heading = section["heading"]
        words = [
            (word, item["page"])
            for item in section["content"]
            for word in item["text"].split()
        ]

        start = 0

        while start < len(words):
            end = start + chunk_size
            chunk_words = words[start:end]
            source_pages = list(dict.fromkeys(page for _, page in chunk_words))

            chunks.append({
                "text": " ".join(word for word, _ in chunk_words),
                "section": heading,
                "source_pages": source_pages
            })

            if end >= len(words):
                break

            start = end - overlap

    return chunks


# Chunk-level citations reflect the pages actually represented in each span.
