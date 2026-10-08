# Intelligent Path Planner (IPP) — System Documentation

This document provides a technical overview of the Intelligent Path Planner (IPP) system, detailing the backend (`main.py`) and frontend (`map.js`) architectures, data flows, and geodetic transformation pipelines.

## System Overview

The IPP is a web-based Ground Control Station (GCS) and mission planner designed for Unmanned Aerial Vehicles (UAVs) and Unmanned Ground Vehicles (UGVs). It leverages a Python backend for heavy computational tasks (geospatial processing, ROS 2 integration, flight simulation) and a JavaScript MapLibre frontend for high-performance 3D visualization.

---

## Backend Architecture (`main.py`)

The backend is built using **NiceGUI**, which runs on an asynchronous FastAPI/Uvicorn event loop. It serves the web application, manages mission state, and handles precise coordinate transformations.

### Core Components

* **Application State (`state` dictionary):** Acts as the single source of truth. It stores current vehicle telemetry (longitude, latitude, MSL altitude), generated routes, drawn boundaries, selected map servers, and flight parameters (speed, AGL, azimuth).
* **Geodetic Transformation Engine (`pyproj`):**
To ensure centimeter-level accuracy in the Swiss coordinate system, the backend completely bypasses the browser's standard WGS84 calculations.
* **Browser Input:** Receives raw Web Mercator (EPSG:3857) meters from `map.js`.
* **Swiss Grid (LV95):** Transforms EPSG:3857 to EPSG:2056 (CH1903+ / LV95) for precise local processing and elevation querying.
* **ITRF2020 / WGS84 3D:** Uses Swisstopo grid shift files (`CHGeo2004.tif` and `CHENyx06.tif`) to transform the Swiss position and LN02 orthometric height into absolute ITRF2020 3D (EPSG:9000) for flight controllers and ROS 2 RTK streams.


* **Elevation Resolver (`get_elevation_and_true_pos`):**
* **Offline Mode:** Uses `rasterio` and `shapely` to sample precise ground elevations from user-uploaded `.tif` (GeoTIFF) files (swissALTI3D).
* **Online Fallback:** Uses `httpx` to query the live Swisstopo REST API if no local offline data covers the requested coordinate.


* **Path Generation (`generate_coverage_path`):** Uses `shapely` polygons and affine transformations to generate "Lawnmower" or "Grid" coverage patterns within a user-defined boundary. It samples elevation at regular intervals to create a terrain-following 3D route.
* **Asynchronous Loops:**
* `poll_waypoints()`: Polls the frontend at 10Hz to retrieve queued user clicks. It handles WebSockets timeouts gracefully and processes clicks based on the active mode (Boundary, Waypoints, Set Start).
* `flight_controller()`: A 10Hz simulation loop that moves the UAV marker along the generated 3D route based on the selected speed multiplier.



---

## Frontend Architecture (`map.js`)

The frontend is a lightweight JavaScript client utilizing **MapLibre GL JS** to render 3D maps, telemetry, and vector data natively in the browser via WebGL.

### Core Components

* **Map Initialization (`initMap`):**
Instantiates the MapLibre canvas. It configures the default style, compass, pitch/bearing limits, and injects an OpenStreetMap raster layer and an AWS Terrarium DEM (Digital Elevation Model) source for 3D terrain extrusion.
* **Layer Management:**
Uses MapLibre's data-driven styling and GeoJSON sources.
* `boundary`: Renders semi-transparent polygons, dashed outlines, and numbered vertex points.
* `path`: Renders the generated route as a solid line with waypoints.
* `uav-shadow`: Renders a flat, geographically accurate ground shadow directly beneath the UAV.
* `uav-marker`: Uses `fill-extrusion` to render the UAV as a true 3D disk floating at the correct Above Ground Level (AGL) altitude.


* **Click Interception & Projection:**
Overrides standard WGS84 click handling. When a user clicks the map, `map.js` calculates the raw EPSG:3857 Web Mercator coordinate (in meters relative to the Earth's radius) and pushes it to `window.waypointQueue` for the Python backend to ingest.
* **Dynamic Update Functions:**
Exposes global JavaScript functions called by the Python backend via WebSockets:
* `updateUAV(lng, lat, alt_msl, agl, uavSize)`: Recalculates the 32-point polygon for the UAV disk and shadow based on the current camera zoom (meters per pixel) and updates the extrusion data.
* `updatePath(geojson)` / `updateBoundary(geojson)`: Hot-swaps the underlying GeoJSON data for immediate visual updates.
* `syncServers(servers)`: Dynamically adds or removes active custom raster and DEM tile sources based on the user's UI selections.



---

## Data Flow: Waypoint Creation

1. **User Action:** The user clicks the 3D map in the browser.
2. **Frontend (`map.js`):** Translates the click into Web Mercator meters and stores it in a JavaScript array.
3. **Backend Bridge (`poll_waypoints`):** Python retrieves the array via an asynchronous WebSocket request.
4. **Transformation:** Python converts the Web Mercator coordinate into Swiss LV95 (EPSG:2056).
5. **Elevation:** Python queries offline GeoTIFFs or the Swisstopo API for the LN02 height at the LV95 coordinate.
6. **Datum Shift:** Python uses `CHGeo2004` and `CHENyx06` grids to convert the LV95/LN02 point into an absolute ITRF2020 3D coordinate.
7. **State Update:** The new 3D coordinate is appended to the mission state.
8. **UI Refresh:** Python calls `window.updatePath()` to render the new route in the browser.

---
---

## 1. Frontend Implementation (`map.js`)

The JavaScript client initializes the MapLibre GL JS engine, manages 3D WebGL rendering layers, and intercepts user interactions to feed the Python backend.

**Global Initialization & Map Canvas**
The system bootstraps the 3D map environment, configuring OpenStreetMap as the base raster tile and AWS Terrarium as the `raster-dem` for 3D elevation extrusion. It establishes empty GeoJSON sources for paths, boundaries, and the UAV.

```javascript
window.waypointQueue = []; // Stores EPSG:3857 map clicks

window.initMap = function() {
    window.mapInstance = new maplibregl.Map({
        container: 'map',
        style: {
            'version': 8,
            'sources': { /* ... OSM and terrainSource definitions ... */ },
            'layers': [{ 'id': 'osm', 'type': 'raster', 'source': 'osm' }],
            'terrain': { 'source': 'terrainSource', 'exaggeration': 1.5 }
        },
        center: [window.MAP_CONFIG.lng, window.MAP_CONFIG.lat],
        zoom: 14.5, pitch: 65, maxPitch: 85   
    });

    window.mapInstance.on('load', () => {
        // Initializes empty GeoJSON sources and styling layers
        // e.g., boundary, path, uav-shadow, uav-marker (fill-extrusion)
    });
};

```

**Web Mercator Click Interception**
Overrides standard WGS84 click handling. When a user clicks the map, it calculates the raw EPSG:3857 Web Mercator coordinate (in meters relative to the Earth's radius) to prevent precision loss before sending it to Python.

```javascript
window.mapInstance.on('click', (e) => {
    const mercatorCoords = maplibregl.MercatorCoordinate.fromLngLat(e.lngLat);
    const earthRadius = 6378137;
    const x = (mercatorCoords.x - 0.5) * (2 * Math.PI * earthRadius);
    const y = (0.5 - mercatorCoords.y) * (2 * Math.PI * earthRadius);
    
    window.waypointQueue.push([x, y]);
});

```

**Dynamic 3D UAV Rendering**
Recalculates the geometric shape of the UAV marker and its shadow. It scales the marker's physical size based on the current camera zoom level and calculates the extrusion base and height to make the drone "hover".

```javascript
window.updateUAV = function(lng, lat, alt_msl, agl, uavSize) {
    const currentZoom = window.mapInstance.getZoom();
    const metersPerPixel = (156543.03392 * Math.cos(lat * Math.PI / 180)) / Math.pow(2, currentZoom);
    const radiusMeters = (uavSize / 2.0) * metersPerPixel; 
    
    // Generate 32-point circle geometry
    const circleCoords = [];
    /* ... trigonometry loop ... */
    
    const thickness = Math.min(0.5, radiusMeters / 2.0);
    window.mapInstance.getSource('uav-marker').setData({
        'type': 'Feature',
        'properties': { 'base': agl - thickness, 'height': agl + thickness },
        'geometry': { 'type': 'Polygon', 'coordinates': [circleCoords] }
    });
};

```

**Data Injection Wrappers**
Safely push newly computed GeoJSON FeatureCollections from the Python backend directly into the active MapLibre rendering buffers.

```javascript
window.updatePath = function(geojson) {
    if (window.mapInstance && window.mapInstance.getSource('path')) {
        window.mapInstance.getSource('path').setData(geojson);
    }
};

```

---

## 2. Backend Implementation (`main.py`)

The Python file manages the application state, geodetic math, UI generation via NiceGUI, and the flight simulation loop.

**Geodetic Transformation Engine**
Defines robust `pyproj.Transformer` instances to handle datum shifts between the web frontend, local Swiss GIS data, and ITRF2020 3D.

```python
from pyproj import Transformer
import pyproj

pyproj.network.set_network_enabled(True)

# 1. Browser Web Mercator (3857) to Swiss LV95 (2056)
transformer_web_to_lv95 = Transformer.from_crs("EPSG:3857", "EPSG:2056", always_xy=True)

# 2. Swiss LV95 + LN02 Height -> ITRF2020 3D (Applies CHGeo2004 & CHENyx06)
transformer_swiss_to_itrf = Transformer.from_crs(
    "EPSG:2056+5728", "EPSG:9000", always_xy=True
)

```

**Elevation & Position Resolver**
Converts the Web Mercator input to LV95, extracts the exact LN02 pixel value from uploaded local GeoTIFFs (or falls back to the Swisstopo API), and feeds the data into the 3D ITRF2020 transformer to output drone-ready coordinates.

```python
def get_elevation_and_true_pos(mercator_x, mercator_y, open_rasters=None):
    lv95_e, lv95_n = transformer_web_to_lv95.transform(mercator_x, mercator_y)
    ground_elevation_ln02 = None
    
    # Check offline raster data
    if open_rasters is not None:
        for src, _ in open_rasters:
            if src.bounds.left <= lv95_e <= src.bounds.right and src.bounds.bottom <= lv95_n <= src.bounds.top:
                for val in src.sample([(lv95_e, lv95_n)]): 
                    ground_elevation_ln02 = float(val[0])
                    break

    # Fallback to Swisstopo API
    if ground_elevation_ln02 is None:
        response = httpx.get(f"https://api3.geo.admin.ch/rest/services/height?easting={lv95_e}&northing={lv95_n}&sr=2056")
        ground_elevation_ln02 = float(response.json().get('height', 530.0))

    return transformer_swiss_to_itrf.transform(lv95_e, lv95_n, ground_elevation_ln02)

```

**Coverage Path Generation**
Uses Shapely to construct a polygon from the user's boundary, rotates it based on the requested azimuth, sweeps line strings across it to generate an intersection grid, and rotates the resulting points back to their true geographical orientation.

```python
def generate_coverage_path(show_warning=True):
    poly = Polygon([pt['coords'] for pt in state['boundary']])
    centroid = poly.centroid
    angle_math = 90 - state['azimuth']
    rotated_poly = rotate(poly, -angle_math, origin=centroid)
    
    # ... calculates sweeps across bounding box (minx, miny, maxx, maxy) ...
    
    best_variant = select_closest_sweep_variant(variants)
    
    new_route_3d = []
    for pt in best_variant:
        rot_pt = rotate(Point(pt), angle_math, origin=centroid)
        lz = get_elevation_and_true_pos(rot_pt.x, rot_pt.y)[2] + state['agl_m']
        new_route_3d.append({'coords': [rot_pt.x, rot_pt.y, lz], 'action': state['current_action']})
        
    state['route'] = new_route_3d
    update_path_display()

```

**Asynchronous Event Loops**
The `poll_waypoints` function drains the frontend queue at 10Hz, transforming coordinates and updating state. The `flight_controller` calculates distance vectors to the next waypoint and interpolates the UAV's position for real-time 3D simulation.

```python
async def poll_waypoints():
    if not ui.context.client.has_socket_connection:
        return
        
    try:
        new_clicks = await ui.run_javascript(js_code, timeout=1.0)
        if new_clicks:
            for pt in new_clicks:
                true_lng, true_lat, ground_ellipsoid = get_elevation_and_true_pos(pt[0], pt[1])
                target_alt = ground_ellipsoid + state['agl_m']
                
                # Append to boundary or route based on state['click_mode']
                # ...
                
    except TimeoutError:
        pass # Client busy, skip tick

def flight_controller():
    if not state['running'] or not state['route']: return
    
    target = state['route'][state['target_idx']]['coords']
    dx, dy = target[0] - state['lng'], target[1] - state['lat']
    dist = math.sqrt(dx**2 + dy**2)
    
    if dist <= movement_budget:
        state['lng'], state['lat'] = target[0], target[1]
        state['target_idx'] += state['direction'] # Advance waypoint
    else:
        # Interpolate movement
        state['lng'] += (dx / dist) * movement_budget
        state['lat'] += (dy / dist) * movement_budget

```