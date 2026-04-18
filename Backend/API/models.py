from django.db import models


class WarehouseMap(models.Model):
	name = models.CharField(max_length=120, default="Default Warehouse")
	aisle_count = models.PositiveIntegerField(default=1)
	shelves_per_aisle = models.PositiveIntegerField(default=1)
	grid = models.JSONField(default=list)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name


class PickingSession(models.Model):
	warehouse_map = models.ForeignKey(
		WarehouseMap,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="picking_sessions",
	)
	start_point = models.JSONField(default=list)
	targets = models.JSONField(default=list)
	request_payload = models.JSONField(default=dict)
	path = models.JSONField(default=list)
	distance = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"PickingSession #{self.pk}"
