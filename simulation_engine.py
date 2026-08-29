import math

def run_coupled_simulation(rain_rate_mm: float, forecast_min: int, blockage_percent: float, G_city) -> dict:
    """
    Physics-guided Rainfall -> Surface -> Drainage Graph -> Surcharge -> Street Flood Engine.
    """
    results = {}
    
    # Runoff parameters
    CATCHMENT_AREA_SQM = 45000  # Assumed catchment per node
    RUNOFF_COEFF = 0.85         # High imperviousness (Urban roads/buildings)
    
    # 1. Rainfall to Runoff
    # rain_rate_mm is per hour. Convert to m/s: / 1000 / 3600
    rain_m_s = rain_rate_mm / 1000.0 / 3600.0
    base_inflow_m3s = rain_m_s * CATCHMENT_AREA_SQM * RUNOFF_COEFF
    
    # Accumulation factor based on forecast horizon
    time_factor = min(1.0, forecast_min / 60.0)
    current_inflow = base_inflow_m3s * (0.5 + 0.5 * time_factor)

    for u, v, data in G_city.edges(data=True):
        street_key = data["street_key"]
        
        # 2. Digital Twin Drainage Graph lookup
        pipe_capacity = data.get("capacity", 0.35)
        
        # 3. Apply blockage ("What-If" Simulator)
        actual_capacity = pipe_capacity * (1.0 - (blockage_percent / 100.0))
        
        # 4. Capacity Test & Surcharge Calculation
        excess_flow = max(0.0, current_inflow - actual_capacity)
        
        # 5. Surcharge -> Street Flood Depth (cm)
        # Volume accumulated over forecast_min = excess (m3/s) * time (s)
        street_area = data["length"] * 12.0  # Assumed 12m street width
        
        if excess_flow > 0:
            accumulated_volume = excess_flow * (forecast_min * 60)
            depth_m = accumulated_volume / street_area
            depth_cm = depth_m * 100.0
        else:
            depth_cm = 0.0
            
        # Topographic depression pooling (lowland nodes gather more water)
        elevation = G_city.nodes[v].get("street_elevation", 100.0)
        if elevation < 98.0 and rain_rate_mm > 10:
            # Add pooling depth based on time and rain intensity
            depth_cm += (rain_rate_mm * 0.15) * time_factor
            
        # 6. Explainability Metrics Formulation
        cause = f"Drain Node {G_city.nodes[u]['id']} overload" if excess_flow > 0 else "Normal"
        if elevation < 98.0 and excess_flow == 0 and depth_cm > 0:
            cause = "Topographic depression pooling"
            
        results[street_key] = {
            "depth_cm": round(depth_cm, 1),
            "inflow": round(current_inflow, 2),
            "capacity": round(actual_capacity, 2),
            "excess": round(excess_flow, 2),
            "cause": cause,
            "time_to_flood": max(5, int(45 - (rain_rate_mm * 0.2))) if depth_cm > 5 else None
        }
        
    return results
