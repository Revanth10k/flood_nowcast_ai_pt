import torch
import torch.nn as nn
import torch.nn.functional as F
import random
import time

class GraphConvolution(nn.Module):
    def __init__(self, in_features, out_features):
        super(GraphConvolution, self).__init__()
        self.linear = nn.Linear(in_features, out_features)

    def forward(self, x, adj):
        deg = torch.sum(adj, dim=1)
        deg_inv_sqrt = torch.pow(deg + 1e-5, -0.5)
        d_mat = torch.diag(deg_inv_sqrt)
        norm_adj = torch.mm(torch.mm(d_mat, adj), d_mat)
        return self.linear(torch.matmul(norm_adj, x))

class HydroDrainageGNN(nn.Module):
    def __init__(self, in_features=4, hidden_dim=32):
        super(HydroDrainageGNN, self).__init__()
        self.gcn1 = GraphConvolution(in_features, hidden_dim)
        self.gcn2 = GraphConvolution(hidden_dim, 16)
        self.out_head = nn.Linear(16, 1)

        self.register_buffer('adj', torch.tensor([
            [1.0, 1.0, 0.0, 0.0, 1.0],
            [1.0, 1.0, 1.0, 0.0, 1.0],
            [0.0, 1.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 0.0, 1.0, 1.0]
        ], dtype=torch.float32))

    def forward(self, x):
        h = F.relu(self.gcn1(x, self.adj))
        h = F.relu(self.gcn2(h, self.adj))
        return F.relu(self.out_head(h))

model = HydroDrainageGNN(in_features=4, hidden_dim=32)
model.eval()

def predict_street_depths(rain_rate_mm: float = 85.0, forecast_min: int = 60, drain_clogged: bool = True, use_1d2d_coupled: bool = True) -> dict:
    intensity_ratio = max(0.2, rain_rate_mm / 60.0)
    clog_factor = 1.85 if (drain_clogged and use_1d2d_coupled) else (1.25 if drain_clogged else 1.0)

    underpass_depth = round(28.0 * intensity_ratio * clog_factor, 1)
    market_depth = round(14.0 * intensity_ratio * clog_factor, 1)
    bypass_depth = round(4.0 * intensity_ratio, 1)

    return {
        "street_0_1": round(market_depth * 0.6, 1),
        "street_1_2": round(underpass_depth * 0.88, 1),
        "street_2_3": underpass_depth,
        "street_1_4": round(bypass_depth * 1.2, 1),
        "street_4_3": round(bypass_depth * 1.0, 1),
        "street_0_4": round(bypass_depth * 0.8, 1),
    }

def get_detailed_sensor_telemetry() -> dict:
    """
    Simulates real-time hardware health, ultrasonic water levels,
    flow velocities, and battery telemetry for IoT sewer and surface stations.
    """
    return {
        "SN-01": {
            "name": "1D Subsurface Flow Node (Inlet Conduit)",
            "health_status": "Optimal",
            "health_pct": 98.4,
            "battery_v": 12.6,
            "signal_dbm": -64,
            "flow_speed_ms": round(random.uniform(1.4, 1.8), 2),
            "discharge_m3s": round(random.uniform(1.8, 2.2), 2),
            "water_depth_cm": round(random.uniform(7.8, 9.4), 1),
            "hydraulic_head_m": 2.3,
            "silt_buildup_pct": 22.0,
            "surcharge_risk": "NOMINAL",
            "last_ping": "1 sec ago"
        },
        "SN-02": {
            "name": "2D Surface Underpass Inundation Sensor",
            "health_status": "Warning (High Submersion)",
            "health_pct": 91.2,
            "battery_v": 12.1,
            "signal_dbm": -72,
            "flow_speed_ms": round(random.uniform(3.1, 3.7), 2),
            "discharge_m3s": round(random.uniform(4.4, 4.9), 2),
            "water_depth_cm": round(random.uniform(44.0, 47.8), 1),
            "hydraulic_head_m": 6.8,
            "silt_buildup_pct": 84.5,
            "surcharge_risk": "CRITICAL OVERFLOW",
            "last_ping": "Live Pulse"
        },
        "PUMP-01": {
            "name": "Municipal Aux Sump Station",
            "health_status": "Ready / Active Standby",
            "health_pct": 99.1,
            "battery_v": 24.2,
            "signal_dbm": -58,
            "flow_speed_ms": 0.0,
            "discharge_m3s": 0.0,
            "water_depth_cm": 12.0,
            "hydraulic_head_m": 1.1,
            "silt_buildup_pct": 8.0,
            "surcharge_risk": "STANDBY",
            "last_ping": "Live Sync"
        }
    }
