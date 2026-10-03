# About
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

# Additional Funcitonality

# ROS2 Integration

# Accurate GNSS EPSG (current epoch)