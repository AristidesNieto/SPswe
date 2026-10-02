from nicegui import ui
import math

# Load MapLibre GL JS library natively into the NiceGUI head
ui.add_head_html('''
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
''')

# Tänikon, Aadorf, Switzerland coordinates
CENTER_LNG, CENTER_LAT = 8.9056, 47.4795
ALTITUDE_M = 30
RADIUS = 0.003  # Roughly 300 meter radius for the UAV circle

# UI: Create a full-screen container for the map
ui.html('<div id="map" style="width: 100vw; height: 100vh;"></div>').classes('absolute top-0 left-0 -z-10')

# UI: Create a floating Heads-Up Display (HUD) for telemetry
with ui.card().classes('absolute top-4 left-4 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200'):
    ui.label('UAV Telemetry (Tänikon)').classes('text-lg font-bold text-gray-800')
    lng_label = ui.label(f'Lon: {CENTER_LNG:.5f}').classes('font-mono')
    lat_label = ui.label(f'Lat: {CENTER_LAT:.5f}').classes('font-mono')
    alt_label = ui.label(f'Alt: {ALTITUDE_M} m (MSL)').classes('font-mono text-blue-600 font-bold')

# JavaScript: Initialize MapLibre and the UAV marker
map_init_js = f'''
    // Initialize the FOSS map
    window.map = new maplibregl.Map({{
        container: 'map',
        style: {{
            'version': 8,
            'sources': {{
                'osm': {{
                    'type': 'raster',
                    'tiles': ['https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png'],
                    'tileSize': 256,
                    'attribution': '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                }}
            }},
            'layers': [{{
                'id': 'osm',
                'type': 'raster',
                'source': 'osm'
            }}]
        }},
        center: [{CENTER_LNG}, {CENTER_LAT}],
        zoom: 14.5,
        pitch: 55, // Pitched to give a 3D perspective
        bearing: 0
    }});

    // Add the UAV marker once the map loads
    window.map.on('load', () => {{
        window.map.addSource('uav', {{
            'type': 'geojson',
            'data': {{
                'type': 'Point',
                'coordinates': [{CENTER_LNG}, {CENTER_LAT}]
            }}
        }});

        window.map.addLayer({{
            'id': 'uav-marker',
            'type': 'circle',
            'source': 'uav',
            'paint': {{
                'circle-radius': 8,
                'circle-color': '#ef4444',
                'circle-stroke-width': 3,
                'circle-stroke-color': '#ffffff'
            }}
        }});
    }});

    // Global function for NiceGUI to call
    window.updateUAV = function(lng, lat) {{
        if (window.map && window.map.getSource('uav')) {{
            window.map.getSource('uav').setData({{
                'type': 'Point',
                'coordinates': [lng, lat]
            }});
        }}
    }};
'''

# Inject the initialization script directly into the HTML body so it runs on page load
ui.add_body_html(f'<script>{map_init_js}</script>')

# Python: UAV Simulation State
state = {'angle': 0.0}

def update_uav_position():
    """Calculates new coordinates and pushes them to the browser."""
    state['angle'] += 0.05
    
    # Calculate new coordinates in a circle
    current_lng = CENTER_LNG + RADIUS * math.cos(state['angle'])
    current_lat = CENTER_LAT + RADIUS * math.sin(state['angle'])
    
    # 1. Update the Python/HTML HUD
    lng_label.set_text(f'Lon: {current_lng:.5f}')
    lat_label.set_text(f'Lat: {current_lat:.5f}')
    
    # 2. Push the new coordinates to MapLibre via JS execution
    try:
        ui.run_javascript(f'window.updateUAV({current_lng}, {current_lat});')
    except Exception:
        # Silently ignore the websocket error if the browser hasn't connected yet
        pass

# Run the simulation at 10Hz (0.1 seconds)
ui.timer(0.1, update_uav_position)

# Bind to 0.0.0.0 to ensure web traffic routes correctly out of your container to the Windows host
ui.run(host='0.0.0.0', port=8080, title="UAV Tracker")