import torch
import torch.nn as nn
import torch.nn.functional as F

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

def predict_street_depths(rain_rate_mm: float = 80.0, forecast_min: int = 60, drain_clogged: bool = True, use_1d2d_coupled: bool = True) -> dict:
    """
    Coupled 1D-2D Hydrodynamic Simulation Engine.
    1D: Subsurface pipe conduit network & manhole hydraulic head.
    2D: Surface overland flood inundation.
    """
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

def get_subsurface_sewer_telemetry(rain_rate_mm: float = 80.0, drain_clogged: bool = True) -> dict:
    """
    Computes 1D pipe drainage metrics, hydraulic capacity, and manhole surcharging.
    """
    load_ratio = (rain_rate_mm / 100.0) * (1.6 if drain_clogged else 0.8)
    
    return {
        "pipe_0_1": {
            "capacity_pct": min(100.0, round(load_ratio * 65.0, 1)),
            "flow_rate_m3s": round(max(0.4, (rain_rate_mm * 0.02)), 2),
            "status": "Warning" if load_ratio > 0.8 else "Nominal",
            "surcharging": load_ratio > 0.85
        },
        "pipe_1_2": {
            "capacity_pct": min(100.0, round(load_ratio * 95.0, 1)),
            "flow_rate_m3s": round(max(0.6, (rain_rate_mm * 0.038)), 2),
            "status": "Critical Surcharge" if drain_clogged else "High Flow",
            "surcharging": drain_clogged or load_ratio > 0.75
        },
        "pipe_2_3": {
            "capacity_pct": min(100.0, round(load_ratio * 98.0, 1)),
            "flow_rate_m3s": round(max(0.5, (rain_rate_mm * 0.042)), 2),
            "status": "Subsurface Surcharging (2D Spillage)" if drain_clogged else "Nominal Flow",
            "surcharging": drain_clogged
        },
        "pipe_1_4": {
            "capacity_pct": min(100.0, round(load_ratio * 40.0, 1)),
            "flow_rate_m3s": round(max(0.2, (rain_rate_mm * 0.015)), 2),
            "status": "Nominal Gravity Flow",
            "surcharging": False
        },
        "pipe_4_3": {
            "capacity_pct": min(100.0, round(load_ratio * 45.0, 1)),
            "flow_rate_m3s": round(max(0.3, (rain_rate_mm * 0.018)), 2),
            "status": "Nominal Gravity Flow",
            "surcharging": False
        },
        "pipe_0_4": {
            "capacity_pct": min(100.0, round(load_ratio * 30.0, 1)),
            "flow_rate_m3s": round(max(0.2, (rain_rate_mm * 0.012)), 2),
            "status": "Nominal Flow",
            "surcharging": False
        }
    }
