from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import PickingSession, WarehouseMap
from .pathfinding import (
	calculate_route_with_alternatives,
	orchestrate_multi_robot_routes,
	validate_route_safety,
)


def _normalize_algorithm_label(value):
	if not isinstance(value, str):
		return "A*"

	normalized = value.strip().lower().replace("_", " ").replace("-", " ")
	if normalized in {"greedy", "greedy best first", "greedy best first search", "gbfs"}:
		return "Greedy Best-First Search"
	if normalized in {"floyd", "floyd warshall", "floyd warshall algo", "floyd warshall algorithm"}:
		return "Floyd-Warshall"
	return "A*"


def _serialize_map(warehouse_map):
	return {
		"id": warehouse_map.id,
		"name": warehouse_map.name,
		"aisle_count": warehouse_map.aisle_count,
		"shelves_per_aisle": warehouse_map.shelves_per_aisle,
		"grid": warehouse_map.grid,
		"created_at": warehouse_map.created_at,
	}


@api_view(["POST"])
@permission_classes([AllowAny])
def create_warehouse_map(request):
	name = request.data.get("name") or "Dynamic Warehouse"
	aisle_count = request.data.get("aisle_count", 1)
	shelves_per_aisle = request.data.get("shelves_per_aisle", 1)
	grid = request.data.get("grid", [])

	if not isinstance(grid, list) or not grid or not isinstance(grid[0], list):
		return Response(
			{"status": "error", "message": "grid must be a non-empty 2D list."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	try:
		aisle_count = int(aisle_count)
		shelves_per_aisle = int(shelves_per_aisle)
	except (TypeError, ValueError):
		return Response(
			{"status": "error", "message": "aisle_count and shelves_per_aisle must be integers."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	warehouse_map = WarehouseMap.objects.create(
		name=name,
		aisle_count=max(1, aisle_count),
		shelves_per_aisle=max(1, shelves_per_aisle),
		grid=grid,
	)

	return Response({"status": "success", "warehouse_map": _serialize_map(warehouse_map)}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_warehouse_maps(request):
	warehouse_maps = WarehouseMap.objects.order_by("-created_at")[:50]
	return Response(
		{
			"status": "success",
			"results": [_serialize_map(item) for item in warehouse_maps],
		}
	)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_warehouse_map(request, map_id):
	warehouse_map = WarehouseMap.objects.filter(pk=map_id).first()
	if not warehouse_map:
		return Response(
			{"status": "error", "message": "warehouse map not found."},
			status=status.HTTP_404_NOT_FOUND,
		)

	return Response({"status": "success", "warehouse_map": _serialize_map(warehouse_map)})


@api_view(["POST"])
@permission_classes([AllowAny])
def get_route(request):
	robots_payload = request.data.get("robots")
	warehouse_map_id = request.data.get("warehouse_map_id")
	grid = request.data.get("grid")
	algorithm = request.data.get("algorithm", "A*")
	warehouse_map = None
	algorithm_label = _normalize_algorithm_label(algorithm)

	if warehouse_map_id is not None:
		warehouse_map = WarehouseMap.objects.filter(pk=warehouse_map_id).first()
		if not warehouse_map:
			return Response(
				{"status": "error", "message": "warehouse_map_id is invalid."},
				status=status.HTTP_400_BAD_REQUEST,
			)
		grid = warehouse_map.grid
	elif grid is None:
		warehouse_map = WarehouseMap.objects.order_by("-created_at").first()
		if warehouse_map:
			grid = warehouse_map.grid

	if not isinstance(grid, list) or not grid or not isinstance(grid[0], list):
		return Response(
			{"status": "error", "message": "Route request needs a valid map grid or warehouse_map_id."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	rows = len(grid)
	cols = len(grid[0])
	if any(not isinstance(row, list) or len(row) != cols for row in grid):
		return Response(
			{"status": "error", "message": "grid rows must have equal length."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	if robots_payload is not None:
		try:
			result = orchestrate_multi_robot_routes(grid, robots_payload)
		except ValueError as exc:
			return Response(
				{"status": "error", "message": str(exc)},
				status=status.HTTP_400_BAD_REQUEST,
			)

		for robot in result.get("robots", []):
			PickingSession.objects.create(
				warehouse_map=warehouse_map,
				start_point=robot.get("start", []),
				targets=robot.get("stops") or [robot.get("goal", [])],
				request_payload={"robots": robots_payload},
				path=robot.get("path", []),
				distance=robot.get("distance", 0),
			)

		result["warehouse_map_id"] = warehouse_map.id if warehouse_map else None
		result["algorithm"] = algorithm_label
		result["summary"] = f"Game-theory-inspired multi-robot planning completed using {algorithm_label}. " + result.get("summary", "")
		return Response(result)

	start = request.data.get("start", [0, 0])
	targets = request.data.get("targets") or request.data.get("pickingList") or []
	max_alternatives = request.data.get("max_alternatives", 5)

	if not isinstance(targets, list):
		return Response(
			{
				"status": "error",
				"message": "targets must be a list of [x, y] coordinates.",
			},
			status=status.HTTP_400_BAD_REQUEST,
		)

	if (
		not isinstance(start, list)
		or len(start) != 2
		or any(not isinstance(axis, int) for axis in start)
	):
		return Response(
			{"status": "error", "message": "start must be [row, col]."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	start_row, start_col = start
	if start_row < 0 or start_col < 0 or start_row >= rows or start_col >= cols:
		return Response(
			{"status": "error", "message": "start is out of bounds."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	if grid[start_row][start_col] == 1:
		return Response(
			{"status": "error", "message": "start cannot be on a shelf cell."},
			status=status.HTTP_400_BAD_REQUEST,
		)

	for target in targets:
		target_row, target_col = target
		if target_row < 0 or target_col < 0 or target_row >= rows or target_col >= cols:
			return Response(
				{"status": "error", "message": f"target {target} is out of bounds."},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if grid[target_row][target_col] != 1:
			return Response(
				{
					"status": "error",
					"message": f"target {target} must point to a shelf cell.",
				},
				status=status.HTTP_400_BAD_REQUEST,
			)

	try:
		route_result = calculate_route_with_alternatives(
			grid,
			start,
			targets,
			max_routes=max_alternatives,
			algorithm=algorithm,
		)
		path = route_result["path"]
		distance = route_result["distance"]
		validate_route_safety(grid, path, start, targets)
	except ValueError as exc:
		return Response(
			{"status": "error", "message": str(exc)},
			status=status.HTTP_400_BAD_REQUEST,
		)

	PickingSession.objects.create(
		warehouse_map=warehouse_map,
		start_point=start,
		targets=targets,
		request_payload={
			"start": start,
			"targets": targets,
			"max_alternatives": max_alternatives,
			"warehouse_map_id": warehouse_map_id,
			"grid": grid,
		},
		path=path,
		distance=distance,
	)

	return Response(
		{
			"status": "success",
			"path": path,
			"distance": distance,
			"route_options": route_result["route_options"],
			"step_options": route_result["step_options"],
			"summary": route_result["summary"],
			"algorithm": algorithm_label,
			"warehouse_map_id": warehouse_map.id if warehouse_map else None,
		}
	)
