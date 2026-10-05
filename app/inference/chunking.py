import re


WHATSAPP_START = re.compile(r"^\d{1,2}[/:.-]\d{1,2}[/:.-]\d{2,4}[^-]*?\s+-\s+[^:]+:\s+")


def split_source(text: str, max_chars: int = 9000) -> list[str]:
    """Split at WhatsApp message boundaries, preserving every original line."""
    lines = text.splitlines(keepends=True)
    if not lines:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in lines:
        if current and WHATSAPP_START.match(line) and len(current) + len(line) > max_chars:
            chunks.append(current)
            current = ""
        current += line
        if len(current) > max_chars and not WHATSAPP_START.match(line):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks or [text]
