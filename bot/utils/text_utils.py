from typing import List


def split_text_to_chunks(text: str, max_size: int = 4000) -> List[str]:
    chunks = []
    while len(text) > max_size:
        split_pos = text.rfind("\n", 0, max_size)
        if split_pos == -1:
            split_pos = text.rfind(" ", 0, max_size)
        if split_pos == -1:
            split_pos = max_size

        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].strip()

    if text:
        chunks.append(text)
    return chunks
