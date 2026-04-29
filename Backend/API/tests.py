from collections import deque

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class RouteSafetyTests(APITestCase):
	def setUp(self):
		# 0 = floor, 1 = shelf
		self.grid = [
			[0, 0, 0, 0, 0],
			[0, 1, 1, 1, 0],
			[0, 0, 0, 0, 0],
		]

		create_response = self.client.post(
			reverse("create_warehouse_map"),
			{
				"name": "Test Warehouse",
				"aisle_count": 1,
				"shelves_per_aisle": 3,
				"grid": self.grid,
			},
			format="json",
		)

		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
		self.map_id = create_response.data["warehouse_map"]["id"]

	def test_route_never_steps_on_shelf_cells(self):
		response = self.client.post(
			reverse("get_route"),
			{
				"start": [0, 0],
				"targets": [[1, 1], [1, 3]],
				"warehouse_map_id": self.map_id,
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["status"], "success")

		for row, col in response.data["path"]:
			self.assertNotEqual(
				self.grid[row][col],
				1,
				msg=f"Route should not traverse shelf cell ({row}, {col})",
			)

	def test_non_shelf_target_is_rejected(self):
		response = self.client.post(
			reverse("get_route"),
			{
				"start": [0, 0],
				"targets": [[0, 2]],
				"warehouse_map_id": self.map_id,
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertEqual(response.data["status"], "error")
		self.assertIn("must point to a shelf cell", response.data["message"])


class GlobalOptimalityTests(APITestCase):
	def _served_mask(self, grid, row, col, targets):
		if grid[row][col] == 1:
			return 0

		mask = 0
		for index, (target_row, target_col) in enumerate(targets):
			if abs(target_row - row) + abs(target_col - col) == 1:
				mask |= 1 << index
		return mask

	def _bruteforce_global_optimum(self, grid, start, targets):
		rows = len(grid)
		cols = len(grid[0])
		all_mask = (1 << len(targets)) - 1
		start_mask = self._served_mask(grid, start[0], start[1], targets)

		queue = deque([(start[0], start[1], start_mask, 0)])
		seen = {(start[0], start[1], start_mask)}

		while queue:
			row, col, mask, dist = queue.popleft()
			if mask == all_mask:
				return dist

			for next_row, next_col in (
				(row - 1, col),
				(row + 1, col),
				(row, col - 1),
				(row, col + 1),
			):
				if next_row < 0 or next_col < 0 or next_row >= rows or next_col >= cols:
					continue
				if grid[next_row][next_col] == 1:
					continue

				next_mask = mask | self._served_mask(grid, next_row, next_col, targets)
				state = (next_row, next_col, next_mask)
				if state in seen:
					continue

				seen.add(state)
				queue.append((next_row, next_col, next_mask, dist + 1))

		return None

	def test_route_distance_matches_global_optimum(self):
		grid = [
			[0, 0, 0, 0, 0, 0],
			[0, 1, 1, 0, 1, 0],
			[0, 0, 0, 0, 0, 0],
			[0, 1, 1, 0, 1, 0],
			[0, 0, 0, 0, 0, 0],
		]
		start = [0, 0]
		targets = [[1, 1], [1, 4], [3, 1], [3, 4]]

		create_response = self.client.post(
			reverse("create_warehouse_map"),
			{
				"name": "Global Optimum Case",
				"aisle_count": 2,
				"shelves_per_aisle": 2,
				"grid": grid,
			},
			format="json",
		)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
		map_id = create_response.data["warehouse_map"]["id"]

		route_response = self.client.post(
			reverse("get_route"),
			{
				"start": start,
				"targets": targets,
				"warehouse_map_id": map_id,
			},
			format="json",
		)

		self.assertEqual(route_response.status_code, status.HTTP_200_OK)
		self.assertEqual(route_response.data["status"], "success")

		expected_distance = self._bruteforce_global_optimum(grid, start, targets)
		self.assertIsNotNone(expected_distance)
		self.assertEqual(route_response.data["distance"], expected_distance)


class MultiRobotOrchestrationTests(APITestCase):
	def _cell_at(self, path, time_step):
		if time_step < len(path):
			return tuple(path[time_step])
		return tuple(path[-1])

	def test_multi_robot_routes_avoid_vertex_and_edge_collisions(self):
		grid = [
			[0, 0, 0, 0],
			[0, 1, 1, 0],
			[0, 0, 0, 0],
		]

		create_response = self.client.post(
			reverse("create_warehouse_map"),
			{
				"name": "Multi Robot Test",
				"aisle_count": 1,
				"shelves_per_aisle": 2,
				"grid": grid,
			},
			format="json",
		)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

		map_id = create_response.data["warehouse_map"]["id"]
		response = self.client.post(
			reverse("get_route"),
			{
				"warehouse_map_id": map_id,
				"robots": [
					{"id": "A", "start": [0, 0], "goal": [0, 3], "priority": 1},
					{"id": "B", "start": [0, 3], "goal": [0, 0], "priority": 2},
				],
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["status"], "success")
		self.assertEqual(response.data["mode"], "multi_robot")

		robots = {item["id"]: item for item in response.data["robots"]}
		self.assertIn("A", robots)
		self.assertIn("B", robots)

		path_a = robots["A"]["path"]
		path_b = robots["B"]["path"]
		self.assertTrue(path_a)
		self.assertTrue(path_b)

		max_len = max(len(path_a), len(path_b))
		for time_step in range(max_len):
			cell_a = self._cell_at(path_a, time_step)
			cell_b = self._cell_at(path_b, time_step)
			self.assertNotEqual(cell_a, cell_b, msg=f"Vertex collision at t={time_step}")

			if time_step > 0:
				prev_a = self._cell_at(path_a, time_step - 1)
				prev_b = self._cell_at(path_b, time_step - 1)
				self.assertFalse(
					prev_a == cell_b and prev_b == cell_a,
					msg=f"Edge swap collision at t={time_step}",
				)

		self.assertGreaterEqual(robots["B"]["distance"], robots["A"]["distance"])

	def test_same_priority_auction_records_yielding_conflict(self):
		grid = [
			[0, 0, 0],
			[0, 0, 0],
			[0, 0, 0],
		]

		response = self.client.post(
			reverse("get_route"),
			{
				"grid": grid,
				"robots": [
					{"id": "A", "start": [0, 1], "goal": [2, 1], "priority": 3},
					{"id": "B", "start": [2, 1], "goal": [0, 1], "priority": 3},
				],
			},
			format="json",
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data["status"], "success")
		self.assertTrue(isinstance(response.data.get("conflicts_resolved", []), list))

		if response.data["conflicts_resolved"]:
			first_conflict = response.data["conflicts_resolved"][0]
			self.assertIn(first_conflict.get("yielded_robot"), {"A", "B"})

	def test_multi_robot_multi_stop_routes_service_all_stops_collision_free(self):
		grid = [
			[0, 0, 0, 0, 0],
			[0, 1, 0, 1, 0],
			[0, 0, 0, 0, 0],
			[0, 1, 0, 1, 0],
			[0, 0, 0, 0, 0],
		]

		create_response = self.client.post(
			reverse("create_warehouse_map"),
			{
				"name": "Multi Stop Multi Robot Test",
				"aisle_count": 0,
				"shelves_per_aisle": 0,
				"grid": grid,
			},
			format="json",
		)
		self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
		map_id = create_response.data["warehouse_map"]["id"]

		response = self.client.post(
			reverse("get_route"),
			{
				"warehouse_map_id": map_id,
				"robots": [
					{
						"id": "R1",
						"start": [0, 0],
						"stops": [[1, 1], [3, 1]],
						"priority": 9,
					},
					{
						"id": "R2",
						"start": [4, 0],
						"stops": [[3, 3], [1, 3]],
						"priority": 8,
					},
				],
			},
			format="json",
		)

		self.assertEqual(response.status_code, 200, response.data)
		data = response.json()
		self.assertIn("robots", data)
		self.assertEqual(len(data["robots"]), 2)

		by_id = {robot["id"]: robot for robot in data["robots"]}

		for robot_id, expected_stops in {
			"R1": [[1, 1], [3, 1]],
			"R2": [[3, 3], [1, 3]],
		}.items():
			robot = by_id[robot_id]
			path = robot["path"]
			serviced_from = robot.get("serviced_from", [])
			self.assertEqual(len(serviced_from), len(expected_stops))

			for row, col in path:
				self.assertNotEqual(grid[row][col], 1)

			for stop in expected_stops:
				self.assertTrue(
					any(abs(stop[0] - point[0]) + abs(stop[1] - point[1]) == 1 for point in path),
					msg=f"Robot {robot_id} never served shelf stop {stop}",
				)

			final_stop = expected_stops[-1]
			self.assertEqual(abs(path[-1][0] - final_stop[0]) + abs(path[-1][1] - final_stop[1]), 1)

		max_len = max(len(robot["path"]) for robot in data["robots"])

		def pos_at(path, t):
			return tuple(path[t] if t < len(path) else path[-1])

		r1_path = by_id["R1"]["path"]
		r2_path = by_id["R2"]["path"]

		for t in range(max_len):
			p1 = pos_at(r1_path, t)
			p2 = pos_at(r2_path, t)
			self.assertNotEqual(p1, p2, f"Vertex collision at t={t}: {p1}")

			if t > 0:
				p1_prev = pos_at(r1_path, t - 1)
				p2_prev = pos_at(r2_path, t - 1)
				self.assertFalse(
					p1_prev == p2 and p2_prev == p1,
					f"Edge swap collision at t={t}: {p1_prev}->{p1} vs {p2_prev}->{p2}",
				)
