import re

UMLAUTS = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}


def slugify(text):
    text = text.lower()
    for char, repl in UMLAUTS.items():
        text = text.replace(char, repl)
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")
