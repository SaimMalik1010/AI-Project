class Node:
    """Represents a node in the pathfinding grid."""
    def __init__(self, x, y, weight=0, walkable=True):
        self.x = x
        self.y = y
        self.pos = (x, y)
        self.weight = weight
        self.walkable = walkable
        self.g = float('inf')  # Cost from start
        self.h = 0             # Heuristic cost to goal
        self.f = float('inf')  # Total cost (g + h)
        self.parent = None

    def __lt__(self, other):
        """For heapq comparison based on f-score."""
        return self.f < other.f

    def __eq__(self, other):
        """Equality based on position."""
        return self.pos == other.pos if isinstance(other, Node) else False

    def __hash__(self):
        """Hash based on position for set operations."""
        return hash(self.pos)


def manhattan_distance(start_pos, end_pos):
    """Calculates the L1 distance between two points."""
    return abs(start_pos[0] - end_pos[0]) + abs(start_pos[1] - end_pos[1])