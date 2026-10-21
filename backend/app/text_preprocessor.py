import re


def clean_text(text: str) -> str:
    text = re.sub(r"[^\S\n]+", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_pages(pages: list) -> list:
    cleaned_pages = []
    for page in pages:
        cleaned_pages.append({
            "page": page["page"],
            "text": clean_text(page["text"])
        })
    return cleaned_pages


# Preserve extracted words while normalizing PDF layout noise.