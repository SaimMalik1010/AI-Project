import heapq
from collections import defaultdict


_FLOYD_CACHE = {}


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


def _normalize_algorithm(algorithm):
    if not isinstance(algorithm, str):
        return "astar"

    normalized = algorithm.strip().lower().replace("_", " ").replace("-", " ")
    if normalized in {"astar", "a star", "a*"}:
        return "astar"
    if normalized in {"greedy", "greedy best first", "greedy best first search", "gbfs"}:
        return "greedy"
    if normalized in {"floyd", "floyd warshall", "floyd warshall algo", "floyd warshall algorithm"}:
        return "floyd-warshall"
    return "astar"


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


def _service_endpoints_for_stop(stop, grid, walkable):
    stop_row, stop_col = stop
    if grid[stop_row][stop_col] == 1:
        return _pickup_endpoints_for_goal(stop, grid, walkable)

    stop_cell = (stop_row, stop_col)
    if stop_cell in walkable:
        return [stop_cell]
    return []


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


def _greedy_best_first_segment(grid, start, goal, walkable):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0

    start_node = tuple(start)
    goal_node = tuple(goal)
    if start_node not in walkable or goal_node not in walkable:
        return []

    frontier = [(0, start_node)]
    came_from = {start_node: None}
    visited = {start_node}

    while frontier:
        _, current = heapq.heappop(frontier)

        if current == goal_node:
            break

        for neighbor in _neighbors(current[0], current[1], rows, cols):
            if neighbor not in walkable or neighbor in visited:
                continue

            visited.add(neighbor)
            came_from[neighbor] = current
            priority = _heuristic(neighbor, goal_node)
            heapq.heappush(frontier, (priority, neighbor))

    if goal_node not in came_from:
        return []

    path = []
    node = goal_node
    while node is not None:
        path.append([node[0], node[1]])
        node = came_from[node]

    path.reverse()
    return path


def _build_floyd_warshall_bundle(grid, walkable):
    cache_key = tuple(tuple(row) for row in grid)
    cached_bundle = _FLOYD_CACHE.get(cache_key)
    if cached_bundle is not None:
        return cached_bundle

    nodes = sorted(walkable)
    index_by_node = {node: index for index, node in enumerate(nodes)}
    size = len(nodes)
    infinity = float("inf")
    distances = [[infinity for _ in range(size)] for _ in range(size)]
    next_hops = [[None for _ in range(size)] for _ in range(size)]

    for index, node in enumerate(nodes):
        distances[index][index] = 0
        next_hops[index][index] = index

    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    for index, node in enumerate(nodes):
        row, col = node
        for next_row, next_col in _neighbors(row, col, rows, cols):
            neighbor = (next_row, next_col)
            if neighbor not in index_by_node:
                continue

            neighbor_index = index_by_node[neighbor]
            distances[index][neighbor_index] = 1
            next_hops[index][neighbor_index] = neighbor_index

    for pivot in range(size):
        for source in range(size):
            if distances[source][pivot] == infinity:
                continue
            for target in range(size):
                if distances[pivot][target] == infinity:
                    continue

                candidate_distance = distances[source][pivot] + distances[pivot][target]
                if candidate_distance < distances[source][target]:
                    distances[source][target] = candidate_distance
                    next_hops[source][target] = next_hops[source][pivot]

    bundle = {
        "nodes": nodes,
        "index_by_node": index_by_node,
        "distances": distances,
        "next_hops": next_hops,
    }
    _FLOYD_CACHE[cache_key] = bundle
    return bundle


def _floyd_warshall_segment(grid, start, goal, walkable):
    start_node = tuple(start)
    goal_node = tuple(goal)
    if start_node not in walkable or goal_node not in walkable:
        return []

    bundle = _build_floyd_warshall_bundle(grid, walkable)
    index_by_node = bundle["index_by_node"]
    next_hops = bundle["next_hops"]

    source_index = index_by_node.get(start_node)
    target_index = index_by_node.get(goal_node)
    if source_index is None or target_index is None:
        return []

    if next_hops[source_index][target_index] is None:
        return []

    path = [[start_node[0], start_node[1]]]
    current_index = source_index
    while current_index != target_index:
        current_index = next_hops[current_index][target_index]
        if current_index is None:
            return []
        node = bundle["nodes"][current_index]
        path.append([node[0], node[1]])

    return path


def _find_segment(grid, start, goal, walkable, algorithm="astar"):
    normalized = _normalize_algorithm(algorithm)
    if normalized == "greedy":
        return _greedy_best_first_segment(grid, start, goal, walkable)
    if normalized == "floyd-warshall":
        return _floyd_warshall_segment(grid, start, goal, walkable)
    return _a_star_segment(grid, start, goal, walkable)


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


def _build_pairwise_segments(grid, service_nodes, walkable, coverage_mask_by_point, algorithm="astar"):
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

            segment = _find_segment(
                grid,
                [source[0], source[1]],
                [target[0], target[1]],
                walkable,
                algorithm=algorithm,
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


def _build_globally_optimal_route(grid, start, goals, walkable, algorithm="astar"):
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
        algorithm=algorithm,
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


def calculate_route_with_alternatives(grid, start, goals, max_routes=5, algorithm="astar"):
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
    algorithm = _normalize_algorithm(algorithm)

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

    best_solution = _build_globally_optimal_route(grid, start, goals, walkable, algorithm=algorithm)
    route_options, step_options = _build_route_alternatives(start, best_solution, max_routes)

    for option in route_options:
        validate_route_safety(grid, option["path"], start, goals)

    best_distance = route_options[0]["distance"]
    summary = (
        f"Route #1 is globally optimal with distance {best_distance} using {algorithm}. "
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


def _copy_reservation_table(reservation_table):
    return {
        "occupied_by_time": {
            time_step: dict(cells)
            for time_step, cells in reservation_table["occupied_by_time"].items()
        },
        "edges_by_time": {
            time_step: set(edges)
            for time_step, edges in reservation_table["edges_by_time"].items()
        },
    }


def _create_empty_reservation_table():
    return {
        "occupied_by_time": defaultdict(dict),
        "edges_by_time": defaultdict(set),
    }


def _reserve_path(reservation_table, robot_id, path, horizon=None):
    if not path:
        return

    for time_step, point in enumerate(path):
        cell = (point[0], point[1])
        reservation_table["occupied_by_time"][time_step][cell] = robot_id

        if time_step > 0:
            previous = path[time_step - 1]
            edge = ((previous[0], previous[1]), (point[0], point[1]))
            reservation_table["edges_by_time"][time_step - 1].add(edge)

    if horizon is None:
        return

    final_cell = (path[-1][0], path[-1][1])
    last_time = len(path) - 1
    for time_step in range(last_time + 1, horizon + 1):
        reservation_table["occupied_by_time"][time_step][final_cell] = robot_id


def _goal_window_is_free(goal_cell, start_time, reservation_table, hold_window):
    for time_step in range(start_time, start_time + hold_window + 1):
        if goal_cell in reservation_table["occupied_by_time"].get(time_step, {}):
            return False
    return True


def _spacetime_a_star(
    grid,
    start,
    goal,
    reservation_table,
    max_time,
    forbidden_nodes=None,
    forbidden_edges=None,
    goal_hold_window=3,
):
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    start_cell = (start[0], start[1])
    goal_cell = (goal[0], goal[1])

    if grid[start_cell[0]][start_cell[1]] == 1:
        return None
    if grid[goal_cell[0]][goal_cell[1]] == 1:
        return None

    forbidden_nodes = forbidden_nodes or set()
    forbidden_edges = forbidden_edges or set()

    start_state = (start_cell[0], start_cell[1], 0)
    frontier = [(0, 0, start_state)]
    came_from = {start_state: None}
    cost_so_far = {start_state: 0}

    while frontier:
        _, current_cost, current = heapq.heappop(frontier)
        row, col, time_step = current

        if cost_so_far[current] != current_cost:
            continue

        if (row, col) == goal_cell and _goal_window_is_free(
            goal_cell,
            time_step,
            reservation_table,
            goal_hold_window,
        ):
            path = []
            node = current
            while node is not None:
                path.append([node[0], node[1]])
                node = came_from[node]
            path.reverse()
            return path

        if time_step >= max_time:
            continue

        next_time = time_step + 1
        candidates = [
            (row, col),
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        ]

        for next_row, next_col in candidates:
            if next_row < 0 or next_col < 0 or next_row >= rows or next_col >= cols:
                continue
            if grid[next_row][next_col] == 1:
                continue

            next_cell = (next_row, next_col)
            current_cell = (row, col)

            if (next_time, next_cell) in forbidden_nodes:
                continue

            if (time_step, current_cell, next_cell) in forbidden_edges:
                continue

            occupied = reservation_table["occupied_by_time"].get(next_time, {})
            if next_cell in occupied:
                continue

            opposite_edge = (next_cell, current_cell)
            if opposite_edge in reservation_table["edges_by_time"].get(time_step, set()):
                continue

            next_state = (next_row, next_col, next_time)
            next_cost = current_cost + 1
            known_cost = cost_so_far.get(next_state)
            if known_cost is not None and next_cost >= known_cost:
                continue

            cost_so_far[next_state] = next_cost
            came_from[next_state] = current
            priority = next_cost + _heuristic(next_cell, goal_cell)
            heapq.heappush(frontier, (priority, next_cost, next_state))

    return None


def _path_cell_at(path, time_step):
    if time_step < len(path):
        return tuple(path[time_step])
    return tuple(path[-1])


def _detect_first_conflict(paths_by_robot):
    robot_ids = sorted(paths_by_robot.keys())
    if len(robot_ids) < 2:
        return None

    max_len = max(len(paths_by_robot[robot_id]) for robot_id in robot_ids)

    for time_step in range(max_len):
        occupancy = {}
        for robot_id in robot_ids:
            cell = _path_cell_at(paths_by_robot[robot_id], time_step)
            if cell in occupancy:
                return {
                    "type": "vertex",
                    "time": time_step,
                    "cell": cell,
                    "robots": (occupancy[cell], robot_id),
                }
            occupancy[cell] = robot_id

        if time_step == 0:
            continue

        for first_index in range(len(robot_ids)):
            for second_index in range(first_index + 1, len(robot_ids)):
                first_id = robot_ids[first_index]
                second_id = robot_ids[second_index]

                first_prev = _path_cell_at(paths_by_robot[first_id], time_step - 1)
                first_curr = _path_cell_at(paths_by_robot[first_id], time_step)
                second_prev = _path_cell_at(paths_by_robot[second_id], time_step - 1)
                second_curr = _path_cell_at(paths_by_robot[second_id], time_step)

                if first_prev == second_curr and second_prev == first_curr:
                    return {
                        "type": "edge",
                        "time": time_step,
                        "edge": (first_prev, first_curr),
                        "robots": (first_id, second_id),
                    }

    return None


def _build_forbidden_constraints_for_robot(robot_id, conflict, paths_by_robot):
    forbidden_nodes = set()
    forbidden_edges = set()

    if conflict["type"] == "vertex":
        forbidden_nodes.add((conflict["time"], conflict["cell"]))
    elif conflict["type"] == "edge":
        time_step = conflict["time"]
        robot_path = paths_by_robot[robot_id]
        from_cell = _path_cell_at(robot_path, time_step - 1)
        to_cell = _path_cell_at(robot_path, time_step)
        forbidden_edges.add((time_step - 1, from_cell, to_cell))

    return forbidden_nodes, forbidden_edges


def _build_reservation_from_peer_paths(base_reservation_table, peer_paths):
    table = _copy_reservation_table(base_reservation_table)
    table["occupied_by_time"] = defaultdict(dict, table["occupied_by_time"])
    table["edges_by_time"] = defaultdict(set, table["edges_by_time"])

    max_path_len = max((len(path) for path in peer_paths.values()), default=0)
    hold_horizon = max_path_len + 12
    for robot_id, path in peer_paths.items():
        _reserve_path(table, robot_id, path, horizon=hold_horizon)

    return table


def _plan_segment_to_stop(
    grid,
    walkable,
    start_point,
    stop,
    reservation_table,
    max_time,
    forbidden_nodes=None,
    forbidden_edges=None,
):
    candidate_endpoints = _service_endpoints_for_stop(tuple(stop), grid, walkable)
    if not candidate_endpoints:
        return None, None

    best_segment = None
    best_endpoint = None
    for endpoint in candidate_endpoints:
        segment = _spacetime_a_star(
            grid,
            start_point,
            [endpoint[0], endpoint[1]],
            reservation_table,
            max_time=max_time,
            forbidden_nodes=forbidden_nodes,
            forbidden_edges=forbidden_edges,
        )
        if not segment:
            continue

        if best_segment is None or len(segment) < len(best_segment):
            best_segment = segment
            best_endpoint = endpoint

    return best_segment, best_endpoint


def _normalize_robots_payload(robots):
    if not isinstance(robots, list) or not robots:
        raise ValueError("robots must be a non-empty list")

    normalized = []
    seen_ids = set()
    for index, robot in enumerate(robots):
        if not isinstance(robot, dict):
            raise ValueError(f"robots[{index}] must be an object")

        robot_id = robot.get("id")
        start = robot.get("start")
        goal = robot.get("goal")
        stops = robot.get("stops")
        priority = robot.get("priority", 10)

        if not isinstance(robot_id, str) or not robot_id.strip():
            raise ValueError(f"robots[{index}].id must be a non-empty string")

        robot_id = robot_id.strip()
        if robot_id in seen_ids:
            raise ValueError(f"Duplicate robot id '{robot_id}'")
        seen_ids.add(robot_id)

        if not _is_coord(start):
            raise ValueError(f"robots[{index}].start must be [row, col]")
        normalized_stops = []
        if stops is not None:
            if not isinstance(stops, list) or not stops:
                raise ValueError(f"robots[{index}].stops must be a non-empty list")
            if any(not _is_coord(stop) for stop in stops):
                raise ValueError(f"robots[{index}].stops must be a list of [row, col] coordinates")
            normalized_stops = [[stop[0], stop[1]] for stop in stops]
        else:
            if not _is_coord(goal):
                raise ValueError(f"robots[{index}].goal must be [row, col]")
            normalized_stops = [[goal[0], goal[1]]]

        try:
            priority = int(priority)
        except (TypeError, ValueError):
            raise ValueError(f"robots[{index}].priority must be an integer")

        normalized.append(
            {
                "id": robot_id,
                "start": [start[0], start[1]],
                "stops": normalized_stops,
                "goal": normalized_stops[-1],
                "priority": max(1, min(priority, 10)),
            }
        )

    return normalized


def orchestrate_multi_robot_routes(grid, robots):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list):
        raise ValueError("grid must be a non-empty 2D list")

    rows = len(grid)
    cols = len(grid[0])
    if any(not isinstance(row, list) or len(row) != cols for row in grid):
        raise ValueError("grid rows must have equal length")

    robots = _normalize_robots_payload(robots)
    walkable = _build_walkable_set(grid, [])

    for robot in robots:
        for label in ("start",):
            row, col = robot[label]
            if row < 0 or col < 0 or row >= rows or col >= cols:
                raise ValueError(f"Robot {robot['id']} has out-of-bounds {label}")
            if grid[row][col] == 1:
                raise ValueError(f"Robot {robot['id']} has {label} on a shelf cell")

        for stop_index, stop in enumerate(robot["stops"]):
            row, col = stop
            if row < 0 or col < 0 or row >= rows or col >= cols:
                raise ValueError(f"Robot {robot['id']} has out-of-bounds stop at index {stop_index}")

            stop_endpoints = _service_endpoints_for_stop(tuple(stop), grid, walkable)
            if not stop_endpoints:
                raise ValueError(
                    f"Robot {robot['id']} has an unreachable stop at index {stop_index}: {stop}"
                )

    robots_by_id = {robot["id"]: robot for robot in robots}
    grouped_by_priority = defaultdict(list)
    for robot in robots:
        grouped_by_priority[robot["priority"]].append(robot)

    global_reservation = _create_empty_reservation_table()
    planned_paths = {}
    conflict_log = []
    max_time = max(60, rows * cols * 2 + len(robots) * 20)

    for priority in sorted(grouped_by_priority.keys()):
        group = sorted(grouped_by_priority[priority], key=lambda robot: robot["id"])

        group_paths = {}
        for robot in group:
            start_point = robot["start"]
            full_path = [start_point]
            serviced_from = []
            for stop in robot["stops"]:
                segment, endpoint = _plan_segment_to_stop(
                    grid,
                    walkable,
                    start_point,
                    stop,
                    global_reservation,
                    max_time=max_time,
                )
                if not segment:
                    raise ValueError(f"No route found for robot {robot['id']}")

                if full_path:
                    full_path.extend(segment[1:])
                else:
                    full_path.extend(segment)

                start_point = [endpoint[0], endpoint[1]]
                serviced_from.append([endpoint[0], endpoint[1]])

            group_paths[robot["id"]] = full_path
            robot["serviced_from"] = serviced_from

        max_iterations = 120
        for _ in range(max_iterations):
            conflict = _detect_first_conflict(group_paths)
            if conflict is None:
                break

            first_robot, second_robot = conflict["robots"]
            first_path = group_paths[first_robot]
            second_path = group_paths[second_robot]

            first_peers = {
                robot_id: path
                for robot_id, path in group_paths.items()
                if robot_id != first_robot
            }
            second_peers = {
                robot_id: path
                for robot_id, path in group_paths.items()
                if robot_id != second_robot
            }

            first_reservation = _build_reservation_from_peer_paths(global_reservation, first_peers)
            second_reservation = _build_reservation_from_peer_paths(global_reservation, second_peers)

            first_forbidden_nodes, first_forbidden_edges = _build_forbidden_constraints_for_robot(
                first_robot,
                conflict,
                group_paths,
            )
            second_forbidden_nodes, second_forbidden_edges = _build_forbidden_constraints_for_robot(
                second_robot,
                conflict,
                group_paths,
            )

            def _plan_robot_stops(robot_definition, reservation, forbidden_nodes, forbidden_edges):
                current_start = robot_definition["start"]
                combined_path = [current_start]
                service_cells = []
                applied_forbidden_nodes = set(forbidden_nodes)
                applied_forbidden_edges = set(forbidden_edges)

                for stop in robot_definition["stops"]:
                    segment, endpoint = _plan_segment_to_stop(
                        grid,
                        walkable,
                        current_start,
                        stop,
                        reservation,
                        max_time=max_time,
                        forbidden_nodes=applied_forbidden_nodes,
                        forbidden_edges=applied_forbidden_edges,
                    )
                    if not segment:
                        return None, None

                    combined_path.extend(segment[1:])
                    current_start = [endpoint[0], endpoint[1]]
                    service_cells.append([endpoint[0], endpoint[1]])
                    applied_forbidden_nodes = set()
                    applied_forbidden_edges = set()

                return combined_path, service_cells

            first_alt, first_service_cells = _plan_robot_stops(
                robots_by_id[first_robot],
                first_reservation,
                first_forbidden_nodes,
                first_forbidden_edges,
            )
            second_alt, second_service_cells = _plan_robot_stops(
                robots_by_id[second_robot],
                second_reservation,
                second_forbidden_nodes,
                second_forbidden_edges,
            )

            first_detour = float("inf")
            second_detour = float("inf")
            if first_alt:
                first_detour = len(first_alt) - len(first_path)
            if second_alt:
                second_detour = len(second_alt) - len(second_path)

            if first_detour == float("inf") and second_detour == float("inf"):
                raise ValueError(
                    f"Conflict between robots {first_robot} and {second_robot} cannot be resolved"
                )

            if first_detour < second_detour:
                yielded_robot = first_robot
                yielded_path = first_alt
                winner = second_robot
            elif second_detour < first_detour:
                yielded_robot = second_robot
                yielded_path = second_alt
                winner = first_robot
            else:
                yielded_robot = sorted([first_robot, second_robot])[0]
                winner = second_robot if yielded_robot == first_robot else first_robot
                yielded_path = first_alt if yielded_robot == first_robot else second_alt

            if not yielded_path:
                winner = yielded_robot
                yielded_robot = second_robot if yielded_robot == first_robot else first_robot
                yielded_path = second_alt if yielded_robot == second_robot else first_alt

            if not yielded_path:
                raise ValueError(
                    f"Conflict between robots {first_robot} and {second_robot} cannot be resolved"
                )

            group_paths[yielded_robot] = yielded_path
            if yielded_robot == first_robot and first_service_cells is not None:
                robots_by_id[first_robot]["serviced_from"] = first_service_cells
            if yielded_robot == second_robot and second_service_cells is not None:
                robots_by_id[second_robot]["serviced_from"] = second_service_cells
            conflict_log.append(
                {
                    "time": conflict["time"],
                    "type": conflict["type"],
                    "robots": [first_robot, second_robot],
                    "yielded_robot": yielded_robot,
                    "winner_robot": winner,
                    "detour_costs": {
                        first_robot: None if first_detour == float("inf") else first_detour,
                        second_robot: None if second_detour == float("inf") else second_detour,
                    },
                }
            )
        else:
            raise ValueError("Conflict resolution exceeded maximum iterations")

        hold_horizon = max(len(path) for path in group_paths.values()) + 12
        for robot_id, path in group_paths.items():
            planned_paths[robot_id] = path
            _reserve_path(global_reservation, robot_id, path, horizon=hold_horizon)

    robots_response = []
    for robot in sorted(robots, key=lambda item: item["id"]):
        robot_id = robot["id"]
        path = planned_paths[robot_id]
        wait_times = []
        for time_step in range(1, len(path)):
            if path[time_step] == path[time_step - 1]:
                wait_times.append(time_step)

        yield_times = sorted(
            {
                entry["time"]
                for entry in conflict_log
                if entry["yielded_robot"] == robot_id
            }
        )

        robots_response.append(
            {
                "id": robot_id,
                "priority": robot["priority"],
                "start": robot["start"],
                "stops": robot["stops"],
                "serviced_from": robot.get("serviced_from", []),
                "goal": robot["goal"],
                "path": path,
                "distance": len(path) - 1,
                "wait_times": wait_times,
                "yield_times": yield_times,
            }
        )

    makespan = max((len(robot["path"]) for robot in robots_response), default=0) - 1
    total_cost = sum(robot["distance"] for robot in robots_response)

    return {
        "status": "success",
        "mode": "multi_robot",
        "robots": robots_response,
        "makespan": max(makespan, 0),
        "total_cost": total_cost,
        "conflicts_resolved": conflict_log,
        "summary": (
            f"Planned {len(robots_response)} robots with makespan {max(makespan, 0)} "
            f"and total cost {total_cost}."
        ),
    }
