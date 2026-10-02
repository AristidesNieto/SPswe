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
    import simplekml
    HAS_GEO = True
except ImportError:
    HAS_GEO = False
    print("WARNING: Please run `pip install rasterio pyproj simplekml` for full functionality.")

current_dir = os.path.dirname(os.path.abspath(__file__))
app.add_static_files('/static', current_dir)

CENTER_LNG, CENTER_LAT = 8.9056, 47.4795
SPEED = 0.00001  

state = {
    'lng': CENTER_LNG, 
    'lat': CENTER_LAT, 
    'alt_msl': 530.0,
    'route': [], 
    'boundary': [], 
    'target_idx': 0,
    'direction': 1,
    'running': False,
    'speed_mult': 1.0, 
    'click_mode': 'Boundary', 
    'pattern': 'Lawnmower',
    'spacing_m': 30,
    'agl_m': 30,       
    'current_action': 'None',
    'dsms': [],
    'dtms': [],
    'orthos': []
}

ui.add_head_html(f'''
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
        .maplibregl-canvas {{ cursor: crosshair !important; }}
    </style>
    <script>window.MAP_CONFIG = {{ lng: {CENTER_LNG}, lat: {CENTER_LAT}, alt: {state['alt_msl']} }};</script>
    <script src="/static/map.js?t={time.time()}" defer></script>
''', shared=True)

@ui.page('/')
async def main_page():
    ui.query('.nicegui-content').classes('p-0')
    ui.element('div').props('id=map').classes('w-screen h-screen absolute top-0 left-0 z-0')
    
    # ==========================================
    # DIALOGS
    # ==========================================
    with ui.dialog() as dlg_help, ui.card().classes('w-96 max-h-[80vh] overflow-y-auto'):
        ui.label('Mission Planner Guide').classes('text-xl font-bold text-blue-800')
        ui.markdown("""**Navigation**\n* **Pan:** Click and drag the map.\n* **Zoom:** Scroll wheel.\n* **3D View (Pitch & Rotate):** Hold Right-Click and drag.""")
        ui.button('Close', on_click=dlg_help.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_flight, ui.card().classes('w-80'):
        ui.label('Flight Parameters').classes('text-lg font-bold')
        ui.number('Distance between lines (m)', value=30, min=2, max=500).bind_value_to(state, 'spacing_m').classes('w-full')
        ui.number('Target AGL Height (m)', value=30, min=5, max=500).bind_value_to(state, 'agl_m').classes('w-full')
        ui.button('Close', on_click=dlg_flight.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_area, ui.card().classes('w-80'):
        ui.label('Area & Path').classes('text-lg font-bold')
        ui.radio(['Boundary', 'Waypoints'], value='Boundary').bind_value_to(state, 'click_mode').classes('flex flex-row gap-4')
        ui.select(['None', 'Take Photo', 'Start Video', 'Stop Video', 'Hover 5s'], value='None', label='Action for next point').bind_value_to(state, 'current_action').classes('w-full mt-2')
        ui.select(['Lawnmower', 'Grid'], value='Lawnmower', label='Coverage Pattern').bind_value_to(state, 'pattern').classes('w-full mt-2')
        ui.button('Compute Path', on_click=lambda: generate_coverage_path()).classes('bg-blue-600 text-white w-full mt-4')
        ui.button('Clear Map', on_click=lambda: clear_all()).classes('bg-red-600 text-white w-full mt-2')
        ui.button('Close', on_click=dlg_area.close).classes('w-full mt-2 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_upload, ui.card().classes('w-80'):
        ui.label('Upload Geospatial Data').classes('text-lg font-bold')
        upload_type = ui.select(['DSM', 'DTM', 'Orthomosaic'], value='DSM', label='Select Data Category').classes('w-full mt-2')
        
        async def handle_upload(e):
            if not HAS_GEO: return
            file_name = getattr(e, 'name', getattr(e, 'filename', 'uploaded_file.tif'))
            path = os.path.join(current_dir, file_name)
            file_source = getattr(e, 'content', getattr(e, 'file', None))
            if file_source is None: return
            raw_data = file_source.read()
            if hasattr(raw_data, '__await__'): data = await raw_data
            else: data = raw_data
            
            with open(path, 'wb') as f: f.write(data)
            cat = upload_type.value
            if cat == 'DSM': state['dsms'].append(path)
            elif cat == 'DTM': state['dtms'].append(path)
            elif cat == 'Orthomosaic': state['orthos'].append(path)
            ui.notify(f'Loaded {cat}: {file_name}', type='positive')

        ui.upload(multiple=True, on_upload=handle_upload).classes('w-full mt-2')
        ui.button('Close', on_click=dlg_upload.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_export, ui.card().classes('w-80'):
        ui.label('Export Mission').classes('text-lg font-bold')
        ui.button('Download GeoJSON', on_click=lambda: export_geojson()).classes('w-full mt-2 bg-gray-800 text-white')
        ui.button('Download KML', on_click=lambda: export_kml(kmz=False)).classes('w-full mt-2 bg-gray-800 text-white')
        ui.button('Download KMZ', on_click=lambda: export_kml(kmz=True)).classes('w-full mt-2 bg-gray-800 text-white')
        ui.button('Close', on_click=dlg_export.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    # ==========================================
    # FLOATING TOP TOOLBAR
    # ==========================================
    with ui.row().classes('absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200 rounded-full px-2 py-1 gap-2 items-center'):
        with ui.button(icon='flight_takeoff', on_click=dlg_flight.open).props('flat round'): ui.tooltip('Flight Parameters')
        with ui.button(icon='polyline', on_click=dlg_area.open).props('flat round'): ui.tooltip('Area Definition & Path')
        with ui.button(icon='upload_file', on_click=dlg_upload.open).props('flat round'): ui.tooltip('Upload DSM/DTM/Ortho')
        with ui.button(icon='download', on_click=dlg_export.open).props('flat round'): ui.tooltip('Export Mission Data')
        with ui.button(icon='help_outline', on_click=dlg_help.open).props('flat round text-blue'): ui.tooltip('Help & Instructions')
        ui.separator().props('vertical').classes('mx-2')
        with ui.button(icon='play_arrow', on_click=lambda: state.update(running=True)).props('flat round text-green'): ui.tooltip('Start UAV Simulation')
        with ui.button(icon='stop', on_click=lambda: state.update(running=False)).props('flat round text-red'): ui.tooltip('Stop UAV Simulation')

    # ==========================================
    # TOP RIGHT LOGO PLACEHOLDER
    # ==========================================
    with ui.element('div').classes('absolute top-4 right-4 z-50 pointer-events-none bg-white/80 backdrop-blur p-2 rounded shadow-sm'):
        ui.image('/static/ISF_Instituts_Visual_EN_Zeichenfläche 1.png').classes('w-56 h-auto')

    # ==========================================
    # BOTTOM LEFT TELEMETRY HUD
    # ==========================================
    with ui.card().classes('absolute bottom-8 left-4 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200 w-64'):
        ui.label('Live Telemetry').classes('text-sm font-bold text-gray-800')
        lng_label = ui.label(f"Lon: {state['lng']:.5f}").classes('font-mono text-xs')
        lat_label = ui.label(f"Lat: {state['lat']:.5f}").classes('font-mono text-xs')
        alt_msl_label = ui.label(f"MSL: {state['alt_msl']:.1f}m").classes('font-mono text-xs text-blue-700 font-bold')
        wp_label = ui.label('Waypoints: 0').classes('font-mono text-xs text-gray-600 font-bold mt-1')

    # ==========================================
    # RIGHT SIDE SPEED SLIDER
    # ==========================================
    with ui.card().classes('absolute top-1/2 right-4 -translate-y-1/2 z-50 bg-white/90 backdrop-blur shadow-lg border border-gray-200 flex flex-col items-center p-2 w-16'):
        ui.label('SPEED').classes('text-[10px] font-bold text-gray-800 text-center')
        ui.slider(min=0.5, max=10.0, step=0.5, value=1.0).bind_value_to(state, 'speed_mult').props('vertical reverse').classes('h-40 my-2')
        ui.label().bind_text_from(state, 'speed_mult', backward=lambda v: f"{v:.1f}x").classes('text-xs font-mono font-bold text-blue-600')

    await ui.context.client.connected()
    ui.run_javascript('if (typeof window.initMap === "function") window.initMap();')

    # ==========================================
    # EXPORT LOGIC
    # ==========================================
    def export_geojson():
        data = {"type": "FeatureCollection", "features": []}
        if state['boundary'] and len(state['boundary']) >= 3:
            coords = [pt['coords'] for pt in state['boundary']]
            coords.append(coords[0])
            data['features'].append({"type": "Feature", "properties": {"name": "Area Boundary", "actions": [pt['action'] for pt in state['boundary']]}, "geometry": {"type": "Polygon", "coordinates": [coords]}})
        if state['route']:
            coords = [pt['coords'] for pt in state['route']]
            data['features'].append({"type": "Feature", "properties": {"name": "Flight Path"}, "geometry": {"type": "LineString", "coordinates": coords}})
        path = os.path.join(current_dir, 'mission.geojson')
        with open(path, 'w') as f: json.dump(data, f)
        ui.download(path)

    def export_kml(kmz=False):
        if not HAS_GEO: return
        kml = simplekml.Kml()
        if state['boundary'] and len(state['boundary']) >= 3:
            coords = [(pt['coords'][0], pt['coords'][1]) for pt in state['boundary']]
            coords.append(coords[0])
            pol = kml.newpolygon(name="Area Boundary", outerboundaryis=coords)
            pol.style.polystyle.color = '4000ffff'
            pol.style.linestyle.color = 'ff00ffff' 
        if state['route']:
            coords = [(pt['coords'][0], pt['coords'][1], pt['coords'][2] if len(pt['coords'])>2 else 0) for pt in state['route']]
            ls = kml.newlinestring(name="Flight Path", coords=coords)
            ls.altitudemode = simplekml.AltitudeMode.absolute
            ls.style.linestyle.color = 'ffff0000'
            ls.style.linestyle.width = 3
        filename = 'mission.kmz' if kmz else 'mission.kml'
        path = os.path.join(current_dir, filename)
        if kmz: kml.savekmz(path)
        else: kml.save(path)
        ui.download(path)

    # ==========================================
    # FLIGHT & ELEVATION LOGIC
    # ==========================================
    def clear_all():
        state['route'].clear()
        state['boundary'].clear()
        state['target_idx'] = 0
        state['running'] = False
        update_path_display()
        update_boundary_display()

    def get_elevation(lng, lat, open_rasters=None):
        if open_rasters is not None:
            for src, transformer in open_rasters:
                x, y = transformer.transform(lng, lat)
                if src.bounds.left <= x <= src.bounds.right and src.bounds.bottom <= y <= src.bounds.top:
                    try:
                        for val in src.sample([(x, y)]): return float(val[0])
                    except Exception: pass
        elif HAS_GEO:
            for file_list in [state['dsms'], state['dtms']]:
                for path in file_list:
                    try:
                        with rasterio.open(path) as src:
                            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                            x, y = transformer.transform(lng, lat)
                            if src.bounds.left <= x <= src.bounds.right and src.bounds.bottom <= y <= src.bounds.top:
                                for val in src.sample([(x, y)]): return float(val[0])
                    except Exception: continue
        dist = math.sqrt((lng - CENTER_LNG)**2 + (lat - CENTER_LAT)**2)
        return 530.0 + (100.0 * math.exp(-(dist**2) / 0.00005))

    def generate_coverage_path():
        if len(state['boundary']) < 3:
            ui.notify('Please draw a boundary with at least 3 points first.', type='warning')
            return
            
        poly = Polygon([pt['coords'] for pt in state['boundary']])
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
                if intersection.geom_type == 'LineString': coords = list(intersection.coords)
                elif intersection.geom_type == 'MultiLineString':
                    ixmin, iymin, ixmax, iymax = intersection.bounds
                    coords = [(ixmin, iymin), (ixmax, iymax)] if not is_vertical else [(ixmin, iymin), (ixmin, iymax)]
                if not left_to_right: coords.reverse()
                raw_waypoints_2d.extend(coords)
                left_to_right = not left_to_right

        append_sweeps(is_vertical=False)
        if state['pattern'] == 'Grid':
            append_sweeps(is_vertical=True)
            
        open_rasters = []
        if HAS_GEO:
            for path in state['dsms'] + state['dtms']:
                try:
                    src = rasterio.open(path)
                    transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                    open_rasters.append((src, transformer))
                except Exception: pass

        new_route_3d = []
        sample_deg = 5.0 / 111111.0

        for i in range(len(raw_waypoints_2d) - 1):
            p1 = raw_waypoints_2d[i]
            p2 = raw_waypoints_2d[i+1]
            dist = math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            steps = max(1, int(dist / sample_deg))
            for step in range(steps):
                f = step / float(steps)
                lx = p1[0] + f * (p2[0] - p1[0])
                ly = p1[1] + f * (p2[1] - p1[1])
                lz = get_elevation(lx, ly, open_rasters) + state['agl_m']
                new_route_3d.append({'coords': [lx, ly, lz], 'action': state['current_action']})
                
        final_pt = raw_waypoints_2d[-1]
        new_route_3d.append({'coords': [final_pt[0], final_pt[1], get_elevation(final_pt[0], final_pt[1], open_rasters) + state['agl_m']], 'action': state['current_action']})
        
        for src, _ in open_rasters: src.close()
            
        state['route'] = new_route_3d
        state['target_idx'] = 0
        update_path_display()

    def update_boundary_display():
        features = []
        if state['boundary']:
            if len(state['boundary']) >= 3:
                coords = [pt['coords'] for pt in state['boundary']]
                coords.append(coords[0])
                features.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [coords]}})
            elif len(state['boundary']) == 2:
                features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': [pt['coords'] for pt in state['boundary']]}})
            for i, pt in enumerate(state['boundary']):
                features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': pt['coords']}, 'properties': {'label': str(i + 1)}})
        
        print(f"--> PYTHON SENDING BOUNDARY (Points: {len(state['boundary'])})")
        ui.run_javascript(f"window.updateBoundary({json.dumps({'type': 'FeatureCollection', 'features': features})});")

    def update_path_display():
        wp_label.set_text(f"Waypoints: {len(state['route'])}")
        features = []
        if state['route']:
            coords_2d = [[state['lng'], state['lat']]]
            if state['direction'] == 1: coords_2d.extend([[p['coords'][0], p['coords'][1]] for p in state['route'][state['target_idx']:]])
            else: coords_2d.extend([[p['coords'][0], p['coords'][1]] for p in state['route'][:state['target_idx']+1][::-1]])
            features.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords_2d}})
        ui.run_javascript(f"window.updatePath({json.dumps({'type': 'FeatureCollection', 'features': features})});")

    async def poll_waypoints():
        js_code = 'if (window.waypointQueue && window.waypointQueue.length > 0) { let q = window.waypointQueue; window.waypointQueue = []; return q; } return [];'
        try:
            new_clicks = await ui.run_javascript(js_code)
            if new_clicks:
                for pt in new_clicks:
                    print(f"--> PYTHON RECEIVED CLICK: {pt}") 
                    if state['click_mode'] == 'Boundary':
                        state['boundary'].append({'coords': pt, 'action': state['current_action']})
                        update_boundary_display()
                    else:
                        pt_3d = [pt[0], pt[1], get_elevation(pt[0], pt[1]) + state['agl_m']]
                        state['route'].append({'coords': pt_3d, 'action': state['current_action']})
                        update_path_display()
        except Exception as e:
            print(f"--> PYTHON SILENT ERROR CAUGHT: {e}") 

    def flight_controller():
        if not state['running'] or not state['route']: return
            
        movement_budget = SPEED * state['speed_mult']
        
        while movement_budget > 0 and state['route']:
            if state['target_idx'] >= len(state['route']):
                state['target_idx'] = len(state['route']) - 1
                break
                
            target = state['route'][state['target_idx']]['coords']
            dx, dy = target[0] - state['lng'], target[1] - state['lat']
            dz_deg = (target[2] - state['alt_msl']) / 111111.0 
            dist = math.sqrt(dx**2 + dy**2 + dz_deg**2)
            
            if dist <= movement_budget:
                state['lng'], state['lat'], state['alt_msl'] = target[0], target[1], target[2]
                movement_budget -= dist
                if len(state['route']) > 1:
                    state['target_idx'] += state['direction']
                    if state['target_idx'] >= len(state['route']):
                        state['direction'] = -1
                        state['target_idx'] = len(state['route']) - 2 
                    elif state['target_idx'] < 0:
                        state['direction'] = 1
                        state['target_idx'] = 1
            else:
                state['lng'] += (dx / dist) * movement_budget
                state['lat'] += (dy / dist) * movement_budget
                state['alt_msl'] += (dz_deg / dist) * movement_budget * 111111.0
                movement_budget = 0
                
        update_path_display()
        lng_label.set_text(f"Lon: {state['lng']:.5f}")
        lat_label.set_text(f"Lat: {state['lat']:.5f}")
        alt_msl_label.set_text(f"MSL: {state['alt_msl']:.1f}m")
        ui.run_javascript(f"window.updateUAV({state['lng']}, {state['lat']}, {state['alt_msl']}, {state['agl_m']});")

    ui.timer(0.1, poll_waypoints)
    ui.timer(0.1, flight_controller)

ui.run(host='0.0.0.0', port=8080, title="UAV Mission Planner")