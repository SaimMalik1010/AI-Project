import os
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Backend.settings')
django.setup()

from rest_framework.test import APIClient

client = APIClient()

def print_res(label, response):
    print(f"--- {label} ---")
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.data, indent=2))
    except:
        print(response.content.decode())
    print()

# 1) POST /api/warehouse-maps/create/
grid = [
    [0, 0, 0],
    [0, 1, 0],
    [0, 0, 0]
]
res1 = client.post('/api/warehouse-maps/create/', {
    "name": "Test Map",
    "aisle_count": 1,
    "shelves_per_aisle": 1,
    "grid": grid
}, format='json')
print_res("Create Map", res1)

map_id = res1.data['warehouse_map']['id'] if res1.status_code == 201 else None

if map_id:
    # 2) POST /api/get-route/ with valid targets
    res2 = client.post('/api/get-route/', {
        "start": [0, 0],
        "targets": [[2, 2]],
        "warehouse_map_id": map_id
    }, format='json')
    print_res("Valid Route", res2)

    # 3) POST /api/get-route/ with impossible target
    blocked_grid = [
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0]
    ]
    res_map_blocked = client.post('/api/warehouse-maps/create/', {
        "name": "Blocked Map",
        "grid": blocked_grid
    }, format='json')
    
    if res_map_blocked.status_code == 201:
        blocked_map_id = res_map_blocked.data['warehouse_map']['id']
        res3 = client.post('/api/get-route/', {
            "start": [0, 0],
            "targets": [[2, 2]],
            "warehouse_map_id": blocked_map_id
        }, format='json')
        print_res("Impossible Route", res3)
else:
    print("Failed to create map, skipping route tests.")
