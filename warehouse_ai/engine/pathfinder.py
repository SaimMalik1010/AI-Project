import heapq
from .utils import manhattan_distance

class AStarPathfinder:
    def __init__(self, grid_data):
        """
        grid_data: 2D array where 0 = walkable, 1 = shelf/wall, 
        integers > 1 = traffic cost.
        """
        self.grid_data = grid_data
        self.rows = len(grid_data)
        self.cols = len(grid_data[0])

    def get_neighbors(self, node, nodes_map):
        neighbors = []
        # Standard 4-direction movement (Up, Down, Left, Right)
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        
        for dx, dy in directions:
            nx, ny = node.x + dx, node.y + dy
            if 0 <= nx < self.rows and 0 <= ny < self.cols:
                neighbor = nodes_map[nx][ny]
                if neighbor.walkable:
                    neighbors.append(neighbor)
        return neighbors

    def find_path(self, start_pos, end_pos):
        # Create a fresh map of Node objects for each search
        nodes_map = [[Node(r, c, weight=self.grid_data[r][c], 
                           walkable=(self.grid_data[r][c] != 1)) 
                      for c in range(self.cols)] for r in range(self.rows)]
        
        start_node = nodes_map[start_pos[0]][start_pos[1]]
        end_node = nodes_map[end_pos[0]][end_pos[1]]
        
        open_list = []
        heapq.heappush(open_list, start_node)
        closed_set = set()

        while open_list:
            current = heapq.heappop(open_list)
            closed_set.add(current.pos)

            if current.pos == end_node.pos:
                return self.reconstruct_path(current)

            for neighbor in self.get_neighbors(current, nodes_map):
                if neighbor.pos in closed_set:
                    continue
                
                # tentative_g = current_g + move_cost (neighbor.weight)
                tentative_g = current.g + neighbor.weight
                
                if neighbor not in open_list or tentative_g < neighbor.g:
                    neighbor.parent = current
                    neighbor.g = tentative_g
                    neighbor.h = manhattan_distance(neighbor.pos, end_node.pos)
                    neighbor.f = neighbor.g + neighbor.h
                    
                    if neighbor not in open_list:
                        heapq.heappush(open_list, neighbor)
        return None # No path found

    def reconstruct_path(self, node):
        path = []
        while node:
            path.append(node.pos)
            node = node.parent
        return path[::-1] # Return from Start to Finish