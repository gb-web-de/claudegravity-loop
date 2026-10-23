def median(values):
    if not values:
        raise ValueError("median() braucht mindestens einen Wert")
    return values[len(values) // 2]
