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
