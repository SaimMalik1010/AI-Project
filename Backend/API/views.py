from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import PickingSession, WarehouseMap


def calculate_a_star(start, goals):
	"""
	Placeholder path planner.

	This function is intentionally verbose so a future implementation can
	replace the dummy route with a real A* search without having to reverse
	engineer the input/output contract.

	Expected behavior for the future real algorithm:
	- Treat `start` as the robot or packing-station origin, expressed as [x, y].
	- Treat `goals` as a list of shelf coordinates the picker must visit.
	- Search across the warehouse grid while respecting blocked shelf cells,
	  aisle cells, and any additional movement constraints.
	- Build the final route by stitching the start-to-goal and return-to-pack
	  segments together.

	For now, the implementation below returns a hardcoded "snake" path so the
	frontend can be developed independently from the eventual routing engine.
	"""

	# The `start` and `goals` parameters are deliberately unused in the dummy
	# version. They remain in the signature so the real A* implementation can
	# slot in later without changing the API surface.
	_ = start
	_ = goals

	# Hardcoded demo route. This gives the frontend a stable, deterministic
	# sequence to animate while the actual warehouse search logic is being
	# built.
	demo_path = [
		[0, 0],
		[0, 1],
		[1, 1],
		[1, 2],
		[2, 2],
	]

	# Distance is also fixed for the placeholder so the response shape stays
	# consistent with the future solver output.
	demo_distance = 15
	return demo_path, demo_distance


@api_view(["POST"])
@permission_classes([AllowAny])
def get_route(request):
	start = request.data.get("start", [0, 0])
	targets = request.data.get("targets") or request.data.get("pickingList") or []

	if not isinstance(targets, list):
		return Response(
			{
				"status": "error",
				"message": "targets must be a list of [x, y] coordinates.",
			},
			status=status.HTTP_400_BAD_REQUEST,
		)

	path, distance = calculate_a_star(start, targets)
	warehouse_map = WarehouseMap.objects.order_by("-created_at").first()

	PickingSession.objects.create(
		warehouse_map=warehouse_map,
		start_point=start,
		targets=targets,
		request_payload={"start": start, "targets": targets},
		path=path,
		distance=distance,
	)

	return Response(
		{
			"status": "success",
			"path": path,
			"distance": distance,
		}
	)
