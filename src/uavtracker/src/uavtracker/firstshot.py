from nicegui import ui
import math

# 1. Load MapLibre dependencies into the document head, explicitly marking them as shared
ui.add_head_html('''
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
    <style>body { margin: 0; padding: 0; overflow: hidden; }</style>
''', shared=True)

# Constants
CENTER_LNG, CENTER_LAT = 8.9056, 47.4795
ALTITUDE_M = 30
RADIUS = 0.003
state = {'angle': 0.0}

# 2. Use a page route to properly manage the client lifecycle
@ui.page('/')
async def main_page():
    # Remove default padding
    ui.query('.nicegui-content').classes('p-0')
    
    # Create the map container using native NiceGUI elements
    ui.element('div').props('id=map').classes('w-screen h-screen absolute top-0 left-0 z-0')
    
    # Create the HUD
    with ui.card().classes('absolute top-4 left-4 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200'):
        ui.label('UAV Telemetry (Tänikon)').classes('text-lg font-bold text-gray-800')
        lng_label = ui.label(f'Lon: {CENTER_LNG:.5f}').classes('font-mono')
        lat_label = ui.label(f'Lat: {CENTER_LAT:.5f}').classes('font-mono')
        alt_label = ui.label(f'Alt: {ALTITUDE_M} m (MSL)').classes('font-mono text-blue-600 font-bold')

    # 3. CRITICAL: Wait for the browser to finish rendering the HTML
    await ui.context.client.connected()

    # 4. Now initialize MapLibre safely
    ui.run_javascript(f'''
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
            pitch: 55
        }});

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

        window.updateUAV = function(lng, lat) {{
            if (window.map && window.map.getSource('uav')) {{
                window.map.getSource('uav').setData({{
                    'type': 'Point',
                    'coordinates': [lng, lat]
                }});
            }}
        }};
    ''')

    # 5. Define the update loop tied to this specific client session
    def update_uav_position():
        state['angle'] += 0.05
        current_lng = CENTER_LNG + RADIUS * math.cos(state['angle'])
        current_lat = CENTER_LAT + RADIUS * math.sin(state['angle'])
        
        # Update UI labels
        lng_label.set_text(f'Lon: {current_lng:.5f}')
        lat_label.set_text(f'Lat: {current_lat:.5f}')
        
        # Push coordinates to the map
        ui.run_javascript(f'window.updateUAV({current_lng}, {current_lat});')

    # Run the timer at 10Hz
    ui.timer(0.1, update_uav_position)

# Bind to 0.0.0.0 for container access
ui.run(host='0.0.0.0', port=8080, title="UAV Tracker")