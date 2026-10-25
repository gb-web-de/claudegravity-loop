PAIRS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
         (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(n):
    if not isinstance(n, int) or not 1 <= n <= 3999:
        raise ValueError("Zahl muss zwischen 1 und 3999 liegen")
    out = []
    for value, sign in PAIRS:
        while n >= value:
            out.append(sign)
            n -= value
    return "".join(out)


def from_roman(text):
    if not isinstance(text, str) or not text:
        raise ValueError("leeres Zahlwort")
    total, i = 0, 0
    for value, sign in PAIRS:
        while text.startswith(sign, i):
            total += value
            i += len(sign)
    if i != len(text) or not 1 <= total <= 3999 or to_roman(total) != text:
        raise ValueError(f"ungültiges Zahlwort: {text}")
    return total
