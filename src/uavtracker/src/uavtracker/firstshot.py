from nicegui import ui, app
from shapely.geometry import Polygon, LineString
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
    'route': [], 
    'boundary': [], 
    'target_idx': 0,
    'direction': 1,
    'running': False,
    'click_mode': 'Boundary', 
    'pattern': 'Lawnmower'
}

# Added CSS override to force crosshair cursor even over interactive map elements
ui.add_head_html(f'''
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
        .maplibregl-canvas {{ cursor: crosshair !important; }}
    </style>
    <script>
        window.MAP_CONFIG = {{ lng: {CENTER_LNG}, lat: {CENTER_LAT} }};
    </script>
    <script src="/static/map.js?t={time.time()}" defer></script>
''', shared=True)

@ui.page('/')
async def main_page():
    ui.query('.nicegui-content').classes('p-0')
    ui.element('div').props('id=map').classes('w-screen h-screen absolute top-0 left-0 z-0')
    
    with ui.card().classes('absolute top-4 left-4 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200 w-80'):
        ui.label('UAV Mission Planner').classes('text-lg font-bold text-gray-800')
        
        ui.label('Click Action:').classes('text-xs text-gray-500 mt-2')
        ui.radio(['Boundary', 'Waypoints'], value='Boundary') \
            .bind_value_to(state, 'click_mode').classes('flex flex-row gap-4')
        
        lng_label = ui.label(f"Lon: {state['lng']:.5f}").classes('font-mono mt-2')
        lat_label = ui.label(f"Lat: {state['lat']:.5f}").classes('font-mono')
        wp_label = ui.label('Waypoints: 0').classes('font-mono text-blue-600 font-bold mb-2')
        
        ui.label('Auto-Coverage Path:').classes('text-xs text-gray-500 mt-2')
        with ui.row().classes('w-full gap-2'):
            ui.select(['Lawnmower', 'Grid'], value='Lawnmower') \
                .bind_value_to(state, 'pattern').classes('flex-1')
            ui.button('Generate', on_click=lambda: generate_coverage_path()) \
                .classes('bg-blue-600 text-white')

        with ui.row().classes('w-full justify-between mt-4'):
            ui.button('Start', on_click=lambda: state.update(running=True)).classes('bg-green-600 text-white p-2 flex-1')
            ui.button('Stop', on_click=lambda: state.update(running=False)).classes('bg-red-600 text-white p-2 flex-1')
            
        def clear_all():
            state['route'].clear()
            state['boundary'].clear()
            state['target_idx'] = 0
            state['running'] = False
            update_path_display()
            update_boundary_display()
            
        ui.button('Clear All', on_click=clear_all).classes('bg-gray-200 text-gray-800 mt-2 w-full')

    await ui.context.client.connected()
    ui.run_javascript('if (typeof window.initMap === "function") window.initMap();')

    def generate_coverage_path():
        if len(state['boundary']) < 3:
            ui.notify('Please draw a boundary with at least 3 points first.', type='warning')
            return
            
        poly = Polygon(state['boundary'])
        minx, miny, maxx, maxy = poly.bounds
        spacing = 0.0003  
        new_route = []

        def get_sweeps(is_vertical=False):
            sweeps = []
            if not is_vertical:
                y = miny
                while y <= maxy:
                    sweeps.append(LineString([(minx - 0.01, y), (maxx + 0.01, y)]))
                    y += spacing
            else:
                x = minx
                while x <= maxx:
                    sweeps.append(LineString([(x, miny - 0.01), (x, maxy + 0.01)]))
                    x += spacing
            
            waypoints = []
            left_to_right = True
            for line in sweeps:
                intersection = poly.intersection(line)
                if intersection.is_empty: continue
                
                if intersection.geom_type == 'LineString':
                    coords = list(intersection.coords)
                    if not left_to_right: coords.reverse()
                    waypoints.extend(coords)
                    left_to_right = not left_to_right
                elif intersection.geom_type == 'MultiLineString':
                    ixmin, iymin, ixmax, iymax = intersection.bounds
                    coords = [(ixmin, iymin), (ixmax, iymax)] if not is_vertical else [(ixmin, iymin), (ixmin, iymax)]
                    if not left_to_right: coords.reverse()
                    waypoints.extend(coords)
                    left_to_right = not left_to_right
            return waypoints

        new_route.extend(get_sweeps(is_vertical=False))
        if state['pattern'] == 'Grid':
            new_route.extend(get_sweeps(is_vertical=True))
            
        state['route'] = new_route
        state['target_idx'] = 0
        update_path_display()

    def update_boundary_display():
        features = []
        if state['boundary']:
            # 1. Draw the connecting lines or filled polygon
            if len(state['boundary']) >= 3:
                coords = state['boundary'] + [state['boundary'][0]]
                features.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [coords]}})
            elif len(state['boundary']) == 2:
                features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': state['boundary']}})
            
            # 2. Draw the numbered points
            for i, pt in enumerate(state['boundary']):
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': pt},
                    'properties': {'label': str(i + 1)}
                })
                
        geojson = {'type': 'FeatureCollection', 'features': features}
        ui.run_javascript(f'window.updateBoundary({json.dumps(geojson)});')

    def update_path_display():
        wp_label.set_text(f"Waypoints: {len(state['route'])}")
        
        features = []
        if state['route']:
            # 1. Draw the flight path line
            coords = [[state['lng'], state['lat']]]
            if state['direction'] == 1:
                coords.extend(state['route'][state['target_idx']:])
            else:
                coords.extend(state['route'][:state['target_idx']+1][::-1])
            features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords}})
            
            # 2. Draw the numbered points
            for i, pt in enumerate(state['route']):
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': pt},
                    'properties': {'label': str(i + 1)}
                })
                
        geojson = {'type': 'FeatureCollection', 'features': features}
        ui.run_javascript(f'window.updatePath({json.dumps(geojson)});')

    async def poll_waypoints():
        js_code = 'if (window.waypointQueue && window.waypointQueue.length > 0) { let q = window.waypointQueue; window.waypointQueue = []; return q; } return [];'
        try:
            new_clicks = await ui.run_javascript(js_code)
            if new_clicks:
                for pt in new_clicks:
                    if state['click_mode'] == 'Boundary':
                        state['boundary'].append(pt)
                        update_boundary_display()
                    else:
                        state['route'].append(pt)
                        update_path_display()
        except Exception:
            pass 

    def flight_controller():
        if not state['running'] or not state['route']:
            return
            
        if state['target_idx'] >= len(state['route']):
            state['target_idx'] = len(state['route']) - 1
            
        target_lng, target_lat = state['route'][state['target_idx']]
        dx = target_lng - state['lng']
        dy = target_lat - state['lat']
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < SPEED:
            state['lng'], state['lat'] = target_lng, target_lat
            if len(state['route']) > 1:
                state['target_idx'] += state['direction']
                if state['target_idx'] >= len(state['route']):
                    state['direction'] = -1
                    state['target_idx'] = len(state['route']) - 2 
                elif state['target_idx'] < 0:
                    state['direction'] = 1
                    state['target_idx'] = 1
            update_path_display()
        else:
            state['lng'] += (dx / distance) * SPEED
            state['lat'] += (dy / distance) * SPEED
            update_path_display()
            
        lng_label.set_text(f"Lon: {state['lng']:.5f}")
        lat_label.set_text(f"Lat: {state['lat']:.5f}")
        ui.run_javascript(f"window.updateUAV({state['lng']}, {state['lat']});")

    # SPEEDED UP POLLING: Now checks for clicks 10 times a second instead of 5
    ui.timer(0.1, poll_waypoints)
    ui.timer(0.1, flight_controller)

ui.run(host='0.0.0.0', port=8080, title="UAV Mission Planner")