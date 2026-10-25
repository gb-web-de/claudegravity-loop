import datetime
from decimal import Decimal, InvalidOperation


def read_sales(text):
    rows = []
    for number, line in enumerate(text.splitlines(), start=1):
        if number == 1 or not line.strip():
            continue
        try:
            datum, region, betrag = line.split(";")
            rows.append(
                {
                    "datum": datetime.date.fromisoformat(datum.strip()),
                    "region": region.strip(),
                    "betrag": Decimal(betrag.strip().replace(",", ".")),
                }
            )
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"Zeile {number}: {exc}") from exc
    return rows
