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
