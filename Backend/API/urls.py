from django.urls import path

from .views import create_warehouse_map, get_route, get_warehouse_map, get_warehouse_maps


urlpatterns = [
    path("warehouse-maps/", get_warehouse_maps, name="get_warehouse_maps"),
    path("warehouse-maps/create/", create_warehouse_map, name="create_warehouse_map"),
    path("warehouse-maps/<int:map_id>/", get_warehouse_map, name="get_warehouse_map"),
    path("get-route/", get_route, name="get_route"),
]