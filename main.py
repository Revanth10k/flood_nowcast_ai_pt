import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict

from ai_engine import predict_street_depths, get_subsurface_sewer_telemetry
from routing_engine import (
    calculate_safe_route, 
    find_nearest_node, 
    G_city, 
    DRAINAGE_SEWER_TRUNKS, 
    SUB_SURFACE_MANHOLES
)

app = FastAPI(title="HydroAI Urban Flood Platform - SIH 26085")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MUNICIPAL_AREA_ACCESS = {
    "Secunderabad-Central": True,
    "Lowland-Underpass-Zone": True,
    "Market-Sector": False
}

SOS_RECORDS: List[Dict] = []

class RouteRequest(BaseModel):
    start_node: Optional[int] = None
    end_node: Optional[int] = None
    start_coords: Optional[List[float]] = None
    end_coords: Optional[List[float]] = None
    vehicle_type: str = "sedan"
    rain_rate_mm: float = 80.0
    forecast_min: int = 60
    drain_clogged: bool = True
    coupled_1d2d_active: bool = True

class SOSBeaconRequest(BaseModel):
    user_name: str = "Public User"
    coords: List[float]
    need_type: str 
    details: Optional[str] = ""
    location_shared: bool = True
    via_sms: bool = False
    sector: str = "Secunderabad-Central"

class AreaAccessToggleRequest(BaseModel):
    sector_name: str
    access_granted: bool

@app.get("/")
def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"error": "index.html not found"}

@app.get("/api/nowcast")
def get_nowcast(rain_rate_mm: float = 80.0, forecast_min: int = 60, drain_clogged: bool = True, coupled_1d2d_active: bool = True):
    depths = predict_street_depths(rain_rate_mm, forecast_min, drain_clogged, coupled_1d2d_active)
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
                "drain_status": "Surcharged (Subsurface 1D Backup)" if (drain_clogged and depth > 20) else "Nominal Flow"
            }
        })

    return {"type": "FeatureCollection", "features": features}

@app.get("/api/municipal/drainage-network")
def get_drainage_network(rain_rate_mm: float = 80.0, drain_clogged: bool = True):
    """
    Supplies complete 1D Subsurface Drainage & Sewer System Network telemetry to Municipal Admin.
    """
    telemetry = get_subsurface_sewer_telemetry(rain_rate_mm, drain_clogged)
    pipes_geojson = []

    for pipe_key, meta in DRAINAGE_SEWER_TRUNKS.items():
        coords = meta["coords"]
        geojson_coords = [[pt[1], pt[0]] for pt in coords]
        pipe_stats = telemetry.get(pipe_key, {"capacity_pct": 50.0, "flow_rate_m3s": 1.2, "status": "Nominal", "surcharging": False})
        
        pipes_geojson.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": geojson_coords
            },
            "properties": {
                "pipe_id": pipe_key,
                "diameter_mm": meta["diameter_mm"],
                "pipe_type": meta["type"],
                "capacity_utilization": pipe_stats["capacity_pct"],
                "discharge_m3s": pipe_stats["flow_rate_m3s"],
                "status": pipe_stats["status"],
                "surcharging": pipe_stats["surcharging"]
            }
        })

    return {
        "pipes": {"type": "FeatureCollection", "features": pipes_geojson},
        "manholes": SUB_SURFACE_MANHOLES,
        "telemetry_summary": telemetry
    }

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

    depths = predict_street_depths(req.rain_rate_mm, req.forecast_min, req.drain_clogged, req.coupled_1d2d_active)
    return calculate_safe_route(start_n, end_n, req.vehicle_type, depths, req.start_coords, req.end_coords)

@app.post("/api/sos/broadcast")
def create_sos(req: SOSBeaconRequest):
    new_id = f"SOS-{len(SOS_RECORDS) + 101}"
    record = {
        "id": new_id,
        "user_name": req.user_name,
        "coords": req.coords if req.location_shared else [17.4450, 78.4950],
        "need_type": req.need_type,
        "details": req.details,
        "location_shared": req.location_shared,
        "sector": req.sector,
        "via_sms": req.via_sms,
        "timestamp": time.strftime("%I:%M %p"),
        "status": "pending"
    }
    SOS_RECORDS.append(record)
    return {"status": "success", "message": "Emergency request registered", "record": record}

@app.get("/api/sos/list")
def list_sos():
    active_victims = []
    for r in SOS_RECORDS:
        sector_access = MUNICIPAL_AREA_ACCESS.get(r["sector"], True)
        if r["location_shared"]:
            r["area_access_granted"] = sector_access
            active_victims.append(r)
    return {"victims": active_victims, "municipal_area_access": MUNICIPAL_AREA_ACCESS}

@app.get("/api/municipal/area-access")
def get_area_access():
    return MUNICIPAL_AREA_ACCESS

@app.post("/api/municipal/area-access")
def set_area_access(req: AreaAccessToggleRequest):
    MUNICIPAL_AREA_ACCESS[req.sector_name] = req.access_granted
    return {"status": "success", "municipal_area_access": MUNICIPAL_AREA_ACCESS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
