def manhattan_distance(start_pos, end_pos):
    """Calculates the L1 distance between two points."""
    return abs(start_pos[0] - end_pos[0]) + abs(start_pos[1] - end_pos[1])