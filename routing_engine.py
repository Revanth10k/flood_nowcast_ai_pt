import networkx as nx
import math

CLEARANCE_LIMITS = {
    "bike": 10.0,
    "sedan": 18.0,
    "suv": 30.0,
    "ambulance": 35.0
}

# Surface street alignments (2D Overland)
DETAILED_STREET_GEOMETRIES = {
    "street_0_1": [
        [17.4400, 78.4900], [17.4415, 78.4918], [17.4430, 78.4935], [17.4450, 78.4950]
    ],
    "street_1_2": [
        [17.4450, 78.4950], [17.4470, 78.4970], [17.4485, 78.4985], [17.4500, 78.5000]
    ],
    "street_2_3": [
        [17.4500, 78.5000], [17.4520, 78.5020], [17.4535, 78.5035], [17.4550, 78.5050]
    ],
    "street_1_4": [
        [17.4450, 78.4950], [17.4445, 78.5020], [17.4448, 78.5065], [17.4450, 78.5100]
    ],
    "street_4_3": [
        [17.4450, 78.5100], [17.4490, 78.5090], [17.4525, 78.5075], [17.4550, 78.5050]
    ],
    "street_0_4": [
        [17.4400, 78.4900], [17.4395, 78.5000], [17.4410, 78.5065], [17.4450, 78.5100]
    ]
}

# Subsurface 1D drainage conduit trunks & underground culverts
DRAINAGE_SEWER_TRUNKS = {
    "pipe_0_1": {
        "diameter_mm": 1200,
        "type": "Reinforced Concrete Pipe",
        "coords": [[17.4401, 78.4902], [17.4416, 78.4920], [17.4431, 78.4937], [17.4451, 78.4952]]
    },
    "pipe_1_2": {
        "diameter_mm": 1800,
        "type": "Primary Storm Drain Trunk",
        "coords": [[17.4451, 78.4952], [17.4471, 78.4972], [17.4486, 78.4987], [17.4501, 78.5002]]
    },
    "pipe_2_3": {
        "diameter_mm": 2200,
        "type": "Lowland Culvert Outfall Trunk",
        "coords": [[17.4501, 78.5002], [17.4521, 78.5022], [17.4536, 78.5037], [17.4551, 78.5052]]
    },
    "pipe_1_4": {
        "diameter_mm": 1000,
        "type": "Gravity Auxiliary Collector",
        "coords": [[17.4451, 78.4952], [17.4446, 78.5022], [17.4449, 78.5067], [17.4451, 78.5102]]
    },
    "pipe_4_3": {
        "diameter_mm": 1400,
        "type": "Bypass Diversion Conduit",
        "coords": [[17.4451, 78.5102], [17.4491, 78.5092], [17.4526, 78.5077], [17.4551, 78.5052]]
    },
    "pipe_0_4": {
        "diameter_mm": 900,
        "type": "Lateral Collector",
        "coords": [[17.4401, 78.4902], [17.4396, 78.5002], [17.4411, 78.5067], [17.4451, 78.5102]]
    }
}

# Subsurface Inspection Chambers & Manholes
SUB_SURFACE_MANHOLES = [
    {"id": "MH-01", "name": "Residential Intake Manhole", "coords": [17.4401, 78.4902], "depth_m": 3.2, "type": "Drop Manhole"},
    {"id": "MH-02", "name": "Market Junction Collector Vault", "coords": [17.4451, 78.4952], "depth_m": 4.5, "type": "Junction Vault"},
    {"id": "MH-03", "name": "Lowland Underpass Sump Manhole", "coords": [17.4501, 78.5002], "depth_m": 6.8, "type": "Heavy Surcharge Pit"},
    {"id": "MH-04", "name": "Hospital Sector Main Outfall", "coords": [17.4551, 78.5052], "depth_m": 5.1, "type": "Discharge Outfall"},
    {"id": "MH-05", "name": "Bypass Trunk Diversion Chamber", "coords": [17.4451, 78.5102], "depth_m": 3.8, "type": "Auxiliary Chamber"}
]

def build_city_graph():
    G = nx.Graph()
    nodes = {
        0: {"id": "N0", "lat": 17.4400, "lon": 78.4900, "name": "Residential Sector"},
        1: {"id": "N1", "lat": 17.4450, "lon": 78.4950, "name": "Market Junction"},
        2: {"id": "N2", "lat": 17.4500, "lon": 78.5000, "name": "Lowland Underpass"},
        3: {"id": "N3", "lat": 17.4550, "lon": 78.5050, "name": "Hospital Sector"},
        4: {"id": "N4", "lat": 17.4450, "lon": 78.5100, "name": "Ring Road Bypass"}
    }
    for n_id, data in nodes.items():
        G.add_node(n_id, **data)

    edges = [
        (0, 1, 650, "street_0_1"),
        (1, 2, 750, "street_1_2"),
        (2, 3, 850, "street_2_3"),
        (1, 4, 1350, "street_1_4"),
        (4, 3, 1200, "street_4_3"),
        (0, 4, 1600, "street_0_4")
    ]
    for u, v, length, key in edges:
        geom = DETAILED_STREET_GEOMETRIES.get(key, [[nodes[u]["lat"], nodes[u]["lon"]], [nodes[v]["lat"], nodes[v]["lon"]]])
        G.add_edge(u, v, length=length, street_key=key, weight=length, geometry=geom)
    return G

G_city = build_city_graph()

def find_nearest_node(lat: float, lon: float, exclude_node: int = None) -> int:
    best_node = None
    min_dist = float("inf")
    for n, d in G_city.nodes(data=True):
        if exclude_node is not None and n == exclude_node:
            continue
        dist = math.hypot(d["lat"] - lat, d["lon"] - lon)
        if dist < min_dist:
            min_dist = dist
            best_node = n
    return best_node if best_node is not None else 0

def extract_detailed_path_geometry(path: list) -> list:
    if len(path) <= 1:
        n = path[0] if path else 0
        return [[G_city.nodes[n]["lat"], G_city.nodes[n]["lon"]]]

    full_coords = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = G_city.get_edge_data(u, v)
        if not edge_data:
            continue
        geom = edge_data.get("geometry", [])
        
        u_lat, u_lon = G_city.nodes[u]["lat"], G_city.nodes[u]["lon"]
        start_dist = math.hypot(geom[0][0] - u_lat, geom[0][1] - u_lon)
        end_dist = math.hypot(geom[-1][0] - u_lat, geom[-1][1] - u_lon)
        
        oriented_geom = geom if start_dist <= end_dist else list(reversed(geom))
        
        if full_coords and oriented_geom:
            full_coords.extend(oriented_geom[1:])
        else:
            full_coords.extend(oriented_geom)
    return full_coords

def calculate_safe_route(start_node: int, end_node: int, vehicle_type: str, flood_depths: dict, raw_start: list = None, raw_end: list = None):
    clearance = CLEARANCE_LIMITS.get(vehicle_type.lower(), 18.0)
    
    if start_node == end_node:
        end_node = (start_node + 2) % 5

    try:
        orig_path = nx.shortest_path(G_city, source=start_node, target=end_node, weight="length")
    except nx.NetworkXNoPath:
        orig_path = [start_node, end_node]

    G_temp = G_city.copy()
    flooded_segments_avoided = 0
    max_flood_depth_on_route = 0.0

    for u, v, data in G_temp.edges(data=True):
        depth = flood_depths.get(data["street_key"], 0.0)
        if depth >= clearance:
            G_temp[u][v]["weight"] = 1e9
            flooded_segments_avoided += 1
        else:
            penalty = 1.0 + (depth / clearance) ** 2 * 6.0
            G_temp[u][v]["weight"] = data["length"] * penalty

    try:
        safe_path = nx.shortest_path(G_temp, source=start_node, target=end_node, weight="weight")
    except nx.NetworkXNoPath:
        safe_path = orig_path

    safe_coords = extract_detailed_path_geometry(safe_path)
    
    if raw_start and len(raw_start) == 2:
        safe_coords.insert(0, [float(raw_start[0]), float(raw_start[1])])
    if raw_end and len(raw_end) == 2:
        safe_coords.append([float(raw_end[0]), float(raw_end[1])])

    total_dist_m = sum(G_city[safe_path[i]][safe_path[i+1]]["length"] for i in range(len(safe_path)-1)) if len(safe_path) > 1 else 950
    
    for i in range(len(safe_path)-1):
        edge_data = G_city.get_edge_data(safe_path[i], safe_path[i+1])
        if edge_data:
            d = flood_depths.get(edge_data["street_key"], 0.0)
            max_flood_depth_on_route = max(max_flood_depth_on_route, d)

    speed_mps = (26.0 * 1000) / 3600
    est_time_min = max(2, round((total_dist_m / speed_mps) / 60))

    start_lat = safe_coords[0][0]
    start_lon = safe_coords[0][1]
    end_lat = safe_coords[-1][0]
    end_lon = safe_coords[-1][1]
    
    return {
        "status": "success",
        "path_nodes": safe_path,
        "coordinates": safe_coords,
        "distance_km": round(total_dist_m / 1000.0, 2),
        "estimated_time_min": est_time_min,
        "max_depth_cm": max_flood_depth_on_route,
        "avoided_segments_count": flooded_segments_avoided,
        "vehicle_type": vehicle_type,
        "clearance_cm": clearance,
        "google_maps_url": f"https://www.google.com/maps/dir/?api=1&origin={start_lat},{start_lon}&destination={end_lat},{end_lon}&travelmode=driving"
    }
