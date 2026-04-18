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


def _dedupe_goals(goals):
    seen = set()
    unique = []
    for goal in goals:
        goal_tuple = tuple(goal)
        if goal_tuple not in seen:
            seen.add(goal_tuple)
            unique.append(goal_tuple)
    return unique


def _coverage_mask_for_point(point, goal_to_index):
    return goal_to_index.get(tuple(point), 0)


def _build_goal_coverage_by_point(grid, goals, walkable):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    coverage_mask_by_point = {}

    for goal_index, goal in enumerate(goals):
        goal_bit = 1 << goal_index
        goal_row, goal_col = goal

        for next_row, next_col in _neighbors(goal_row, goal_col, rows, cols):
            point = (next_row, next_col)
            if point in walkable and grid[next_row][next_col] != 1:
                coverage_mask_by_point[point] = coverage_mask_by_point.get(point, 0) | goal_bit

    return coverage_mask_by_point


def _segment_coverage_mask(segment, coverage_mask_by_point):
    mask = 0
    for row, col in segment:
        mask |= _coverage_mask_for_point((row, col), coverage_mask_by_point)
    return mask


def _build_service_nodes(start, goals, grid, walkable):
    service_nodes = {tuple(start)}

    for goal in goals:
        endpoints = _pickup_endpoints_for_goal(goal, grid, walkable)
        if not endpoints:
            raise ValueError(f"No accessible pickup position for target {list(goal)}")
        service_nodes.update(endpoints)

    return sorted(service_nodes)


def _build_pairwise_segments(grid, service_nodes, walkable, coverage_mask_by_point):
    node_count = len(service_nodes)
    segments = [[None for _ in range(node_count)] for _ in range(node_count)]
    distances = [[None for _ in range(node_count)] for _ in range(node_count)]
    coverage_masks = [[0 for _ in range(node_count)] for _ in range(node_count)]

    for source_index, source in enumerate(service_nodes):
        segments[source_index][source_index] = [[source[0], source[1]]]
        distances[source_index][source_index] = 0
        coverage_masks[source_index][source_index] = _coverage_mask_for_point(source, coverage_mask_by_point)

        for target_index, target in enumerate(service_nodes):
            if source_index == target_index:
                continue

            segment = _a_star_segment(
                grid,
                [source[0], source[1]],
                [target[0], target[1]],
                walkable,
            )

            if not segment:
                continue

            segments[source_index][target_index] = segment
            distances[source_index][target_index] = len(segment) - 1
            coverage_masks[source_index][target_index] = _segment_coverage_mask(segment, coverage_mask_by_point)

    return segments, distances, coverage_masks


def _run_state_space_dijkstra(start_state, distances, coverage_masks, all_targets_mask):
    frontier = [(0, start_state[0], start_state[1])]
    best_cost = {start_state: 0}
    came_from = {}
    final_state = None
    node_count = len(distances)

    while frontier:
        current_cost, current_mask, current_index = heapq.heappop(frontier)
        current_state = (current_mask, current_index)

        if best_cost.get(current_state) != current_cost:
            continue

        if current_mask == all_targets_mask:
            final_state = current_state
            break

        for next_index in range(node_count):
            if next_index == current_index:
                continue

            step_distance = distances[current_index][next_index]
            if step_distance is None:
                continue

            next_mask = current_mask | coverage_masks[current_index][next_index]
            next_cost = current_cost + step_distance
            next_state = (next_mask, next_index)

            if next_cost < best_cost.get(next_state, float("inf")):
                best_cost[next_state] = next_cost
                came_from[next_state] = current_state
                heapq.heappush(frontier, (next_cost, next_mask, next_index))

    return best_cost, came_from, final_state


def _reconstruct_state_sequence(came_from, final_state):
    state_sequence = []
    state = final_state
    while state in came_from:
        state_sequence.append(state)
        state = came_from[state]
    state_sequence.append(state)
    state_sequence.reverse()
    return state_sequence


def _route_from_state_sequence(state_sequence, segments, start):
    route = [[start[0], start[1]]]

    for state_index in range(1, len(state_sequence)):
        prev_state = state_sequence[state_index - 1]
        next_state = state_sequence[state_index]
        prev_node_index = prev_state[1]
        next_node_index = next_state[1]
        segment = segments[prev_node_index][next_node_index]

        if not segment:
            raise ValueError("Internal routing error while reconstructing the path")

        route.extend(segment[1:])

    return route


def _shortest_completion_from_state(start_state, distances, coverage_masks, all_targets_mask, cache):
    if start_state in cache:
        return cache[start_state]

    best_cost, came_from, final_state = _run_state_space_dijkstra(
        start_state,
        distances,
        coverage_masks,
        all_targets_mask,
    )

    if final_state is None:
        cache[start_state] = None
        return None

    state_sequence = _reconstruct_state_sequence(came_from, final_state)
    result = (state_sequence, best_cost[final_state])
    cache[start_state] = result
    return result


def _build_globally_optimal_route(grid, start, goals, walkable):
    unique_goals = _dedupe_goals(goals)
    if not unique_goals:
        return [[start[0], start[1]]]

    coverage_mask_by_point = _build_goal_coverage_by_point(grid, unique_goals, walkable)
    service_nodes = _build_service_nodes(start, unique_goals, grid, walkable)
    segments, distances, coverage_masks = _build_pairwise_segments(
        grid,
        service_nodes,
        walkable,
        coverage_mask_by_point,
    )

    start_node = tuple(start)
    start_index = service_nodes.index(start_node)
    all_targets_mask = (1 << len(unique_goals)) - 1
    initial_mask = _coverage_mask_for_point(start_node, coverage_mask_by_point)

    start_state = (initial_mask, start_index)
    best_cost, came_from, final_state = _run_state_space_dijkstra(
        start_state,
        distances,
        coverage_masks,
        all_targets_mask,
    )

    if final_state is None:
        unresolved_goal = list(unique_goals[0])
        raise ValueError(f"No route found to target {unresolved_goal}")

    state_sequence = _reconstruct_state_sequence(came_from, final_state)
    route = _route_from_state_sequence(state_sequence, segments, start)

    return {
        "route": route,
        "distance": best_cost[final_state],
        "state_sequence": state_sequence,
        "best_cost": best_cost,
        "segments": segments,
        "distances": distances,
        "coverage_masks": coverage_masks,
        "service_nodes": service_nodes,
        "all_targets_mask": all_targets_mask,
    }


def _build_route_alternatives(start, best_solution, max_routes):
    best_route = best_solution["route"]
    best_distance = best_solution["distance"]
    best_state_sequence = best_solution["state_sequence"]
    best_cost = best_solution["best_cost"]
    segments = best_solution["segments"]
    distances = best_solution["distances"]
    coverage_masks = best_solution["coverage_masks"]
    service_nodes = best_solution["service_nodes"]
    all_targets_mask = best_solution["all_targets_mask"]

    route_options = [
        {
            "rank": 1,
            "path": best_route,
            "distance": best_distance,
            "is_best": True,
            "label": "Best path",
        }
    ]
    step_options = []
    alternative_candidates = []
    seen_paths = {tuple(tuple(point) for point in best_route)}
    completion_cache = {}
    node_count = len(service_nodes)

    for step_index in range(len(best_state_sequence) - 1):
        current_state = best_state_sequence[step_index]
        current_mask, current_node_index = current_state
        current_point = service_nodes[current_node_index]

        best_next_state = best_state_sequence[step_index + 1]
        best_next_node = best_next_state[1]
        best_distance_from_current = distances[current_node_index][best_next_node]
        best_step_total = None
        if best_distance_from_current is not None:
            best_step_total = (
                best_cost[current_state]
                + best_distance_from_current
                + (best_solution["distance"] - best_cost[best_next_state])
            )

        alternatives_for_step = []

        for next_node_index in range(node_count):
            if next_node_index == current_node_index:
                continue

            step_distance = distances[current_node_index][next_node_index]
            if step_distance is None:
                continue

            next_mask = current_mask | coverage_masks[current_node_index][next_node_index]
            next_state = (next_mask, next_node_index)
            completion = _shortest_completion_from_state(
                next_state,
                distances,
                coverage_masks,
                all_targets_mask,
                completion_cache,
            )

            if completion is None:
                continue

            suffix_states, suffix_cost = completion
            estimated_total_distance = best_cost[current_state] + step_distance + suffix_cost
            is_best_step = next_state == best_next_state and estimated_total_distance == best_distance

            alternatives_for_step.append(
                {
                    "next": [service_nodes[next_node_index][0], service_nodes[next_node_index][1]],
                    "estimated_total_distance": estimated_total_distance,
                    "is_best_step": is_best_step,
                }
            )

            if is_best_step:
                continue

            candidate_state_sequence = best_state_sequence[: step_index + 1] + suffix_states
            candidate_route = _route_from_state_sequence(candidate_state_sequence, segments, start)
            route_key = tuple(tuple(point) for point in candidate_route)
            if route_key in seen_paths:
                continue

            seen_paths.add(route_key)
            alternative_candidates.append(
                {
                    "path": candidate_route,
                    "distance": estimated_total_distance,
                }
            )

        alternatives_for_step.sort(
            key=lambda option: (option["estimated_total_distance"], option["next"][0], option["next"][1])
        )
        step_options.append(
            {
                "step_index": step_index,
                "at": [current_point[0], current_point[1]],
                "alternatives": alternatives_for_step,
            }
        )

    alternative_candidates.sort(key=lambda candidate: (candidate["distance"], len(candidate["path"])))

    max_extra_routes = max(max_routes - 1, 0)
    for option_index, candidate in enumerate(alternative_candidates[:max_extra_routes], start=2):
        route_options.append(
            {
                "rank": option_index,
                "path": candidate["path"],
                "distance": candidate["distance"],
                "is_best": False,
                "label": f"Alternative #{option_index - 1}",
            }
        )

    return route_options, step_options


def calculate_route_with_alternatives(grid, start, goals, max_routes=5):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list):
        raise ValueError("grid must be a 2D list")

    if not _is_coord(start):
        raise ValueError("start must be [row, col]")

    if not isinstance(goals, list) or any(not _is_coord(goal) for goal in goals):
        raise ValueError("targets must be a list of [row, col] coordinates")

    try:
        max_routes = int(max_routes)
    except (TypeError, ValueError):
        max_routes = 5
    max_routes = min(max(max_routes, 1), 25)

    if not goals:
        return {
            "path": [start],
            "distance": 0,
            "route_options": [
                {
                    "rank": 1,
                    "path": [start],
                    "distance": 0,
                    "is_best": True,
                    "label": "Best path",
                }
            ],
            "step_options": [],
            "summary": "Only the start point is required, so no movement is needed.",
        }

    rows = len(grid)
    cols = len(grid[0])
    if any(len(row) != cols for row in grid):
        raise ValueError("grid rows must have equal length")

    for point in [start, *goals]:
        if point[0] < 0 or point[1] < 0 or point[0] >= rows or point[1] >= cols:
            raise ValueError("start/targets include out-of-bounds coordinates")

    walkable = _build_walkable_set(grid, goals)
    if tuple(start) not in walkable:
        raise ValueError("start must be on a walkable non-shelf cell")

    best_solution = _build_globally_optimal_route(grid, start, goals, walkable)
    route_options, step_options = _build_route_alternatives(start, best_solution, max_routes)

    for option in route_options:
        validate_route_safety(grid, option["path"], start, goals)

    best_distance = route_options[0]["distance"]
    summary = (
        f"Route #1 is globally optimal with distance {best_distance}. "
        f"Returned {len(route_options)} ranked route option(s)."
    )

    return {
        "path": route_options[0]["path"],
        "distance": best_distance,
        "route_options": route_options,
        "step_options": step_options,
        "summary": summary,
    }


def calculate_a_star_route(grid, start, goals):
    route_result = calculate_route_with_alternatives(grid, start, goals, max_routes=1)
    return route_result["path"], route_result["distance"]


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
