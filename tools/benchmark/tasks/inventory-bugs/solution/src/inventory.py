from pricing import apply_discount


class Inventory:
    def __init__(self):
        self.stock = {}
        self.prices = {}

    def add(self, item, qty, price):
        self.stock[item] = self.stock.get(item, 0) + qty
        self.prices[item] = price

    def remove(self, item, qty):
        if self.stock.get(item, 0) < qty:
            raise ValueError(f"zu wenig Bestand für {item}")
        self.stock[item] -= qty

    def total_value(self, discount_percent=0):
        total = sum(self.prices[i] * q for i, q in self.stock.items())
        return apply_discount(total, discount_percent)
