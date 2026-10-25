from pricing import apply_discount


class Inventory:
    def __init__(self):
        self.stock = {}
        self.prices = {}

    def add(self, item, qty, price):
        self.stock[item] = self.stock.get(item, 0) + qty
        self.prices[item] = price

    def remove(self, item, qty):
        self.stock[item] = self.stock.get(item, 0) - qty

    def total_value(self, discount_percent=0):
        total = sum(self.prices[i] for i in self.stock)
        return apply_discount(total, discount_percent)
