def is_leap(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_between(start, end):
    if end < start:
        raise ValueError("end liegt vor start")
    return (end - start).days + 1
