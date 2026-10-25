from decimal import ROUND_HALF_UP, Decimal


def apply_discount(amount, percent):
    value = Decimal(amount) * (Decimal(100) - Decimal(percent)) / Decimal(100)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
