import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional

from ai_engine import predict_street_depths
from routing_engine import calculate_safe_route, find_nearest_node, G_city

app = FastAPI(title="HydroAI Urban Flood Platform - SIH 26085")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RouteRequest(BaseModel):
    start_node: Optional[int] = None
    end_node: Optional[int] = None
    start_coords: Optional[List[float]] = None
    end_coords: Optional[List[float]] = None
    vehicle_type: str = "sedan"
    rain_rate_mm: float = 80.0
    forecast_min: int = 60
    drain_clogged: bool = True

@app.get("/")
def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"error": "index.html not found"}

@app.get("/api/nowcast")
def get_nowcast(rain_rate_mm: float = 80.0, forecast_min: int = 60, drain_clogged: bool = True):
    depths = predict_street_depths(rain_rate_mm, forecast_min, drain_clogged)
    features = []
    
    for u, v, data in G_city.edges(data=True):
        key = data["street_key"]
        depth = depths.get(key, 0.0)
        
        geom_latlngs = data.get("geometry", [[G_city.nodes[u]["lat"], G_city.nodes[u]["lon"]], [G_city.nodes[v]["lat"], G_city.nodes[v]["lon"]]])
        geojson_coords = [[pt[1], pt[0]] for pt in geom_latlngs]

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": geojson_coords
            },
            "properties": {
                "street_name": f"{G_city.nodes[u]['name']} ↔ {G_city.nodes[v]['name']}",
                "water_depth_cm": depth,
                "drain_status": "Surcharged" if drain_clogged and depth > 20 else "Nominal"
            }
        })

    return {"type": "FeatureCollection", "features": features}

@app.post("/api/route")
def get_route(req: RouteRequest):
    start_n = req.start_node
    end_n = req.end_node

    if req.start_coords and len(req.start_coords) == 2:
        start_n = find_nearest_node(req.start_coords[0], req.start_coords[1])
    elif start_n is None:
        start_n = 0

    if req.end_coords and len(req.end_coords) == 2:
        end_n = find_nearest_node(req.end_coords[0], req.end_coords[1], exclude_node=start_n)
    elif end_n is None:
        end_n = 3

    depths = predict_street_depths(req.rain_rate_mm, req.forecast_min, req.drain_clogged)
    return calculate_safe_route(start_n, end_n, req.vehicle_type, depths, req.start_coords, req.end_coords)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)