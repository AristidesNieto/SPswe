from nicegui import ui, app
from shapely.geometry import Polygon, LineString
import math
import json
import os
import time

# --- Geospatial imports ---
try:
    import rasterio
    from pyproj import Transformer
    HAS_GEO = True
except ImportError:
    HAS_GEO = False

current_dir = os.path.dirname(os.path.abspath(__file__))
app.add_static_files('/static', current_dir)

CENTER_LNG, CENTER_LAT = 8.9056, 47.4795
SPEED = 0.00008  

state = {
    'lng': CENTER_LNG, 
    'lat': CENTER_LAT, 
    'alt_msl': 530.0,
    'route': [], 
    'boundary': [], 
    'target_idx': 0,
    'direction': 1,
    'running': False,
    'click_mode': 'Boundary', 
    'pattern': 'Lawnmower',
    'spacing_m': 30,
    'agl_m': 30,       # NEW: Distance-to-ground parameter
    'dsm_path': None   # NEW: Path to the uploaded GeoTIFF
}

ui.add_head_html(f'''
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
        .maplibregl-canvas {{ cursor: crosshair !important; }}
    </style>
    <script>window.MAP_CONFIG = {{ lng: {CENTER_LNG}, lat: {CENTER_LAT} }};</script>
    <script src="/static/map.js?t={time.time()}" defer></script>
''', shared=True)

@ui.page('/')
async def main_page():
    ui.query('.nicegui-content').classes('p-0')
    ui.element('div').props('id=map').classes('w-screen h-screen absolute top-0 left-0 z-0')
    
    with ui.card().classes('absolute top-4 left-4 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200 w-96'):
        ui.label('UAV RTK Mission Planner').classes('text-lg font-bold text-gray-800')
        
        # --- File Upload for DSM ---
        def handle_upload(e):
            if not HAS_GEO:
                ui.notify('Please run: pip install rasterio pyproj', type='negative')
                return
            path = os.path.join(current_dir, e.name)
            with open(path, 'wb') as f:
                f.write(e.content.read())
            state['dsm_path'] = path
            ui.notify(f'Loaded DSM: {e.name}', type='positive')

        ui.upload(on_upload=handle_upload, label='Upload GeoTIFF DSM').classes('w-full mt-2')
        
        ui.label('Click Action:').classes('text-xs text-gray-500 mt-2')
        ui.radio(['Boundary', 'Waypoints'], value='Boundary') \
            .bind_value_to(state, 'click_mode').classes('flex flex-row gap-4')
        
        # --- 3D Telemetry ---
        with ui.row().classes('w-full justify-between mt-2'):
            lng_label = ui.label(f"Lon: {state['lng']:.5f}").classes('font-mono text-sm')
            lat_label = ui.label(f"Lat: {state['lat']:.5f}").classes('font-mono text-sm')
        
        with ui.row().classes('w-full justify-between'):
            alt_msl_label = ui.label(f"MSL: {state['alt_msl']:.1f}m").classes('font-mono text-sm text-blue-700 font-bold')
            agl_label = ui.label(f"Target AGL: {state['agl_m']}m").classes('font-mono text-sm text-green-700')
            
        wp_label = ui.label('Waypoints: 0').classes('font-mono text-gray-600 font-bold mb-2 mt-2')
        
        # --- Flight Parameters ---
        ui.label('Auto-Coverage Parameters:').classes('text-xs text-gray-500 mt-2')
        with ui.row().classes('w-full gap-2 items-center'):
            ui.number('Track (m)', value=30, min=2, max=500).bind_value_to(state, 'spacing_m').classes('w-20')
            ui.number('AGL (m)', value=30, min=5, max=500).bind_value_to(state, 'agl_m').classes('w-20')
            ui.select(['Lawnmower', 'Grid'], value='Lawnmower').bind_value_to(state, 'pattern').classes('flex-1')
                
        ui.button('Generate 3D Path', on_click=lambda: generate_coverage_path()) \
            .classes('bg-blue-600 text-white w-full mt-2')

        with ui.row().classes('w-full justify-between mt-4 gap-2'):
            ui.button('Start', on_click=lambda: state.update(running=True)).classes('bg-green-600 text-white p-2 flex-1')
            ui.button('Stop', on_click=lambda: state.update(running=False)).classes('bg-red-600 text-white p-2 flex-1')
            ui.button('Clear', on_click=lambda: clear_all()).classes('bg-gray-200 text-gray-800 p-2 flex-1')

    await ui.context.client.connected()
    ui.run_javascript('if (typeof window.initMap === "function") window.initMap();')

    def clear_all():
        state['route'].clear()
        state['boundary'].clear()
        state['target_idx'] = 0
        state['running'] = False
        update_path_display()
        update_boundary_display()

    def get_elevation(lng, lat):
        """Samples the uploaded GeoTIFF. Falls back to a simulated hill if no file is uploaded."""
        if state['dsm_path'] and HAS_GEO:
            try:
                with rasterio.open(state['dsm_path']) as src:
                    transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                    x, y = transformer.transform(lng, lat)
                    for val in src.sample([(x, y)]):
                        return float(val[0])
            except Exception as e:
                print(f"DSM Error: {e}")
        
        # Simulated terrain fallback for testing (100m hill centered at Tänikon)
        dist = math.sqrt((lng - CENTER_LNG)**2 + (lat - CENTER_LAT)**2)
        base_alt = 530.0
        hill = 100.0 * math.exp(-(dist**2) / 0.00005)
        return base_alt + hill

    def generate_coverage_path():
        if len(state['boundary']) < 3:
            ui.notify('Please draw a boundary with at least 3 points first.', type='warning')
            return
            
        poly = Polygon(state['boundary'])
        minx, miny, maxx, maxy = poly.bounds
        
        spacing_deg_y = state['spacing_m'] / 111111.0
        spacing_deg_x = state['spacing_m'] / (111111.0 * math.cos(math.radians(CENTER_LAT)))
        
        raw_waypoints_2d = []

        def append_sweeps(is_vertical=False):
            sweeps = []
            if not is_vertical:
                y = miny
                while y <= maxy:
                    sweeps.append(LineString([(minx - 0.01, y), (maxx + 0.01, y)]))
                    y += spacing_deg_y
            else:
                x = minx
                while x <= maxx:
                    sweeps.append(LineString([(x, miny - 0.01), (x, maxy + 0.01)]))
                    x += spacing_deg_x
            
            left_to_right = True
            for line in sweeps:
                intersection = poly.intersection(line)
                if intersection.is_empty: continue
                
                coords = []
                if intersection.geom_type == 'LineString':
                    coords = list(intersection.coords)
                elif intersection.geom_type == 'MultiLineString':
                    ixmin, iymin, ixmax, iymax = intersection.bounds
                    coords = [(ixmin, iymin), (ixmax, iymax)] if not is_vertical else [(ixmin, iymin), (ixmin, iymax)]
                
                if not left_to_right: coords.reverse()
                raw_waypoints_2d.extend(coords)
                left_to_right = not left_to_right

        append_sweeps(is_vertical=False)
        if state['pattern'] == 'Grid':
            append_sweeps(is_vertical=True)
            
        # --- 3D Densification to follow Ground Curvature ---
        new_route_3d = []
        sample_interval_m = 5.0  # Sample terrain every 5 meters
        sample_deg = sample_interval_m / 111111.0

        for i in range(len(raw_waypoints_2d) - 1):
            p1 = raw_waypoints_2d[i]
            p2 = raw_waypoints_2d[i+1]
            
            dist = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            steps = max(1, int(dist / sample_deg))
            
            for step in range(steps):
                f = step / float(steps)
                lx = p1[0] + f * (p2[0] - p1[0])
                ly = p1[1] + f * (p2[1] - p1[1])
                # Compute absolute MSL based on ground elevation + AGL
                lz = get_elevation(lx, ly) + state['agl_m']
                new_route_3d.append([lx, ly, lz])
                
        # Append final point
        final_pt = raw_waypoints_2d[-1]
        new_route_3d.append([final_pt[0], final_pt[1], get_elevation(final_pt[0], final_pt[1]) + state['agl_m']])
            
        state['route'] = new_route_3d
        state['target_idx'] = 0
        update_path_display()

    def update_boundary_display():
        features = []
        if state['boundary']:
            if len(state['boundary']) >= 3:
                coords = state['boundary'] + [state['boundary'][0]]
                features.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [coords]}})
            elif len(state['boundary']) == 2:
                features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': state['boundary']}})
            
            for i, pt in enumerate(state['boundary']):
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': pt},
                    'properties': {'label': str(i + 1)}
                })
        ui.run_javascript(f"window.updateBoundary({json.dumps({'type': 'FeatureCollection', 'features': features})});")

    def update_path_display():
        wp_label.set_text(f"Waypoints: {len(state['route'])}")
        features = []
        if state['route']:
            # Strip the Z coordinate for MapLibre 2D line drawing
            coords_2d = [[state['lng'], state['lat']]]
            if state['direction'] == 1:
                coords_2d.extend([[p[0], p[1]] for p in state['route'][state['target_idx']:]])
            else:
                coords_2d.extend([[p[0], p[1]] for p in state['route'][:state['target_idx']+1][::-1]])
            features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords_2d}})
            
            # We skip drawing numbers for dense 3D points as there will be thousands
                
        ui.run_javascript(f"window.updatePath({json.dumps({'type': 'FeatureCollection', 'features': features})});")

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
                        # Manual waypoints sample terrain instantly
                        pt_3d = [pt[0], pt[1], get_elevation(pt[0], pt[1]) + state['agl_m']]
                        state['route'].append(pt_3d)
                        update_path_display()
        except Exception:
            pass 

    def flight_controller():
        if not state['running'] or not state['route']:
            return
            
        if state['target_idx'] >= len(state['route']):
            state['target_idx'] = len(state['route']) - 1
            
        target = state['route'][state['target_idx']]
        target_lng, target_lat, target_alt = target[0], target[1], target[2]
        
        # Calculate 3D distance
        dx = target_lng - state['lng']
        dy = target_lat - state['lat']
        # Convert altitude difference (meters) to approximate degree equivalent for normalized speed calculation
        dz_deg = (target_alt - state['alt_msl']) / 111111.0 
        
        distance = math.sqrt(dx**2 + dy**2 + dz_deg**2)
        
        if distance < SPEED:
            state['lng'], state['lat'], state['alt_msl'] = target_lng, target_lat, target_alt
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
            state['alt_msl'] += (dz_deg / distance) * SPEED * 111111.0
            update_path_display()
            
        lng_label.set_text(f"Lon: {state['lng']:.5f}")
        lat_label.set_text(f"Lat: {state['lat']:.5f}")
        alt_msl_label.set_text(f"MSL: {state['alt_msl']:.1f}m")
        ui.run_javascript(f"window.updateUAV({state['lng']}, {state['lat']});")

    ui.timer(0.1, poll_waypoints)
    ui.timer(0.1, flight_controller)

ui.run(host='0.0.0.0', port=8080, title="UAV Mission Planner")