class Node:
    def __init__(self, x, y, weight=1, walkable=True):
        self.x = x
        self.y = y
        self.weight = weight   # Higher weight = congested area
        self.walkable = walkable
        self.parent = None     # For path reconstruction
        self.g = 0             # Cost from start to this node
        self.h = 0             # Heuristic (estimate to goal)
        self.f = 0             # Total cost (g + h)

    def __lt__(self, other):
        return self.f < other.f

    @property
    def pos(self):
        return (self.x, self.y)