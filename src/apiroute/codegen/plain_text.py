import html
import re

_BREAKS = re.compile(r"<\s*(br|/p|/ul|/ol|/div|/h\d|/tr)\s*/?\s*>", re.IGNORECASE)
_ITEMS = re.compile(r"<\s*li[^>]*>", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")


def plain_text(text: str) -> str:
    """Spec descriptions as plain text for docstrings and comments. Many APIs (eBay's among
    them) write descriptions in HTML: breaks and paragraphs become new lines, list items
    become "- " lines, other tags are dropped and entities decoded."""
    if not text or "<" not in text and "&" not in text:
        return (text or "").strip()
    text = _BREAKS.sub("\n", text)
    text = _ITEMS.sub("\n- ", text)
    text = html.unescape(_TAGS.sub("", text))
    lines = [" ".join(line.split()) for line in text.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
