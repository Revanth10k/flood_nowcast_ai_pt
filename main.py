import os
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict

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

# In-Memory Database for Area Clearance and SOS Signals
MUNICIPAL_AREA_ACCESS = {
    "Secunderabad-Central": True,
    "Lowland-Underpass-Zone": True,
    "Market-Sector": False
}

SOS_RECORDS: List[Dict] = [
    {
        "id": "SOS-101",
        "user_name": "Public User (Ramesh)",
        "coords": [17.4490, 78.4985],
        "need_type": "medical",  # medical, stuck, essentials
        "details": "Diabetic patient trapped in flooded car, high water level.",
        "location_shared": True,
        "sector": "Lowland-Underpass-Zone",
        "via_sms": False,
        "timestamp": "10:14 AM",
        "status": "pending"
    },
    {
        "id": "SOS-102",
        "user_name": "Public User (Anitha)",
        "coords": [17.4452, 78.4960],
        "need_type": "essentials",
        "details": "Stranded on 1st floor, requires clean drinking water and food rations.",
        "location_shared": True,
        "sector": "Market-Sector",
        "via_sms": True,
        "timestamp": "10:30 AM",
        "status": "pending"
    }
]

class RouteRequest(BaseModel):
    start_node: Optional[int] = None
    end_node: Optional[int] = None
    start_coords: Optional[List[float]] = None
    end_coords: Optional[List[float]] = None
    vehicle_type: str = "sedan"
    rain_rate_mm: float = 80.0
    forecast_min: int = 60
    drain_clogged: bool = True

class SOSBeaconRequest(BaseModel):
    user_name: str = "Public User"
    coords: List[float]
    need_type: str  # 'stuck', 'medical', 'essentials'
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

# ================= SOS & FIRST RESPONDER ENDPOINTS =================

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
    """Returns SOS requests filtered by location sharing consent and municipal area clearance."""
    active_victims = []
    for r in SOS_RECORDS:
        # Check if user opted in to share location and area clearance is provided by Municipal authority
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
