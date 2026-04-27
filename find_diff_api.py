import random
import json
import collections
import sys
import os

# Ensure the parent of API is in path
sys.path.append(os.getcwd())

try:
    # Need to check how API.pathfinding is structured. Assuming it's a module.
    from API.pathfinding import calculate_route_with_alternatives
except ImportError:
    # Diagnostic: print where it looks
    print(f"ImportError. Current dir: {os.getcwd()}")
    print(f"Directory listing: {os.listdir('.')}")
    if os.path.exists('API'):
         print(f"API listing: {os.listdir('API')}")
    sys.exit(1)

def generate_connected_grid(rows, cols):
    while True:
        grid = [[random.choice([0, 1]) for _ in range(cols)] for _ in range(rows)]
        zeros = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 0]
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
        
        start_dict = {"x": start[0], "y": start[1]}
        targets_dicts = [{"x": t[0], "y": t[1]} for t in targets]
        
        try:
            # Note: The API might expect different grid formats or object types
            results = calculate_route_with_alternatives(grid, start_dict, targets_dicts, algorithms)
            
            distances = {}
            for alg in algorithms:
                if alg in results and results[alg] is not None:
                    # Logic to extract distance from the actual response structure
                    # Common structures: {'distance': X, ...} or {'total_distance': X, ...}
                    res = results[alg]
                    dist = res.get('total_distance') if isinstance(res, dict) else None
                    if dist is None and hasattr(res, 'total_distance'):
                        dist = res.total_distance
                    
                    if dist is not None:
                        distances[alg] = dist
                    else:
                        distances = None
                        break
                else:
                    distances = None
                    break
            
            if distances and len(set(distances.values())) > 1:
                print(json.dumps({"grid": grid, "start": start_dict, "targets": targets_dicts, "algorithms": algorithms}))
                print(json.dumps(distances))
                return
        except Exception as e:
            continue

if __name__ == "__main__":
    solve()
