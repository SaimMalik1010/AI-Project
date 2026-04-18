from engine.pathfinder import AStarPathfinder

# 0 = Floor, 1 = Shelf, 5 = Congested Aisle
warehouse_map = [
    [0, 0, 0, 0, 0],
    [0, 1, 1, 1, 0],
    [0, 0, 5, 0, 0],
    [0, 1, 1, 1, 0],
    [0, 0, 0, 0, 0]
]

def test_ai():
    solver = AStarPathfinder(warehouse_map)
    start = (0, 0)
    goal = (4, 4)
    
    path = solver.find_path(start, goal)
    
    if path:
        print(f"🚀 Path Found! Length: {len(path)} steps")
        for step in path:
            print(step)
    else:
        print("No path possible.")

if __name__ == "__main__":
    test_ai()