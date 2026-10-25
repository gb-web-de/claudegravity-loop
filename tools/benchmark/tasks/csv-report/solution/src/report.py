def totals_by_region(rows):
    totals = {}
    for row in rows:
        totals[row["region"]] = totals.get(row["region"], 0) + row["betrag"]
    return totals


def format_report(rows):
    totals = totals_by_region(rows)
    lines = ["Region      Summe"]
    for region, total in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"{region:<10} {str(total).replace('.', ','):>8}")
    return "\n".join(lines)
