import os
import time
import random
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict

from ai_engine import predict_street_depths, get_detailed_sensor_telemetry
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
    rain_rate_mm: float = 85.0
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
def get_nowcast(rain_rate_mm: float = 85.0, forecast_min: int = 60, drain_clogged: bool = True, coupled_1d2d_active: bool = True):
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
def get_drainage_network():
    sensor_telemetry = get_detailed_sensor_telemetry()
    pipes_geojson = []

    pipe_load_map = {
        "pipe_0_1": {"load": 64.2, "flow": 1.75, "speed": 1.35, "head": 2.2, "silt": 25.0, "surcharge": False},
        "pipe_1_2": {"load": 96.5, "flow": 3.65, "speed": 2.85, "head": 4.5, "silt": 72.0, "surcharge": True},
        "pipe_2_3": {"load": 99.1, "flow": 4.35, "speed": 0.75, "head": 6.4, "silt": 86.0, "surcharge": True},
        "pipe_1_4": {"load": 38.0, "flow": 1.05, "speed": 1.60, "head": 1.5, "silt": 14.0, "surcharge": False},
        "pipe_4_3": {"load": 44.5, "flow": 1.25, "speed": 1.70, "head": 1.7, "silt": 18.0, "surcharge": False},
        "pipe_0_4": {"load": 31.0, "flow": 0.85, "speed": 1.25, "head": 1.2, "silt": 12.0, "surcharge": False}
    }

    for pipe_key, meta in DRAINAGE_SEWER_TRUNKS.items():
        coords = meta["coords"]
        geojson_coords = [[pt[1], pt[0]] for pt in coords]
        st = pipe_load_map.get(pipe_key, {"load": 40.0, "flow": 1.0, "speed": 1.2, "head": 1.5, "silt": 15.0, "surcharge": False})
        
        pipes_geojson.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": geojson_coords
            },
            "properties": {
                "pipe_id": pipe_key,
                "diameter_mm": meta["diameter_mm"],
                "material": meta["material"],
                "inflow_zone": meta["inflow_zone"],
                "capacity_utilization": st["load"],
                "discharge_m3s": st["flow"],
                "flow_velocity_ms": st["speed"],
                "hydraulic_head_m": st["head"],
                "silt_buildup_pct": st["silt"],
                "surcharging": st["surcharge"]
            }
        })

    dynamic_manholes = []
    for mh in SUB_SURFACE_MANHOLES:
        mh_copy = dict(mh)
        fluc = round(random.uniform(-0.08, 0.08), 2)
        mh_copy["water_level_m"] = round(max(0.2, mh["water_level_m"] + fluc), 2)
        mh_copy["gas_ppm_h2s"] = round(max(1.0, mh["gas_ppm_h2s"] + random.uniform(-0.5, 0.5)), 1)
        mh_copy["surcharge_risk"] = "CRITICAL" if (mh_copy["water_level_m"] / mh_copy["depth_m"] > 0.85) else "NOMINAL"
        dynamic_manholes.append(mh_copy)

    return {
        "pipes": {"type": "FeatureCollection", "features": pipes_geojson},
        "manholes": dynamic_manholes,
        "sensors": sensor_telemetry,
        "scada_summary": {
            "surface_rain_detected_mm": 86.4,
            "underpass_2d_depth_cm": 45.8,
            "subsurface_total_flow_m3s": 12.9,
            "active_surcharge_alarms": 2
        }
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
