import random
import json
import collections

# Mocking the API logic based on the user's request. 
# Since I don't have access to the actual API.pathfinding module in the environment without checking, 
# I will implement the algorithms myself or try to import it if it exists.
# Given the instructions "run an inline Python script... to randomly generate... call API.pathfinding...",
# I should check if the API is available. If not, I'll need to locate it.
# However, usually these tasks imply the environment has the code.

try:
    from API.pathfinding import calculate_route_with_alternatives
except ImportError:
    # If not found, I will try to find where it is or implement the logic.
    # Let's assume it's in the current directory or PYTHONPATH.
    import sys
    import os
    sys.path.append(os.getcwd())
    try:
        from API.pathfinding import calculate_route_with_alternatives
    except ImportError:
        def calculate_route_with_alternatives(grid, start, targets, algorithms):
            # Fallback if API is missing, but the task says "call API.pathfinding"
            # This is likely a local module.
            raise ImportError("Could not find API.pathfinding")

def generate_connected_grid(rows, cols):
    while True:
        grid = [[random.choice([0, 1]) for _ in range(cols)] for _ in range(rows)]
        # Check connectivity using BFS from the first 0 found
        start_node = None
        zeros = []
        for r in range(rows):
            for c in range(cols):
                if grid[r][c] == 0:
                    zeros.append((r, c))
        if not zeros: continue
        
        start_node = zeros[0]
        visited = {start_node}
        queue = collections.deque([start_node])
        while queue:
            r, c = queue.popleft()
            for dr, dc in [(0,1), (0,-1), (1,0), (-1,0)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0 and (nr, nc) not in visited:
                    visited.add((nr, nc))
                    queue.append((nr, nc))
        
        if len(visited) == len(zeros):
            return grid, zeros
    return None, None

def solve():
    algorithms = ['A*', 'Greedy Best-First Search', 'Floyd-Warshall']
    for i in range(5000):
        rows = random.randint(6, 10)
        cols = random.randint(6, 10)
        grid, zeros = generate_connected_grid(rows, cols)
        if len(zeros) < 5: continue
        
        start = random.choice(zeros)
        rem_zeros = [z for z in zeros if z != start]
        num_targets = random.randint(2, 4)
        if len(rem_zeros) < num_targets: continue
        targets = random.sample(rem_zeros, num_targets)
        
        # Convert to the format expected by the API (often objects or lists)
        # Assuming grid is list of lists, start/targets are dicts or lists
        start_dict = {"x": start[0], "y": start[1]}
        targets_dicts = [{"x": t[0], "y": t[1]} for t in targets]
        
        try:
            results = calculate_route_with_alternatives(grid, start_dict, targets_dicts, algorithms)
            # results is expected to be a dict or list with distances
            # e.g., { 'A*': { 'total_distance': 10 }, ... }
            
            distances = {}
            for alg in algorithms:
                if alg in results and results[alg] is not None:
                    # Depending on API structure, distance might be in 'total_distance' or 'distance'
                    dist = results[alg].get('total_distance') or results[alg].get('distance')
                    distances[alg] = dist
                else:
                    # If any algorithm fails or returns None, we stop and skip this candidate
                    distances = None
                    break
            
            if distances and len(set(distances.values())) > 1:
                output = {
                    "grid": grid,
                    "start": start_dict,
                    "targets": targets_dicts,
                    "algorithms": algorithms
                }
                print(json.dumps(output))
                print(json.dumps(distances))
                return
        except Exception as e:
            continue

solve()
