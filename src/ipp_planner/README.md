# About <br> ISF's Intelligent Path Planner - IPP
The **Intelligent Path Planner (IPP)** is a web-based UAV mission planning and 3D simulation platform built with Python, NiceGUI, and MapLibre GL JS. It is designed to generate complex, terrain-following flight paths while visualizing the vehicle's movements in a fully interactive 3D map environment.

**Core Capabilities:**

* **Interactive 3D Mapping:** Renders a 3D globe where users can toggle default basemaps, enable 3D terrain meshes, or add custom online XYZ tile servers.
* **Advanced Path Generation:** Automatically computes "Lawnmower" or "Grid" coverage patterns within user-drawn boundaries. It features a real-time azimuth slider that dynamically rotates the pattern and mathematically routes the UAV to the optimal starting corner.
* **Terrain-Following & Geospatial Import:** Calculates precise Above Ground Level (AGL) altitudes by combining base map data with user-uploaded, high-resolution DSM, DTM, and Orthomosaic `.tif` files.
* **Live Flight Simulation:** Features a customizable 3D UAV marker with a geographically accurate ground shadow, dynamic speed controls, "Set Start" teleportation, and a live telemetry HUD tracking Longitude, Latitude, and Mean Sea Level (MSL) altitude.
* **Waypoint Actions & Looping:** Supports manual waypoint placement with assigned actions (e.g., Take Photo, Hover) and automatically detects closed routes to generate continuous orbiting loops.
* **Mission Export:** Downloads finalized flight paths and area boundaries as GeoJSON, KML, or KMZ files for deployment to actual flight hardware.

# Implemented functionality - An Overview
| Category | Feature / Requirement | Description |
| --- | --- | --- |
| **System Identity** | Project Title & Port | "intelligent path planer - IPP" running on a Python backend at port 8091 using NiceGUI and MapLibre GL JS. |
| **User Interface** | Persistent Planning Panel | A fixed top-left control card containing the ISF logo, boundary/waypoint selectors, action drop-downs, and coverage pattern settings. |
| **User Interface** | Floating Toolbars | Quick-access buttons for Flight Parameters, Uploads, Server Management, and Export, plus a vertical drone speed slider on the right side. |
| **Map & Visuals** | Online Server Manager | UI to toggle default map/terrain and add custom XYZ tile servers for both 2D raster basemaps and 3D terrain meshes (`raster-dem`). |
| **Map & Visuals** | 3D UAV & Shadow | The UAV is visualized as a 3D extruded disk with a custom physical size (in meters). Its ground shadow scales geographically to match physical dimensions regardless of zoom level. |
| **Map & Visuals** | Layer Filtering | Robust WebGL geometry filters ensuring polygons, lines, and points render simultaneously without crashing the MapLibre engine. |
| **Path Planning** | Start Point Selection | "Set Start" mode allowing the user to click the map to instantly teleport the UAV and sample the local elevation before mission start. |
| **Path Planning** | Coverage Algorithms | Auto-generates standard "Lawnmower" or intersecting "Grid" paths inside drawn boundaries, controlled by a customizable line spacing (m) parameter. |
| **Path Planning** | Live Azimuth Control | A bottom-center 0-180° slider (with a live rotating compass needle) that recalculates pattern heading in real-time, automatically routing the UAV to the nearest starting corner. |
| **Path Planning** | Continuous Looping | If a manual route's final waypoint is placed within 15 meters of the starting point, the path mathematically closes, causing the UAV to orbit endlessly. |
| **Path Planning** | Waypoint Actions | Ability to assign discrete actions (e.g., Take Photo, Start Video, Hover 5s) to individual waypoints or boundary nodes. |
| **Simulation** | Live Telemetry HUD | Bottom-left display actively tracking the UAV's Longitude, Latitude, absolute MSL (Mean Sea Level), and total waypoint count. |
| **Simulation** | Terrain Following | Real-time elevation sampling combining base map math with uploaded high-resolution data to maintain an exact AGL (Above Ground Level) target height. |
| **Data Management** | Local Geospatial Import | Upload `.tif` files directly to the server, categorized as DSM, DTM, or Orthomosaics. Includes a menu to toggle which files actively influence elevation calculations. |
| **Data Management** | Mission Export | Export drawn boundaries and calculated 3D flight paths directly to the user's machine as GeoJSON, KML, or KMZ files. |

# Additional Functionality: <br> Intelligent Path Planner (IPP) — ROS 2 Architecture & Feature Extension Specification

This document provides a comprehensive technical architecture and implementation roadmap to transition the Intelligent Path Planner (IPP) into an offline-capable, multi-robot, ROS 2-integrated ground control and planning platform.

## 1. ROS 2 Environment Integration & Asynchronous IPC

```
+-------------------------------------------------------------------------+
|                              ROS 2 Domain                               |
|                                                                         |
|  [ Robot Fleet ] --- /active_robots (std_msgs/String JSON) -------->+   |
|                  <-- /mission_data  (geometry_msgs/PoseArray) ------+   |
|                  --- /<robot_id>/nav_sat_fix (sensor_msgs/NavSatFix) -> |
+------------------------------------|------------------------------------+
                                     | rclpy Background Thread
                                     v
+------------------------------------+------------------------------------+
|                         IPP Server (Port 8091)                          |
|  +--------------------+   Thread-Safe   +----------------------------+  |
|  | ROS 2 Node Worker  | <=============> | NiceGUI / FastAPI Core     |  |
|  | (MultiThreadSpin)  |      Queue      | (Asyncio Event Loop)       |  |
|  +--------------------+                 +----------------------------+  |
|                                                       |                 |
|                                                       v                 |
|                                            Browser Client (MapLibre)    |
+-------------------------------------------------------------------------+

```

### Problem Statement

The planner must function as a first-class ROS 2 node that communicates seamlessly with the robot fleet over native middleware while keeping the NiceGUI / FastAPI event loop completely responsive and unblocked.

### Technical Implementation

#### Threading Model & Event Loop Decoupling

NiceGUI runs on an asynchronous Uvicorn/FastAPI event loop, whereas [rclpy](https://docs.ros.org/en/rolling/p/rclpy/) requires an executor to handle subscriptions, service calls, and timers. Running `rclpy.spin()` directly inside the async event loop causes starvation.

* **Solution**: Launch a dedicated daemon thread running `rclpy.spin()` with a `MultiThreadedExecutor`.
* **Cross-Thread Synchronization**:
* Incoming ROS data (robot lists, poses) is pushed into standard Python thread-safe queues or atomic dictionaries protected by `threading.Lock`.
* NiceGUI timers (`ui.timer(0.05, poll_ros_events)`) poll this shared memory state and dispatch UI updates via WebSockets to MapLibre GL JS.

#### Topic Contracts

| Topic Name | Direction | Message Type | Purpose |
| --- | --- | --- | --- |
| `/active_robots` | Subscription | `std_msgs/msg/String` (or custom `ipp_interfaces/msg/RobotList`) | Emits JSON-serialized telemetry and IDs of online robots. |
| `/mission_data` | Publication | `geometry_msgs/msg/PoseArray` or `std_msgs/msg/String` | Emits finalized waypoint missions containing 3D coordinates, headings, and payload triggers. |
| `/<robot_id>/nav_sat_fix` | Dynamic Subscription | `sensor_msgs/msg/NavSatFix` | Real-time GPS coordinate telemetry per robot. |
| `/<robot_id>/cmd` | Publication | `std_msgs/msg/String` | Interactive mission triggers (`START`, `PAUSE`, `ABORT`, `RTH`). |

#### Reference Implementation: `ros_bridge.py`

```python
import threading
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import NavSatFix
from geometry_msgs.msg import PoseArray, Pose

class IPPRosNode(Node):
    def __init__(self, state_lock, shared_state):
        super().__init__('intelligent_path_planner')
        self.state_lock = state_lock
        self.shared_state = shared_state
        self.pose_subs = {}

        # Core Topics
        self.create_subscription(String, '/active_robots', self._on_active_robots, 10)
        self.mission_pub = self.create_publisher(PoseArray, '/mission_data', 10)

    def _on_active_robots(self, msg: String):
        data = json.loads(msg.data)
        with self.state_lock:
            self.shared_state['active_robots'] = data
            for r in data:
                robot_id = r['id']
                if robot_id not in self.pose_subs:
                    self.pose_subs[robot_id] = self.create_subscription(
                        NavSatFix,
                        f'/{robot_id}/nav_sat_fix',
                        lambda p_msg, r_id=robot_id: self._on_robot_pose(r_id, p_msg),
                        10
                    )

    def _on_robot_pose(self, robot_id: str, msg: NavSatFix):
        with self.state_lock:
            if robot_id not in self.shared_state['robot_telemetry']:
                self.shared_state['robot_telemetry'][robot_id] = {}
            self.shared_state['robot_telemetry'][robot_id].update({
                'lat': msg.latitude,
                'lng': msg.longitude,
                'alt': msg.altitude,
            })

    def publish_mission(self, route_points):
        msg = PoseArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'earth'
        for pt in route_points:
            pose = Pose()
            pose.position.x = float(pt['coords'][0]) # Longitude
            pose.position.y = float(pt['coords'][1]) # Latitude
            pose.position.z = float(pt['coords'][2]) # Altitude MSL
            msg.poses.append(pose)
        self.mission_pub.publish(msg)

def start_ros_node(state_lock, shared_state):
    rclpy.init()
    node = IPPRosNode(state_lock, shared_state)
    thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    thread.start()
    return node

```

## 2. Offline GeoTIFF Tiling & Tile Serving

### Problem Statement

In field deployments (agricultural domains, GPS-denied environments, remote areas), internet connections are unavailable. The application must display high-resolution orthomosaics and 3D elevation terrains directly from uploaded `.tif` (GeoTIFF) files without relying on external tile servers like OpenStreetMap or AWS Terrarium.

```
+-----------------------------------------------------------------------+
|                       Offline Tiling Strategies                       |
|                                                                       |
|  [ Uploaded GeoTIFF ]                                                 |
|           |                                                           |
|           +---> Strategy A (Static Pre-Tiling):                       |
|           |     gdal2tiles.py ---> Static Folder /tiles/{z}/{x}/{y}   |
|           |                                                           |
|           +---> Strategy B (Dynamic COG Streaming):                   |
|                 rio-tiler + FastAPI Endpoint /api/tiles/{z}/{x}/{y}   |
+-----------------------------------------------------------------------+

```

### Technical Implementation

#### Strategy A: Static Offline Tiling via GDAL (Pre-computation)

* Convert GeoTIFF into directory structures conforming to standard Slippy Map Tile specifications (`/tiles/{z}/{x}/{y}.png`).
* **Tooling**: [GDAL Python Bindings](https://www.google.com/search?q=https://gdal.org/api/python_bindings.html) or `gdal2tiles.py`.
* **Execution**: Run background worker upon GeoTIFF upload:
```bash
gdal2tiles.py -p mercator -z 12-19 -w none input_ortho.tif ./static/tiles/ortho/

```


* **Serving**: Mount the folder directly in NiceGUI via `app.add_static_files('/tiles/ortho', './static/tiles/ortho')`.

#### Strategy B: Dynamic In-Memory Tiling via rio-tiler (On-demand)

Pre-tiling high-resolution drone orthomosaics can generate millions of image files, consuming time and disk I/O. Dynamic tiling extracts only the requested Web Mercator bounding box directly from a Cloud-Optimized GeoTIFF (COG).

* **Tooling**: [rio-tiler](https://cogeotiff.github.io/rio-tiler/) and [rasterio](https://rasterio.readthedocs.io/).
* **Implementation via FastAPI Endpoint**:
```python
from fastapi import Response
from rio_tiler.io import Reader
from nicegui import app

@app.get('/api/tiles/{source_id}/{z}/{x}/{y}.png')
async def serve_tile(source_id: str, z: int, x: int, y: int):
    file_path = get_geotiff_path(source_id)
    with Reader(file_path) as cog:
        img = cog.tile(x, y, z)
        content = img.render(img_format='PNG')
        return Response(content=content, media_type='image/png')

```
#### Offline 3D Terrain Engine (DEM / Terrarium Conversion)

MapLibre GL JS generates 3D surface mesh elevations using RGB-encoded DEM tiles.

* Convert raw elevation meters into Terrarium format:

$$\text{Elevation (m)} = (\text{Red} \times 256 + \text{Green} + \text{Blue} / 256) - 32768$$


* Python converts uploaded DTM/DSM GeoTIFFs to byte arrays using the formula above, serving them as an offline `raster-dem` source directly into `window.mapInstance.setTerrain()`.

## 3. Multi-Robot Tracking & Interactive Command UI

### Problem Statement

Operators must observe multiple autonomous vehicles operating simultaneously, distinguish their tracks, inspect vehicle states, and send execution commands (e.g., assign route, abort, start mission).

```
+-------------------------------------------------------------+
|               Multi-Robot Frontend Architecture             |
|                                                             |
|   MapLibre GeoJSON Source: 'fleet-markers'                  |
|   +-------------------------------------------------------+ |
|   | Feature 1: UAV-01 -> Coords, Color: #3b82f6, AGL: 30m | |
|   | Feature 2: UAV-02 -> Coords, Color: #10b981, AGL: 45m | |
|   | Feature 3: AGV-01 -> Coords, Color: #f59e0b, AGL: 0m  | |
|   +-------------------------------------------------------+ |
|                               |                             |
|          +--------------------+--------------------+        |
|          v                                         v        |
|   Map Visual Layer:                         NiceGUI Sidebar:|
|   Extruded 3D Disks per Robot               Robot Command   |
|   & Trajectory Ground Paths                 Cards & HUD     |
+-------------------------------------------------------------+

```

### Technical Implementation

#### Vector State Layering in MapLibre

Instead of managing distinct DOM markers per vehicle, track the entire fleet using a unified GeoJSON source with property-driven data expressions:

```javascript
window.mapInstance.addSource('fleet-markers', {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] }
});

window.mapInstance.addLayer({
    id: 'fleet-marker-extrusion',
    type: 'fill-extrusion',
    source: 'fleet-markers',
    paint: {
        'fill-extrusion-color': ['get', 'color'],
        'fill-extrusion-height': ['get', 'height'],
        'fill-extrusion-base': ['get', 'base'],
        'fill-extrusion-opacity': 0.9
    }
});

```

#### Fleet Interaction Control Card

Provide an interactive sidebar card in NiceGUI bound to the live telemetry stream:

* **Robot Selector**: Highlights the vehicle and pans the camera view.
* **Status Flags**: Battery, flight mode (Manual, Auto, Loiter, RTH), link quality.
* **Direct Commands**: Assign current planning route, trigger `/cmd` topic execution.

## 4. Multi-Path Management, Overlay, and Zoom-to-Path

### Problem Statement

Missions often require managing separate transit paths, multiple coverage sub-grids, or individual paths assigned to different robots. Operators must view all paths simultaneously, toggle individual layer visibility, and quickly center/zoom to any specific path.

### Technical Implementation

#### Multi-Path GeoJSON Schema

All paths are cataloged into an in-memory dictionary and projected onto the map with distinct styling:

```python
state['paths'] = {
    'path_alpha': {
        'name': 'Field Survey 01',
        'color': '#2563eb',
        'visible': True,
        'waypoints': [...]
    },
    'path_beta': {
        'name': 'Perimeter Transit',
        'color': '#16a34a',
        'visible': True,
        'waypoints': [...]
    }
}

```

#### Zoom-to-Path (`fitBounds`) Integration

Calculating bounds in Python with [Shapely](https://shapely.readthedocs.io/) and triggering MapLibre's camera transition:

1. **Calculate Bounding Box in Python**:
```python
from shapely.geometry import LineString

def get_path_bounds(path_id: str):
    coords = [p['coords'][:2] for p in state['paths'][path_id]['waypoints']]
    line = LineString(coords)
    minx, miny, maxx, maxy = line.bounds
    return [[minx, miny], [maxx, maxy]]

```


2. **Invoke MapLibre Camera Animation**:
Trigger [MapLibre fitBounds](https://www.google.com/search?q=https://maplibre.org/maplibre-gl-js/docs/API/classes/Map/%23fitbounds) via NiceGUI's JavaScript bridge:
```python
bounds = get_path_bounds('path_alpha')
ui.run_javascript(f"window.mapInstance.fitBounds({json.dumps(bounds)}, {{ padding: 60, duration: 1500 }});")

```
## 5. Local Route Persistence & REST API

### Problem Statement

Routes must persist across server restarts, enable cross-session reuse, and be queryable or manageable by external automation systems via standard REST API endpoints.

```
+-------------------------------------------------------------------+
|                        REST API & Persistence                     |
|                                                                   |
|   External Services / Scripts / Third-party GCS                   |
|                             |                                     |
|                             v                                     |
|   +-------------------------------------------------------------+ |
|   |                       FastAPI Endpoints                     | |
|   |                                                             | |
|   |  GET    /api/v1/routes          -> List saved routes        | |
|   |  GET    /api/v1/routes/{id}     -> Fetch GeoJSON & metadata | |
|   |  POST   /api/v1/routes          -> Create / validate route  | |
|   |  DELETE /api/v1/routes/{id}     -> Remove persistent route  | |
|   |  POST   /api/v1/routes/{id}/run -> Dispatch to ROS 2 fleet  | |
|   +-------------------------------------------------------------+ |
|                             |                                     |
|                             v                                     |
|   +-------------------------------------------------------------+ |
|   |            Storage Engine: SQLite + JSON Blobs              | |
|   |                     routes_store.db                         | |
|   +-------------------------------------------------------------+ |
+-------------------------------------------------------------------+

```

### Technical Implementation

#### Persistence Layer (SQLite + Pydantic)

Store route schemas with strict validation using [Pydantic](https://www.google.com/search?q=https://docs.pydantic.dev/) and a local SQLite database (`sqlite3`):

```python
import sqlite3
import json
from pydantic import BaseModel, Field
from typing import List, Optional

class WaypointModel(BaseModel):
    coords: List[float] = Field(..., min_items=3, max_items=3) # [lng, lat, alt]
    action: Optional[str] = "None"

class RouteRecord(BaseModel):
    id: str
    name: str
    pattern: str
    spacing_m: float
    agl_m: float
    azimuth: float
    waypoints: List[WaypointModel]

class RouteRepository:
    def __init__(self, db_path='routes_store.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS routes (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    route_json TEXT
                )
            ''')

    def save(self, route: RouteRecord):
        with self.conn:
            self.conn.execute(
                'INSERT OR REPLACE INTO routes (id, name, route_json) VALUES (?, ?, ?)',
                (route.id, route.name, route.model_dump_json())
            )

    def list_all(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, name, created_at FROM routes ORDER BY created_at DESC')
        return [{'id': r[0], 'name': r[1], 'created_at': r[2]} for r in cursor.fetchall()]

    def get_by_id(self, route_id: str) -> Optional[RouteRecord]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT route_json FROM routes WHERE id = ?', (route_id,))
        row = cursor.fetchone()
        return RouteRecord.model_validate_json(row[0]) if row else None

```

#### REST Interface Definition (FastAPI on Port 8091)

Since NiceGUI is built directly on [FastAPI](https://fastapi.tiangolo.com/), API routes mount directly to the active web instance:

```python
from fastapi import HTTPException
from nicegui import app

repo = RouteRepository()

@app.get('/api/v1/routes')
async def list_routes():
    """Retrieve an exhaustive list of all persistent saved routes."""
    return repo.list_all()

@app.get('/api/v1/routes/{route_id}')
async def get_route(route_id: str):
    """Retrieve full 3D waypoint coordinates and mission actions."""
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route

@app.post('/api/v1/routes')
async def create_route(route: RouteRecord):
    """Persist a new route generated externally or client-side."""
    repo.save(route)
    return {"status": "success", "id": route.id}

@app.post('/api/v1/routes/{route_id}/dispatch')
async def dispatch_route(route_id: str, target_robot_id: Optional[str] = None):
    """Publish saved route directly to ROS 2 mission topic."""
    route = repo.get_by_id(route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    ros_node.publish_mission([wp.model_dump() for wp in route.waypoints])
    return {"status": "dispatched", "robot": target_robot_id or "fleet_broadcast"}

```

## 6. System Architecture Diagram

The component diagram below visualizes the decoupled threads, inter-process communication, offline caching, and data pipelines across the extended system:

```mermaid
graph TB
    subgraph ROS2_Network ["ROS 2 Middleware Environment"]
        subgraph Topics_In ["Inbound Telemetry"]
            T_Active["/active_robots<br>(std_msgs/String JSON)"]
            T_Poses["/&lt;robot_id&gt;/nav_sat_fix<br>(sensor_msgs/NavSatFix)"]
        end
        subgraph Topics_Out ["Outbound Mission Commands"]
            T_Mission["/mission_data<br>(geometry_msgs/PoseArray)"]
            T_Cmd["/&lt;robot_id&gt;/cmd<br>(std_msgs/String)"]
        end
    end

    subgraph Backend_Process ["IPP Backend Server (Python & Port 8091)"]
        subgraph Worker_Thread ["ROS 2 Node Worker Thread"]
            RCLPY["rclpy MultiThreadedExecutor"]
            Node["IPPRosNode"]
        end

        subgraph Core_Async_Loop ["NiceGUI & FastAPI Core Engine"]
            FastAPI["FastAPI REST Subsystem<br>(/api/v1/routes)"]
            UI_Engine["NiceGUI UI Component Engine"]
            CoveragePlanner["Terrain Coverage Generator<br>(Shapely & Affinity)"]
            TileServer["Local Tile Generator / Server<br>(rio-tiler & static mounts)"]
        end

        subgraph Storage_Layer ["Persistent Storage Layer"]
            DB[(SQLite Engine<br>routes_store.db)]
            GeoStore[("Local GeoTIFF Storage<br>(DSM / DTM / Orthos)")]
        end

        StateLock{{"Thread-Safe State & Queues"}}
    end

    subgraph Frontend_App ["Browser Client Application"]
        UI_View["NiceGUI Client Views<br>(Top-Left Persistent Panel & HUD)"]
        MapEngine["MapLibre GL JS 3D Engine<br>(Web Mercator & WebGL 3D Canvas)"]
    end

    %% Communications
    T_Active -->|Subscribe| Node
    T_Poses -->|Subscribe| Node
    Node -->|Publish| T_Mission
    Node -->|Publish| T_Cmd

    Node <-->|Sync Telemetry & Events| StateLock
    StateLock <-->|Poll & Dispatch| UI_Engine

    CoveragePlanner -->|Compute Path| UI_Engine
    CoveragePlanner -->|Sample Elevation| GeoStore
    GeoStore -->|Extract Pixels & Slices| TileServer

    FastAPI <-->|CRUD Routes| DB
    FastAPI -->|Direct Mission Trigger| Node
    UI_Engine <-->|Manage Routes| DB

    TileServer -->|Serve Offline XYZ Tiles| MapEngine
    UI_Engine <-->|WebSocket State Sync| UI_View
    UI_View -->|Bridge Calls| MapEngine

```

## 7. Requirements Table & Implementation Task List

| Phase | Milestone / Task | Complexity | Key Dependencies | Primary Deliverable |
| --- | --- | --- | --- | --- |
| **1. ROS 2 Bridge** | Implement daemon thread and `rclpy` lifecycle manager | Medium | `rclpy`, `threading` | Non-blocking execution of `IPPRosNode` inside NiceGUI server |
| **1. ROS 2 Bridge** | Build subscriptions for `/active_robots` and `/<id>/nav_sat_fix` | Low | `std_msgs`, `sensor_msgs` | Automated fleet discovery and live telemetry queue ingestion |
| **1. ROS 2 Bridge** | Implement `/mission_data` publisher for 3D route dispatches | Low | `geometry_msgs` | Native translation from IPP route arrays to ROS 2 `PoseArray` |
| **2. Offline Tiling** | Build on-demand COG tile streamer or GDAL pre-tiler | High | `rio-tiler` or `gdal2tiles` | Offline serving of local raster imagery at `/api/tiles/{id}/{z}/{x}/{y}.png` |
| **2. Offline Tiling** | Generate RGB Terrarium DEM tiles from local DSM/DTMs | High | `rasterio`, `numpy` | Offline 3D hillshade and extruded terrain rendering in MapLibre |
| **3. Fleet Tracking** | MapLibre GeoJSON dynamic multi-robot visualization layer | Medium | MapLibre GL JS | Real-time extruded markers, headings, and color-coded vehicle trails |
| **3. Fleet Tracking** | Develop Interactive Fleet Command Drawer in NiceGUI | Medium | NiceGUI | Vehicle detail cards, status badges, and interactive "Send Mission" action |
| **4. Multi-Path** | Refactor state dictionary to support multiple paths | Medium | `shapely` | Simultaneous rendering of distinct transit lines and coverage loops |
| **4. Multi-Path** | Implement `fitBounds` path focus utility | Low | MapLibre GL JS | One-click camera zoom to selected route bounding boxes |
| **5. Persistence** | Build SQLite database repository with Pydantic validation | Low | `sqlite3`, `pydantic` | Fully ACID-compliant persistent local route catalog |
| **5. Persistence** | Implement FastAPI endpoints (`/api/v1/routes/*`) | Medium | `fastapi` | RESTful API documentation, listing, query, and execution routes |

Here is the complete, ready-to-run package containing the final frontend and backend files, along with the installation instructions your developer needs to deploy this on Windows or Linux.

### 1. Environment & Installation Setup

To run this application and prepare for the upcoming ROS 2 integration, the developer will need **Python 3.10+**.

Create a `requirements.txt` file with the following libraries:

```text
nicegui>=1.4.0
fastapi
uvicorn
shapely
rasterio
pyproj
simplekml
rio-tiler
pydantic

```

# Installation Notes

## Environment & Installation Setup (Using `uv`)

### 1. Create a ROS-Compatible Virtual Environment:
ROS 2 requires access to system-level libraries. Initialize a virtual environment requesting Python 3.12 or higher with system site-packages enabled:
```bash
uv venv --python ">=3.12" --system-site-packages
```
### Activate the Environment:
* **Windows:** `.venv\Scripts\activate`
* **Linux:** `source .venv/bin/activate`


### Install Dependencies:
Use `uv add` to automatically resolve, fetch, and add the required packages to your project (this manages your `pyproject.toml` and lockfile directly):
```bash
uv add nicegui fastapi uvicorn shapely rasterio pyproj simplekml rio-tiler pydantic
```
### Source ROS 2:
The host machine must have a native ROS 2 distribution installed. Source this environment so the Python script can locate the middleware:
* **Windows:** `call C:\dev\ros2\local_setup.bat` (or your specific ROS path)
* **Linux:** `source /opt/ros/humble/setup.bash`

### Folder Structure Setup
Ensure your directory contains the scripts and the exact logo file:

```text
/ipp_planner/
├── main.py
├── map.js
└── ISF_Instituts_Visual_EN_Zeichenfläche 1.png

```


6. **Launch the Platform:**
```bash
uv run main.py

```