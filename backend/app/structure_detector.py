
import re


def detect_structure(pages: list) -> list:
    sections = []
    current_section = None

    for page in pages:
        page_number = page["page"]
        text = page["text"]

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            is_heading = (
                re.match(r"^Chapter\s+\d+", line, re.IGNORECASE)
                or re.match(r"^\d+(\.\d+)*\s+", line)
            )

            if is_heading:
                current_section = {
                    "heading": line,
                    "start_page": page_number,
                    "content": []
                }

                sections.append(current_section)

            else:
                if current_section is None:
                    current_section = {
                        "heading": "Document Content",
                        "start_page": page_number,
                        "content": []
                    }

                    sections.append(current_section)

                current_section["content"].append({
                    "page": page_number,
                    "text": line
                })

    return sections