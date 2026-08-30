import React, { useEffect, useRef, useState } from "react"
import L from "leaflet"
import "leaflet/dist/leaflet.css"

type Role = "citizen" | "responder" | "admin" | null
type Tab = "warnings" | "routes" | "sos" | "diagnostics"

const VEHICLES: Record<string, { label: string; clearance: number }> = {
  sedan: { label: "Car / Sedan", clearance: 18 },
  bike: { label: "Two-Wheeler / Bike", clearance: 10 },
  suv: { label: "SUV / 4x4", clearance: 30 },
  ambulance: { label: "Emergency / Ambulance", clearance: 35 },
}

export default function App() {
  const [role, setRole] = useState<Role>(null)
  const [activeTab, setActiveTab] = useState<Tab>("warnings")
  const [rainRate, setRainRate] = useState(80)
  const [drainClog, setDrainClog] = useState(true)
  const [vehicle, setVehicle] = useState("sedan")
  const [route, setRoute] = useState<any>(null)
  const [sos, setSos] = useState<any[]>([])
  const [areaAccess, setAreaAccess] = useState<Record<string, boolean>>({})
  const [pumpActive, setPumpActive] = useState(false)
  const [loginError, setLoginError] = useState("")
  const [search, setSearch] = useState("")

  const mapRef = useRef<L.Map | null>(null)
  const layers = useRef({
    streets: L.layerGroup(),
    route: L.layerGroup(),
    zones: L.layerGroup(),
    sensors: L.layerGroup(),
  })
  const markers = useRef({ start: null as L.Marker | null, end: null as L.Marker | null })

  const API = "" // Same-origin: works locally and on Render.

  useEffect(() => {
    if (!role || mapRef.current) return
    const map = L.map("flood-map", { zoomControl: false }).setView([17.4475, 78.5], 14)
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: "&copy; OpenStreetMap & CartoDB",
      maxZoom: 20,
    }).addTo(map)
    L.control.zoom({ position: "topright" }).addTo(map)
    Object.values(layers.current).forEach(l => l.addTo(map))
    mapRef.current = map

    if (role === "citizen" || role === "responder") {
      markers.current.start = L.marker([17.44, 78.49], {
        draggable: true,
        icon: L.divIcon({ html: '<div class="marker-start">A</div>', className: "", iconSize: [28,28], iconAnchor: [14,14] }),
      }).addTo(map).bindTooltip("Start")
      markers.current.end = L.marker([17.455, 78.505], {
        draggable: true,
        icon: L.divIcon({ html: '<div class="marker-end">B</div>', className: "", iconSize: [28,28], iconAnchor: [14,14] }),
      }).addTo(map).bindTooltip("Destination")
      markers.current.start.on("dragend", fetchRoute)
      markers.current.end.on("dragend", fetchRoute)
    }
    setTimeout(() => map.invalidateSize(), 100)
    fetchFloodData()
    if (role === "responder") fetchSOS()
    if (role === "admin") { fetchAreaAccess(); renderSensors() }
  }, [role])

  useEffect(() => {
    if (!mapRef.current) return
    fetchFloodData()
    if (role === "citizen" || role === "responder") fetchRoute()
    if (role === "admin") renderSensors()
  }, [rainRate, drainClog, vehicle, pumpActive])

  async function fetchFloodData() {
    if (!mapRef.current) return
    try {
      const res = await fetch(`${API}/api/nowcast?rain_rate_mm=${rainRate}&forecast_min=60&drain_clogged=${drainClog}`)
      const data = await res.json()
      layers.current.streets.clearLayers()
      const clearance = VEHICLES[vehicle].clearance
      L.geoJSON(data, {
        style: (f: any) => {
          const d = f.properties.water_depth_cm
          const blocked = d >= clearance
          const caution = d >= 10 && d < clearance
          return { color: blocked ? "#ef4444" : caution ? "#f59e0b" : "#64748b", weight: blocked ? 7 : caution ? 5 : 3, opacity: .9 }
        },
        onEachFeature: (f: any, layer: any) => layer.bindPopup(`<b>${f.properties.street_name}</b><br>Water depth: <b>${f.properties.water_depth_cm} cm</b>`),
      }).addTo(layers.current.streets)

      layers.current.zones.clearLayers()
      if (rainRate >= 50) {
        L.circle([17.4485,78.4985], { color:"#ef4444", fillColor:"#ef4444", fillOpacity:.12, radius:600, weight:1 }).bindTooltip("Critical inundation zone").addTo(layers.current.zones)
        L.circle([17.444,78.5065], { color:"#f59e0b", fillColor:"#f59e0b", fillOpacity:.10, radius:400, weight:1 }).bindTooltip("Warning zone").addTo(layers.current.zones)
      }
    } catch (e) { console.warn("Flood API unavailable", e) }
  }

  async function fetchRoute() {
    const s = markers.current.start?.getLatLng(), e = markers.current.end?.getLatLng()
    if (!s || !e) return
    try {
      const res = await fetch(`${API}/api/route`, { method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ start_coords:[s.lat,s.lng], end_coords:[e.lat,e.lng], vehicle_type:vehicle, rain_rate_mm:rainRate, forecast_min:60, drain_clogged:drainClog })
      })
      const data = await res.json()
      setRoute(data)
      layers.current.route.clearLayers()
      if (data.coordinates?.length) L.polyline(data.coordinates, { color:"#22d3ee", weight:7, opacity:.95 }).addTo(layers.current.route)
    } catch (e) { console.warn("Route API unavailable", e) }
  }

  async function fetchSOS() {
    try { const r=await fetch(`${API}/api/sos/list`); const d=await r.json(); setSos(d.victims || []) } catch {}
  }
  async function fetchAreaAccess() {
    try { const r=await fetch(`${API}/api/municipal/area-access`); setAreaAccess(await r.json()) } catch {}
  }

  async function handleSOS() {
    const p = markers.current.start?.getLatLng() || {lat:17.445,lng:78.495}
    try {
      const r=await fetch(`${API}/api/sos/broadcast`, {method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({user_name:"Citizen (Live)",coords:[p.lat,p.lng],need_type:"stuck",details:"Emergency assistance requested from HydroAI.",location_shared:true,sector:"Secunderabad-Central"})
      })
      const d=await r.json(); if(d.record) setSos(x=>[...x,d.record])
    } catch {}
    alert("Emergency SOS broadcasted to responders.")
  }

  async function toggleArea(name:string) {
    const next=!areaAccess[name]
    setAreaAccess(x=>({...x,[name]:next}))
    await fetch(`${API}/api/municipal/area-access`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({sector_name:name,access_granted:next})})
  }

  function renderSensors() {
    if (!mapRef.current) return
    layers.current.sensors.clearLayers()
    const stations=[
      ["SN-01","Residential Outfall Sensor",17.441,78.491,6.2],
      ["SN-02","Underpass Sump Depth Sensor",17.4495,78.499,44.8],
      ["SN-03","Market Junction Flow Probe",17.4455,78.496,16.8],
    ]
    stations.forEach(([id,name,lat,lon,base])=>{
      const depth=(Number(base)*(rainRate/80)*(drainClog?1.4:1)*(pumpActive?.75:1)).toFixed(1)
      const critical=Number(depth)>25
      L.marker([Number(lat),Number(lon)],{icon:L.divIcon({html:`<div class="sensor-dot ${critical?"critical":"normal"}">⌁</div>`,className:"",iconSize:[28,28],iconAnchor:[14,14]})})
       .bindPopup(`<b>${name}</b><br>ID: ${id}<br>Live depth: <b>${depth} cm</b>`).addTo(layers.current.sensors)
    })
    ;[
      ["PUMP-01","Secunderabad Central Sump",17.448,78.502,"4.5 m³/s"],
      ["PUMP-02","Ring Road Discharge Pump",17.444,78.508,"3.2 m³/s"]
    ].forEach(([id,name,lat,lon,cap])=>L.marker([Number(lat),Number(lon)],{icon:L.divIcon({html:`<div class="pump-dot">⚙</div>`,className:"",iconSize:[30,30],iconAnchor:[15,15]})}).bindPopup(`<b>${name}</b><br>${id}<br>Capacity: ${cap}<br>Status: ONLINE`).addTo(layers.current.sensors))
  }

  function enter(r:Role) {
    setRole(r); setActiveTab(r==="admin"?"diagnostics":r==="responder"?"sos":"warnings")
    setTimeout(()=>mapRef.current?.invalidateSize(),100)
  }
  function adminLogin(e:React.FormEvent) {
    e.preventDefault()
    const pass=(document.getElementById("adminPass") as HTMLInputElement)?.value
    if(pass==="sih2026" || pass==="admin123") { setLoginError(""); enter("admin") } else setLoginError("Invalid passcode. Use sih2026.")
  }
  function shelter() {
    markers.current.end?.setLatLng([17.455,78.505]); fetchRoute()
    setActiveTab("routes")
  }

  if (!role) return <div className="auth-screen">
    <div className="auth-card">
      <div className="brand-mark">≈</div><h1>HydroAI</h1>
      <p>Urban Flood Intelligence & Safe Transit</p>
      <div className="auth-grid">
        <button onClick={()=>enter("citizen")}><b>Citizen / Commuter</b><small>Safe routes, flood warnings & SOS</small></button>
        <button onClick={()=>enter("responder")}><b>First Responder</b><small>Victim requests & emergency routing</small></button>
      </div>
      <form onSubmit={adminLogin} className="admin-login"><label>Municipal Authority</label><input id="adminPass" type="password" placeholder="Passcode: sih2026"/>{loginError&&<span>{loginError}</span>}<button>Enter Regional Command</button></form>
    </div>
  </div>

  return <div className="app">
    <aside className="sidebar">
      <header><div><div className="logo"><span>≈</span> HydroAI</div><small>{role==="citizen"?"Citizen Dashboard":role==="responder"?"Responder Field Unit":"Regional Authority"}</small></div><button className="switch" onClick={()=>{setRole(null);mapRef.current?.remove();mapRef.current=null}}>Switch</button></header>
      <div className="search"><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search address or region..."/><span>⌕</span></div>

      <nav className="tabs">
        {(role==="admin"?["diagnostics","warnings","sos"]:["warnings","routes","sos"]).map((t:any)=><button key={t} onClick={()=>setActiveTab(t)} className={activeTab===t?"active":""}>{t==="warnings"?"Warnings":t==="routes"?"Safe Routes":t==="sos"?"SOS": "Command"}</button>)}
      </nav>

      <section className="panel-scroll">
        {role==="citizen" && activeTab==="warnings" && <div className="stack">
          <div className="eyebrow">LIVE FLOOD STATUS</div>
          <div className="alert-card"><div className="alert-title">● Critical inundation</div><h2>Lowland Underpass</h2><p>Water levels exceed safe clearance on the central lowland corridor. Avoid flooded segments.</p><div className="stat-row"><span>Nowcast <b>{rainRate} mm/hr</b></span><span>Drain <b>{drainClog?"Surcharged":"Nominal"}</b></span></div></div>
          <button className="danger-btn" onClick={handleSOS}>REQUEST EMERGENCY HELP</button>
          <div className="info-card"><b>Forecast horizon</b><span>60 minutes</span><small>Live GNN-assisted street inundation nowcast</small></div>
        </div>}

        {role==="citizen" && activeTab==="routes" && <div className="stack">
          <div className="eyebrow">SAFE TRANSIT</div>
          <div className="card"><label>Vehicle & clearance</label><select value={vehicle} onChange={e=>setVehicle(e.target.value)}>{Object.entries(VEHICLES).map(([k,v])=><option key={k} value={k}>{v.label} — {v.clearance} cm</option>)}</select><button className="primary-btn" onClick={fetchRoute}>Calculate Safe Route</button><button className="secondary-btn" onClick={shelter}>Evacuate to Shelter</button></div>
          <RouteCard route={route}/>
        </div>}

        {role==="citizen" && activeTab==="sos" && <div className="stack"><div className="eyebrow">EMERGENCY</div><div className="card"><h2>Need immediate help?</h2><p>Broadcast your location to responders. Location sharing is explicitly included with this request.</p><button className="danger-btn" onClick={handleSOS}>BROADCAST SOS</button></div></div>}

        {role==="responder" && activeTab==="sos" && <div className="stack"><div className="eyebrow">ACTIVE SOS REQUESTS</div>{sos.length? sos.map((x:any)=><div className="sos-card" key={x.id}><b>{x.need_type?.toUpperCase()} · {x.id}</b><h3>{x.details||"Emergency assistance requested"}</h3><small>{x.sector} · {x.timestamp}</small><button onClick={()=>{markers.current.end?.setLatLng(x.coords);fetchRoute();setActiveTab("routes")}}>TARGET LOCATION →</button></div>):<div className="card">No active SOS requests.</div>}</div>}
        {role==="responder" && activeTab==="warnings" && <div className="stack"><div className="eyebrow">FIELD BRIEF</div><div className="alert-card"><div className="alert-title">● HIGH RISK</div><h2>Lowland Underpass</h2><p>Use the safe-route engine before dispatch. Red segments indicate vehicle-specific roadblocks.</p></div><button className="primary-btn" onClick={()=>{fetchRoute();setActiveTab("routes")}}>Route to Victim</button></div>}
        {role==="responder" && activeTab==="routes" && <div className="stack"><div className="eyebrow">RESPONSE ROUTING</div><div className="card"><label>Response vehicle</label><select value={vehicle} onChange={e=>setVehicle(e.target.value)}>{Object.entries(VEHICLES).map(([k,v])=><option key={k} value={k}>{v.label}</option>)}</select><button className="primary-btn" onClick={fetchRoute}>Calculate Safe Route</button></div><RouteCard route={route}/></div>}

        {role==="admin" && activeTab==="diagnostics" && <div className="stack"><div className="eyebrow">REGIONAL COMMAND</div><div className="card"><div className="label-row"><label>Simulation rainfall</label><b>{rainRate} mm/hr</b></div><input type="range" min="10" max="150" step="5" value={rainRate} onChange={e=>setRainRate(Number(e.target.value))}/><label className="check"><input type="checkbox" checked={drainClog} onChange={e=>setDrainClog(e.target.checked)}/> Drain clogging / surcharge</label></div><div className="metrics"><div><small>Underpass</small><b>{(rainRate*.55*(drainClog?1.5:1)*(pumpActive?.7:1)).toFixed(1)} cm</b><span>SN-02 · {rainRate*.55>25?"CRITICAL":"MONITOR"}</span></div><div><small>Drain outflow</small><b>{Math.max(.8,rainRate*.035).toFixed(1)} m³/s</b><span>NOMINAL DISCHARGE</span></div></div><div className="card"><div className="label-row"><label>Auxiliary sump pumps</label><button className="tiny-btn" onClick={()=>setPumpActive(!pumpActive)}>{pumpActive?"Deactivate":"Deploy Aux Pump"}</button></div><button className="primary-btn" onClick={()=>alert("CAP emergency broadcast dispatched to registered citizens.")}>SEND CAP ALERT</button><button className="secondary-btn" onClick={()=>{const txt=`HYDROAI INCIDENT LOG\\nGenerated: ${new Date().toLocaleString()}\\nRainfall: ${rainRate} mm/hr\\nDrain surcharge: ${drainClog}\\nAux pumps: ${pumpActive?"DEPLOYED":"STANDBY"}`;const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([txt],{type:"text/plain"}));a.download="HydroAI_Incident_Log.txt";a.click()}}>EXPORT INCIDENT LOG</button></div></div>}

        {role==="admin" && activeTab==="warnings" && <div className="stack"><div className="eyebrow">AREA ACCESS</div>{Object.entries(areaAccess).map(([name,val])=><div className="access-row" key={name}><div><b>{name}</b><small>Responder location visibility</small></div><button onClick={()=>toggleArea(name)} className={val?"on":"off"}>{val?"GRANTED":"BLOCKED"}</button></div>)}<div className="card"><b>Sensor network</b><p>SN-01, SN-02, SN-03 and pump stations are rendered on the map in command mode.</p></div></div>}
        {role==="admin" && activeTab==="sos" && <div className="stack"><div className="eyebrow">INCIDENT QUEUE</div>{sos.map((x:any)=><div className="sos-card" key={x.id}><b>{x.id} · {x.need_type}</b><p>{x.details}</p><small>{x.sector} · {x.timestamp}</small></div>)}</div>}
      </section>

      {route && <div className="route-mini"><span>SAFE ROUTE</span><b>{route.distance_km} km · {route.estimated_time_min} min</b><small>Max depth {route.max_depth_cm} cm · avoids {route.avoided_segments_count} roadblocks</small></div>}
    </aside>
    <main className="map-wrap"><div id="flood-map"></div><div className="map-status"><span className="live-dot"></span> LIVE NOWCAST <b>{rainRate} mm/hr</b></div><div className="legend"><b>RISK LEVEL</b><span><i className="red"></i>Severe / Blocked</span><span><i className="amber"></i>Warning / Moderate</span><span><i className="gray"></i>Safe / Navigable</span><span><i className="cyan"></i>Active Safe Route</span></div></main>
  </div>
}

function RouteCard({route}:{route:any}) {
  if(!route) return null
  return <div className="route-result"><div className="route-head"><span>✓ Safe route active</span><b>{route.avoided_segments_count} roadblocks avoided</b></div><div className="route-stats"><div><small>Distance</small><b>{route.distance_km} km</b></div><div><small>ETA</small><b>{route.estimated_time_min} min</b></div><div><small>Max depth</small><b>{route.max_depth_cm} cm</b></div></div>{route.google_maps_url&&<a href={route.google_maps_url} target="_blank" rel="noreferrer">OPEN GOOGLE MAPS →</a>}</div>
}
