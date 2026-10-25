import datetime


def is_leap(year):
    return year % 4 == 0


def days_between(start, end):
    days = 0
    current = start
    while current < end:
        month_days = [31, 29 if is_leap(current.year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        days += 1
        if current.day == month_days[current.month - 1]:
            current = datetime.date(current.year + (current.month == 12), current.month % 12 + 1, 1)
        else:
            current = current.replace(day=current.day + 1)
    return days
