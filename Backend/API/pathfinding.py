import heapq


def _is_coord(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(axis, int) for axis in value)
    )


def _neighbors(row, col, rows, cols):
    for next_row, next_col in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
        if 0 <= next_row < rows and 0 <= next_col < cols:
            yield next_row, next_col


def _heuristic(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _build_walkable_set(grid, goals):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    walkable = set()
    for row in range(rows):
        for col in range(cols):
            cell = grid[row][col]
            # Shelves are hard obstacles and are never walkable.
            if cell != 1:
                walkable.add((row, col))

    return walkable


def _pickup_endpoints_for_goal(goal, grid, walkable):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    goal_row, goal_col = goal

    endpoints = []
    for next_row, next_col in _neighbors(goal_row, goal_col, rows, cols):
        # Prefer picking from adjacent aisle/floor cells.
        if (next_row, next_col) in walkable and grid[next_row][next_col] != 1:
            endpoints.append((next_row, next_col))

    return endpoints


def _target_is_served(grid, route_point, target):
    point_row, point_col = route_point
    target_row, target_col = target

    # A target shelf is considered picked when the picker reaches an
    # adjacent non-shelf walkable cell.
    return (
        abs(point_row - target_row) + abs(point_col - target_col) == 1
        and grid[point_row][point_col] != 1
    )


def _a_star_segment(grid, start, goal, walkable):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    start_node = tuple(start)
    goal_node = tuple(goal)
    if start_node not in walkable or goal_node not in walkable:
        return []

    frontier = [(0, start_node)]
    came_from = {start_node: None}
    cost_so_far = {start_node: 0}

    while frontier:
        _, current = heapq.heappop(frontier)

        if current == goal_node:
            break

        for neighbor in _neighbors(current[0], current[1], rows, cols):
            if neighbor not in walkable:
                continue

            next_cost = cost_so_far[current] + 1
            if neighbor not in cost_so_far or next_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = next_cost
                priority = next_cost + _heuristic(neighbor, goal_node)
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current

    if goal_node not in came_from:
        return []

    path = []
    node = goal_node
    while node is not None:
        path.append([node[0], node[1]])
        node = came_from[node]

    path.reverse()
    return path


def calculate_a_star_route(grid, start, goals):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list):
        raise ValueError("grid must be a 2D list")

    if not _is_coord(start):
        raise ValueError("start must be [row, col]")

    if not isinstance(goals, list) or any(not _is_coord(goal) for goal in goals):
        raise ValueError("targets must be a list of [row, col] coordinates")

    if not goals:
        return [start], 0

    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("grid rows must have equal length")

    for point in [start, *goals]:
        if point[0] < 0 or point[1] < 0 or point[0] >= rows or point[1] >= cols:
            raise ValueError("start/targets include out-of-bounds coordinates")

    walkable = _build_walkable_set(grid, goals)

    remaining = [tuple(goal) for goal in goals]
    current = tuple(start)
    route = [[current[0], current[1]]]

    while remaining:
        selected_goal = None
        selected_endpoint = None
        selected_segment = None

        candidate_goals = sorted(remaining, key=lambda goal: _heuristic(current, goal))
        for candidate_goal in candidate_goals:
            endpoints = _pickup_endpoints_for_goal(candidate_goal, grid, walkable)
            endpoints = sorted(endpoints, key=lambda end: _heuristic(current, end))

            for endpoint in endpoints:
                segment = _a_star_segment(
                    grid,
                    [current[0], current[1]],
                    [endpoint[0], endpoint[1]],
                    walkable,
                )
                if segment:
                    selected_goal = candidate_goal
                    selected_endpoint = endpoint
                    selected_segment = segment
                    break

            if selected_segment:
                break

        if not selected_segment:
            nearest = min(remaining, key=lambda goal: _heuristic(current, goal))
            raise ValueError(f"No route found to target {list(nearest)}")

        route.extend(selected_segment[1:])
        current = selected_endpoint
        remaining.remove(selected_goal)

    validate_route_safety(grid, route, start, goals)
    return route, max(len(route) - 1, 0)


def validate_route_safety(grid, route, start, goals):
    if not isinstance(route, list) or any(not _is_coord(point) for point in route):
        raise ValueError("Invalid route format returned by pathfinder")

    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if tuple(route[0]) != tuple(start):
        raise ValueError("Route must start from the provided start point")

    for index, point in enumerate(route):
        row, col = point
        if row < 0 or col < 0 or row >= rows or col >= cols:
            raise ValueError("Route contains out-of-bounds coordinates")

        if grid[row][col] == 1:
            raise ValueError("Route crosses a shelf cell")

        if index == 0:
            continue

        prev_row, prev_col = route[index - 1]
        if abs(prev_row - row) + abs(prev_col - col) != 1:
            raise ValueError("Route contains non-adjacent movement")

    for goal in goals:
        if not any(_target_is_served(grid, route_point, tuple(goal)) for route_point in route):
            raise ValueError(f"Route never reaches a pickup position for target {list(goal)}")
