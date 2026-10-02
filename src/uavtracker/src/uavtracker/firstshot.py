from nicegui import ui, app
import math
import json
import os
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
app.add_static_files('/static', current_dir)

CENTER_LNG, CENTER_LAT = 8.9056, 47.4795
SPEED = 0.00008  
state = {
    'lng': CENTER_LNG, 
    'lat': CENTER_LAT, 
    'waypoints': [], 
    'running': False
}

# Added cache-busting timestamp to the script source
ui.add_head_html(f'''
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
    <style>body {{ margin: 0; padding: 0; overflow: hidden; }}</style>
    
    <script>
        window.MAP_CONFIG = {{
            lng: {CENTER_LNG},
            lat: {CENTER_LAT}
        }};
    </script>
    <script src="/static/map.js?t={time.time()}" defer></script>
''', shared=True)

@ui.page('/')
async def main_page():
    ui.query('.nicegui-content').classes('p-0')
    
    # Render the map container
    ui.element('div').props('id=map').classes('w-screen h-screen absolute top-0 left-0 z-0')
    
    with ui.card().classes('absolute top-4 left-4 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200 w-72'):
        ui.label('UAV Flight Planner').classes('text-lg font-bold text-gray-800')
        ui.label('Click the map to add waypoints').classes('text-xs text-gray-500 mb-2')
        
        lng_label = ui.label(f"Lon: {state['lng']:.5f}").classes('font-mono')
        lat_label = ui.label(f"Lat: {state['lat']:.5f}").classes('font-mono')
        wp_label = ui.label('Waypoints: 0').classes('font-mono text-blue-600 font-bold mb-2')
        
        with ui.row().classes('w-full justify-between mt-2'):
            ui.button('Start', on_click=lambda: state.update(running=True)).classes('bg-green-600 text-white p-2 flex-1')
            ui.button('Stop', on_click=lambda: state.update(running=False)).classes('bg-red-600 text-white p-2 flex-1')
            
        def clear_path():
            state['waypoints'].clear()
            state['running'] = False
            update_path_display()
            
        ui.button('Clear Path', on_click=clear_path).classes('bg-gray-200 text-gray-800 mt-2 w-full')

    await ui.context.client.connected()
    
    # Trigger JS initialization with a fallback catch
    ui.run_javascript('''
        if (typeof window.initMap === "function") {
            window.initMap();
        } else {
            console.error("[Python] Could not find window.initMap. Did map.js load?");
        }
    ''')

    def update_path_display():
        wp_label.set_text(f"Waypoints: {len(state['waypoints'])}")
        if not state['waypoints']:
            geojson = {'type': 'FeatureCollection', 'features': []}
        else:
            coords = [[state['lng'], state['lat']]] + state['waypoints']
            geojson = {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords}}
        ui.run_javascript(f'window.updatePath({json.dumps(geojson)});')

    async def poll_waypoints():
        js_code = '''
            if (window.waypointQueue && window.waypointQueue.length > 0) {
                let q = window.waypointQueue;
                window.waypointQueue = []; 
                return q;
            }
            return [];
        '''
        try:
            new_wps = await ui.run_javascript(js_code)
            if new_wps:
                for wp in new_wps:
                    state['waypoints'].append(wp)
                update_path_display()
        except Exception:
            pass 

    def flight_controller():
        if not state['running'] or not state['waypoints']:
            return
            
        target_lng, target_lat = state['waypoints'][0]
        dx = target_lng - state['lng']
        dy = target_lat - state['lat']
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < SPEED:
            state['lng'], state['lat'] = target_lng, target_lat
            state['waypoints'].pop(0)
            update_path_display()
            if not state['waypoints']:
                state['running'] = False
        else:
            state['lng'] += (dx / distance) * SPEED
            state['lat'] += (dy / distance) * SPEED
            update_path_display()
            
        lng_label.set_text(f"Lon: {state['lng']:.5f}")
        lat_label.set_text(f"Lat: {state['lat']:.5f}")
        ui.run_javascript(f"window.updateUAV({state['lng']}, {state['lat']});")

    ui.timer(0.2, poll_waypoints)
    ui.timer(0.1, flight_controller)

ui.run(host='0.0.0.0', port=8080, title="UAV Flight Planner")