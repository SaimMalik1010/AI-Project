import json
import sys
import os
sys.path.append(os.getcwd())
try:
    from API.pathfinding import calculate_route_with_alternatives
except ImportError:
    print('Import Error')
    sys.exit(1)
def solve():
    grid = [[0, 0, 0, 0, 0], [0, 1, 1, 1, 0], [0, 1, 0, 1, 0], [0, 0, 0, 0, 0]]
    algos = ['A*', 'Greedy Best-First Search', 'Floyd-Warshall']
    for r in range(4):
        for c in range(5):
            if grid[r][c] == 0:
                start = [r, c]
                for tr in range(4):
                    for tc in range(5):
                        if grid[tr][tc] == 1:
                            targets = [[tr, tc]]
                            results = {}
                            for algo in algos:
                                try:
                                    res = calculate_route_with_alternatives(grid, start, targets, algorithm=algo)
                                    results[algo] = res.get('distance', -1)
                                except:
                                    results[algo] = -1
                            valid_dist = [v for v in results.values() if v > 0]
                            if len(set(valid_dist)) > 1:
                                print(json.dumps({'grid': grid, 'start': start, 'targets': targets, 'distances': results}))
                                return
solve()
