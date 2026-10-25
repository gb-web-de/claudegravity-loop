class LRUCache:
    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity muss mindestens 1 sein")
        self.capacity = capacity
        self.items = {}

    def get(self, key, default=None):
        return self.items.get(key, default)

    def put(self, key, value):
        if len(self.items) >= self.capacity:
            oldest = next(iter(self.items))
            del self.items[oldest]
        self.items[key] = value

    def __len__(self):
        return len(self.items)
