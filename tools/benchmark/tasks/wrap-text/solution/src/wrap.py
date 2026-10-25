def _wrap_paragraph(words, width):
    lines, current = [], ""
    for word in words:
        while len(word) > width:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:width])
            word = word[width:]
        if not word:
            continue
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def wrap(text, width):
    if width < 1:
        raise ValueError("width muss mindestens 1 sein")
    result = []
    for i, paragraph in enumerate(text.split("\n\n")):
        if i:
            result.append("")
        result.extend(_wrap_paragraph(paragraph.split(), width))
    return result
