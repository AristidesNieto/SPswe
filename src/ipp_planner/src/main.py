from nicegui import ui, app
from shapely.geometry import Polygon, LineString, Point
from shapely.affinity import rotate
import math
import json
import os
import time
import traceback

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

state = {
    'lng': CENTER_LNG, 
    'lat': CENTER_LAT, 
    'route': [], 
    'boundary': [], 
    'click_mode': 'Boundary', 
    'pattern': 'Lawnmower',
    'spacing_m': 30,
    'agl_m': 30,       
    'azimuth': 0, 
    'current_action': 'No action',
    'sources': [],
    'map_servers': [
        {'id': 'osm', 'name': 'OpenStreetMap Base', 'url': 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', 'type': 'raster', 'active': False},
        {'id': 'swisstopo', 'name': 'Swisstopo Aerial', 'url': 'https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.swissimage/default/current/3857/{z}/{x}/{y}.jpeg', 'type': 'raster', 'active': True},
        {'id': 'esri', 'name': 'Esri World Imagery', 'url': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', 'type': 'raster', 'active': False},
        {'id': 'terrainSource', 'name': 'Mapzen Terrarium 3D', 'url': 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', 'type': 'raster-dem', 'active': True}
    ]}

ui.add_head_html(f'''
    <link href="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js"></script>
    <style>
    body {{ margin: 0; padding: 0; overflow: hidden; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }}
        .maplibregl-canvas {{ cursor: crosshair !important; }}
    </style>
    <script>window.MAP_CONFIG = {{ lng: {CENTER_LNG}, lat: {CENTER_LAT} }};</script>
    <script src="/static/map.js?t={time.time()}" defer></script>
''', shared=True)

def send_servers_to_map():
    ui.run_javascript(f"window.syncServers({json.dumps(state['map_servers'])});")

@ui.page('/')
async def main_page():
    ui.query('.nicegui-content').classes('p-0')
    ui.element('div').props('id=map').classes('w-screen h-screen absolute top-0 left-0 z-0')
    
    with ui.card().classes('absolute top-4 left-4 right-4 z-50 bg-white/95 backdrop-blur shadow-lg border border-gray-200 rounded-2xl px-5 py-3'):
        with ui.row().classes('w-full items-center justify-between no-wrap'):
            with ui.row().classes('items-center gap-3 no-wrap'):
                ui.icon('eco', size='md').classes('text-emerald-700')
                with ui.column().classes('gap-0'):
                    ui.label('Crop Health Monitor').classes('text-lg font-bold text-gray-900')
                    ui.label('Crop health dashboard').classes('text-xs text-gray-500')
            with ui.row().classes('items-center gap-2 no-wrap'):
                ui.badge('PROTOTYPE · SAMPLE DATA').props('color=amber text-color=dark')
                with ui.button(icon='layers', on_click=lambda: (refresh_servers(), dlg_servers.open())).props('flat round'):
                    ui.tooltip('Change basemap')
                with ui.button(icon='upload_file', on_click=lambda: dlg_upload.open()).props('flat round'):
                    ui.tooltip('Upload geospatial data')
                with ui.button(icon='folder_open', on_click=lambda: (refresh_sources_list(), dlg_sources.open())).props('flat round'):
                    ui.tooltip('Manage local data sources')
                with ui.button(icon='download', on_click=lambda: dlg_export.open()).props('flat round'):
                    ui.tooltip('Export area and route')
                with ui.button(icon='help_outline', on_click=lambda: dlg_help.open()).props('flat round text-emerald'):
                    ui.tooltip('Help')

    with ui.card().classes('absolute top-24 left-4 z-40 bg-white/95 backdrop-blur shadow-lg border border-gray-200 rounded-2xl w-80 max-w-[calc(100vw-2rem)] max-h-[calc(100vh-7rem)] overflow-y-auto p-4'):
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Intervention plan').classes('text-base font-bold text-gray-900')
            ui.icon('route').classes('text-emerald-700')
        ui.label('Mark the field boundary on the map to plan an inspection or removal route.').classes('text-xs leading-5 text-gray-500')
        ui.radio(
            {'Boundary': 'Draw field boundary', 'Waypoints': 'Add points'},
            value='Boundary',
        ).bind_value_to(state, 'click_mode').props('inline').classes('w-full mt-2')
        ui.select(
            ['No action', 'Remove plant', 'Inspect plant', 'Collect sample'],
            value='No action',
            label='Intervention action',
        ).bind_value_to(state, 'current_action').classes('w-full mt-2')
        ui.select(
            {'Lawnmower': 'Parallel passes', 'Grid': 'Grid'},
            value='Lawnmower',
            label='Route pattern',
        ).bind_value_to(state, 'pattern').classes('w-full mt-2')
        ui.number('Pass spacing (m)', value=30, min=2, max=500).bind_value_to(state, 'spacing_m').classes('w-full mt-2')
        with ui.row().classes('w-full gap-2 mt-3'):
            ui.button('Generate route', icon='route', on_click=lambda: generate_coverage_path()).classes('bg-emerald-700 text-white flex-1')
            with ui.button(icon='delete_sweep', on_click=lambda: clear_all()).props('outline').classes('text-gray-600'):
                ui.tooltip('Clear field and route')
        wp_label = ui.label('Route points: 0').classes('text-xs font-semibold text-emerald-800 mt-3')
        ui.separator().classes('my-3')
        with ui.row().classes('w-full items-center justify-between'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('sensors').classes('text-sky-700')
                ui.label('Device tracking').classes('text-sm font-bold text-gray-900')
            tracking_status_badge = ui.badge('Ready', color='grey').props('rounded')
        ui.label('Route-following simulation · no live device data').classes('text-[11px] text-gray-500')
        tracking_position_label = ui.label('Position: —').classes('text-xs font-mono text-gray-700 mt-1')
        tracking_progress_label = ui.label('Progress: 0%').classes('text-xs text-gray-500')
        with ui.row().classes('w-full gap-2 mt-2'):
            start_tracking_button = ui.button(
                'Start',
                icon='play_arrow',
                on_click=lambda: start_tracking(),
            ).props('disable').classes('bg-sky-700 text-white flex-1')
            stop_tracking_button = ui.button(
                'Stop',
                icon='stop',
                on_click=lambda: stop_tracking(),
            ).props('outline disable').classes('text-gray-600 flex-1')

    # ==========================================
    # POPUP DIALOGS (Settings, Upload, Export)
    # ==========================================
    with ui.dialog() as dlg_help, ui.card().classes('w-96 max-h-[80vh] overflow-y-auto'):
        ui.label('Using the map').classes('text-xl font-bold text-emerald-800')
        ui.markdown("""
**Navigation**

- **Pan:** drag the map.
- **Zoom:** use the mouse wheel or map controls.

**Intervention planning**

- Select “Draw field boundary” and mark at least three points around the field.
- Choose an action and generate a coverage route.

The hotspots and figures shown are sample data for demonstration only.
""")
        ui.button('Close', on_click=dlg_help.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_upload, ui.card().classes('w-80'):
        ui.label('Upload geospatial data').classes('text-lg font-bold')
        upload_type = ui.select(['DSM', 'DTM', 'Orthomosaic'], value='DSM', label='Raster layer type').classes('w-full mt-2')
        
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
            state['sources'].append({'name': file_name, 'path': path, 'type': cat, 'active': True})
            ui.notify(f'Loaded {cat}: {file_name}', type='positive')

        ui.upload(multiple=True, on_upload=handle_upload).classes('w-full mt-2')
        ui.button('Close', on_click=dlg_upload.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_sources, ui.card().classes('w-96'):
        ui.label('Local data sources').classes('text-lg font-bold')
        sources_container = ui.column().classes('w-full mt-2')
        
        def refresh_sources_list():
            sources_container.clear()
            with sources_container:
                if not state['sources']: ui.label('No files uploaded yet.').classes('text-sm text-gray-400 italic')
                else:
                    for src in state['sources']:
                        with ui.row().classes('w-full items-center justify-between border-b pb-1 mb-1'):
                            ui.checkbox(src['name'], value=src['active']).bind_value_to(src, 'active').classes('text-sm truncate w-48')
                            color = 'blue' if src['type'] == 'DSM' else 'green' if src['type'] == 'DTM' else 'orange'
                            ui.badge(src['type'], color=color)

        ui.button('Close', on_click=dlg_sources.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_servers, ui.card().classes('w-96 max-h-[80vh] overflow-y-auto'):
        ui.label('Basemaps').classes('text-lg font-bold')
        server_list = ui.column().classes('w-full mt-2')
        
        def update_server_state(server_dict, is_active):
            server_dict['active'] = is_active
            send_servers_to_map()

        def refresh_servers():
            server_list.clear()
            with server_list:
                for s in state['map_servers']:
                    with ui.row().classes('w-full items-center justify-between border-b pb-1 mb-1'):
                        ui.checkbox(s['name'], value=s['active'], on_change=lambda e, s=s: update_server_state(s, e.value)).classes('text-sm truncate w-48')
                        ui.badge('Terrain' if s['type'] == 'raster-dem' else 'Basemap', color='purple' if s['type'] == 'raster-dem' else 'blue')

        with ui.expansion('Add Custom Server', icon='add').classes('w-full mt-2 border rounded'):
            new_name = ui.input('Server Name', placeholder='e.g. Satellite Imagery').classes('w-full')
            new_url = ui.input('Tile URL (XYZ)', placeholder='https://.../{z}/{x}/{y}.png').classes('w-full')
            new_type = ui.select(['raster', 'raster-dem'], value='raster', label='Type').classes('w-full mt-2')
            def add_server():
                if new_name.value and new_url.value:
                    new_id = new_name.value.lower().replace(' ', '-')
                    state['map_servers'].append({'id': new_id, 'name': new_name.value, 'url': new_url.value, 'type': new_type.value, 'active': True})
                    refresh_servers()
                    send_servers_to_map()
                    new_name.value = ""
                    new_url.value = ""
            ui.button('Add Server', on_click=add_server).classes('mt-2 bg-blue-600 text-white w-full')

        ui.button('Close', on_click=dlg_servers.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.dialog() as dlg_export, ui.card().classes('w-80'):
        ui.label('Export intervention plan').classes('text-lg font-bold')
        ui.button('Download GeoJSON', on_click=lambda: export_geojson()).classes('w-full mt-2 bg-gray-800 text-white')
        ui.button('Download KML', on_click=lambda: export_kml(kmz=False)).classes('w-full mt-2 bg-gray-800 text-white')
        ui.button('Download KMZ', on_click=lambda: export_kml(kmz=True)).classes('w-full mt-2 bg-gray-800 text-white')
        ui.button('Close', on_click=dlg_export.close).classes('w-full mt-4 bg-gray-200 text-gray-800')

    with ui.card().classes('absolute top-24 right-4 z-40 bg-white/95 backdrop-blur shadow-lg border border-gray-200 rounded-2xl w-72 max-w-[calc(100vw-2rem)] max-h-[calc(100vh-7rem)] overflow-y-auto p-4'):
        with ui.row().classes('w-full items-center justify-between'):
            with ui.column().classes('gap-0'):
                ui.label('Field devices').classes('text-base font-bold text-gray-900')
                ui.label('Portable units · sample data').classes('text-xs text-gray-500')
            ui.icon('sensors').classes('text-emerald-700')
        ui.label('Equipment farmers can carry into the field to record areas of concern.').classes('text-xs leading-5 text-gray-500 mt-2')
        with ui.row().classes('w-full gap-2 mt-3'):
            with ui.column().classes('flex-1 rounded-xl bg-emerald-50 p-3 gap-0'):
                ui.label('1').classes('text-2xl font-bold text-emerald-700')
                ui.label('connected').classes('text-[11px] text-emerald-900')
            with ui.column().classes('flex-1 rounded-xl bg-gray-100 p-3 gap-0'):
                ui.label('1').classes('text-2xl font-bold text-gray-600')
                ui.label('offline').classes('text-[11px] text-gray-700')
        with ui.column().classes('w-full gap-2 mt-3'):
            with ui.row().classes('w-full items-center justify-between rounded-xl border border-gray-200 p-3'):
                with ui.row().classes('items-center gap-3 no-wrap'):
                    ui.icon('sensors').classes('text-emerald-700')
                    with ui.column().classes('gap-0'):
                        ui.label('Scout-01').classes('text-sm font-semibold text-gray-900')
                        ui.label('Portable unit · North field').classes('text-[11px] text-gray-500')
                ui.badge('Connected', color='green').props('rounded')
            with ui.row().classes('w-full items-center justify-between rounded-xl border border-gray-200 p-3'):
                with ui.row().classes('items-center gap-3 no-wrap'):
                    ui.icon('sensors').classes('text-gray-400')
                    with ui.column().classes('gap-0'):
                        ui.label('Scout-02').classes('text-sm font-semibold text-gray-900')
                        ui.label('Portable unit · East field').classes('text-[11px] text-gray-500')
                ui.badge('Offline', color='grey').props('rounded')
        ui.button('Add device', icon='add').props('outline disable').classes('w-full mt-3 text-emerald-800')
        ui.label('Device registration and live connections are not implemented yet.').classes('text-[11px] leading-4 text-gray-400 mt-2')
        ui.separator().classes('my-4')
        ui.label('Crop overview').classes('text-base font-bold text-gray-900')
        ui.label('Previous season · sample data').classes('text-xs text-gray-500')
        with ui.row().classes('w-full gap-2 mt-3'):
            with ui.column().classes('flex-1 rounded-xl bg-amber-50 p-3 gap-0'):
                ui.label('3').classes('text-2xl font-bold text-amber-700')
                ui.label('recorded hotspots').classes('text-[11px] text-amber-900')
            with ui.column().classes('flex-1 rounded-xl bg-rose-50 p-3 gap-0'):
                ui.label('18%').classes('text-2xl font-bold text-rose-700')
                ui.label('area under observation').classes('text-[11px] text-rose-900')
        ui.separator().classes('my-3')
        ui.switch(
            'Show historical hotspots',
            value=True,
            on_change=lambda e: ui.run_javascript(
                f"window.setHistoricalHotspotsVisible({str(e.value).lower()});"
            ),
        ).classes('text-sm')
        with ui.row().classes('w-full items-center gap-2 mt-3'):
            ui.label('Lower').classes('text-[10px] text-gray-500')
            ui.element('div').classes('h-2 flex-1 rounded-full').style(
                'background: linear-gradient(90deg, #a3e635, #facc15, #fb923c, #dc2626);'
            )
            ui.label('Higher').classes('text-[10px] text-gray-500')
        ui.label('Colored areas are illustrative and do not represent actual farm measurements.').classes('text-xs leading-5 text-gray-500 mt-2')

    # ==========================================
    # BOTTOM MAP STATUS AND ROUTE ORIENTATION
    # ==========================================
    with ui.card().classes('absolute bottom-5 left-1/2 -translate-x-1/2 z-40 bg-white/95 backdrop-blur shadow-lg border border-gray-200 rounded-2xl flex flex-row items-center p-2 w-80 max-w-[calc(100vw-2rem)] gap-3'):
        compass_icon = ui.icon('navigation', size='sm').classes('text-emerald-700').style(f"transform: rotate({state['azimuth']}deg); transition: transform 0.1s;")
        ui.label('Route heading').classes('text-xs font-semibold text-gray-700')
        def on_slider_change(e):
            compass_icon.style(f'transform: rotate({e.value}deg);')
            if len(state['boundary']) >= 3:
                generate_coverage_path(show_warning=False)
                
        ui.slider(min=0, max=180, step=1, value=0, on_change=on_slider_change).bind_value_to(state, 'azimuth').classes('flex-1')
        ui.label().bind_text_from(state, 'azimuth', backward=lambda v: f"{int(v)}°").classes('text-xs font-mono font-bold text-emerald-700 w-8 text-right')

    await ui.context.client.connected()
    ui.run_javascript('if (typeof window.initMap === "function") window.initMap();')
    send_servers_to_map()

    # ==========================================
    # EXPORT LOGIC
    # ==========================================
    def export_geojson():
        data = {"type": "FeatureCollection", "features": []}
        if state['boundary'] and len(state['boundary']) >= 3:
            coords = [pt['coords'] for pt in state['boundary']]
            coords.append(coords[0])
            data['features'].append({"type": "Feature", "properties": {"name": "Intervention area", "actions": [pt['action'] for pt in state['boundary']]}, "geometry": {"type": "Polygon", "coordinates": [coords]}})
        if state['route']:
            coords = [pt['coords'] for pt in state['route']]
            data['features'].append({"type": "Feature", "properties": {"name": "Intervention route"}, "geometry": {"type": "LineString", "coordinates": coords}})
        path = os.path.join(current_dir, 'intervencion.geojson')
        with open(path, 'w') as f: json.dump(data, f)
        ui.download(path)

    def export_kml(kmz=False):
        if not HAS_GEO: return
        kml = simplekml.Kml()
        if state['boundary'] and len(state['boundary']) >= 3:
            coords = [(pt['coords'][0], pt['coords'][1]) for pt in state['boundary']]
            coords.append(coords[0])
            pol = kml.newpolygon(name="Intervention area", outerboundaryis=coords)
            pol.style.polystyle.color = '4000ffff'
            pol.style.linestyle.color = 'ff00ffff' 
        if state['route']:
            coords = [(pt['coords'][0], pt['coords'][1], pt['coords'][2] if len(pt['coords'])>2 else 0) for pt in state['route']]
            ls = kml.newlinestring(name="Intervention route", coords=coords)
            ls.altitudemode = simplekml.AltitudeMode.absolute
            ls.style.linestyle.color = 'ffff0000'
            ls.style.linestyle.width = 3
        filename = 'intervencion.kmz' if kmz else 'intervencion.kml'
        path = os.path.join(current_dir, filename)
        if kmz: kml.savekmz(path)
        else: kml.save(path)
        ui.download(path)

    # ==========================================
    # FLIGHT & ELEVATION LOGIC
    # ==========================================
    is_tracking = False
    tracking_index = 0

    def update_tracking_display(status, badge_color, progress):
        tracking_status_badge.set_text(status)
        tracking_status_badge.props(f'color={badge_color}')
        tracking_progress_label.set_text(f'Progress: {progress}%')
        start_tracking_button.set_enabled(bool(state['route']) and not is_tracking)
        stop_tracking_button.set_enabled(is_tracking)

    def stop_tracking():
        nonlocal is_tracking
        is_tracking = False
        tracking_timer.deactivate()
        progress = int(tracking_index / max(len(state['route']) - 1, 1) * 100) if state['route'] else 0
        status = 'Complete' if state['route'] and tracking_index >= len(state['route']) - 1 else 'Stopped'
        update_tracking_display(status, 'green' if status == 'Complete' else 'grey', progress)

    def start_tracking():
        nonlocal is_tracking, tracking_index
        if len(state['route']) < 2:
            ui.notify('Generate a route with at least two points before starting tracking.', type='warning')
            return
        tracking_index = 0
        is_tracking = True
        start = state['route'][tracking_index]['coords']
        tracking_position_label.set_text(f'Position: {start[1]:.5f}, {start[0]:.5f}')
        ui.run_javascript(f'window.updateSimulatedDevice({json.dumps(start[:2])});')
        update_tracking_display('Simulating', 'blue', 0)
        tracking_timer.activate()

    def update_tracking():
        nonlocal tracking_index
        if not is_tracking or not state['route']:
            return
        tracking_index = min(
            tracking_index + max(1, math.ceil((len(state['route']) - 1) / 120)),
            len(state['route']) - 1,
        )
        coords = state['route'][tracking_index]['coords']
        tracking_position_label.set_text(f'Position: {coords[1]:.5f}, {coords[0]:.5f}')
        ui.run_javascript(f'window.updateSimulatedDevice({json.dumps(coords[:2])});')
        progress = int(tracking_index / (len(state['route']) - 1) * 100)
        if tracking_index >= len(state['route']) - 1:
            stop_tracking()
        else:
            update_tracking_display('Simulating', 'blue', progress)

    tracking_timer = ui.timer(0.25, update_tracking, active=False)

    def clear_all():
        nonlocal tracking_index
        if is_tracking:
            stop_tracking()
        state['route'].clear()
        state['boundary'].clear()
        tracking_index = 0
        tracking_position_label.set_text('Position: —')
        tracking_status_badge.set_text('Ready')
        tracking_status_badge.props('color=grey')
        tracking_progress_label.set_text('Progress: 0%')
        start_tracking_button.disable()
        update_path_display()
        update_boundary_display()
        ui.run_javascript('window.clearSimulatedDevice();')

    def get_elevation(lng, lat, open_rasters=None):
        if open_rasters is not None:
            for src, transformer in open_rasters:
                x, y = transformer.transform(lng, lat)
                if src.bounds.left <= x <= src.bounds.right and src.bounds.bottom <= y <= src.bounds.top:
                    try:
                        for val in src.sample([(x, y)]): return float(val[0])
                    except Exception: pass
        elif HAS_GEO:
            for cat in ['DSM', 'DTM']:
                for src_item in [s for s in state['sources'] if s['active'] and s['type'] == cat]:
                    try:
                        with rasterio.open(src_item['path']) as src:
                            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
                            x, y = transformer.transform(lng, lat)
                            if src.bounds.left <= x <= src.bounds.right and src.bounds.bottom <= y <= src.bounds.top:
                                for val in src.sample([(x, y)]): return float(val[0])
                    except Exception: continue
        dist = math.sqrt((lng - CENTER_LNG)**2 + (lat - CENTER_LAT)**2)
        return 530.0 + (100.0 * math.exp(-(dist**2) / 0.00005))
        
    def check_and_close_route():
        if len(state['route']) > 2:
            p1 = state['route'][0]['coords']
            p2 = state['route'][-1]['coords']
            dx, dy = p1[0] - p2[0], p1[1] - p2[1]
            dist_m = math.sqrt((dx * 111111.0 * math.cos(math.radians(CENTER_LAT)))**2 + (dy * 111111.0)**2)
            if dist_m < 15.0:
                state['route'][-1]['coords'] = p1.copy()

    def generate_coverage_path(show_warning=True):
        nonlocal tracking_index
        if len(state['boundary']) < 3:
            if show_warning:
                ui.notify('Mark at least three points to draw the field boundary.', type='warning')
            return
            
        poly = Polygon([pt['coords'] for pt in state['boundary']])
        centroid = poly.centroid
        angle_math = 90 - state['azimuth']
        
        rotated_poly = rotate(poly, -angle_math, origin=centroid)
        minx, miny, maxx, maxy = rotated_poly.bounds
        
        spacing_deg_y = state['spacing_m'] / 111111.0
        spacing_deg_x = state['spacing_m'] / (111111.0 * math.cos(math.radians(CENTER_LAT)))
        
        def generate_2d_variant(start_left, reverse_sweeps):
            coords_list = []
            def append(is_vertical):
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
                if reverse_sweeps: sweeps.reverse()
                
                left_to_right = start_left
                for line in sweeps:
                    intersection = rotated_poly.intersection(line)
                    if intersection.is_empty: continue
                    seg_coords = []
                    if intersection.geom_type == 'LineString': seg_coords = list(intersection.coords)
                    elif intersection.geom_type == 'MultiLineString':
                        ixmin, iymin, ixmax, iymax = intersection.bounds
                        seg_coords = [(ixmin, iymin), (ixmax, iymax)] if not is_vertical else [(ixmin, iymin), (ixmin, iymax)]
                    if not left_to_right: seg_coords.reverse()
                    coords_list.extend(seg_coords)
                    left_to_right = not left_to_right
            append(is_vertical=False)
            if state['pattern'] == 'Grid':
                append(is_vertical=True)
            return coords_list

        variants = [
            generate_2d_variant(start_left=True, reverse_sweeps=False),
            generate_2d_variant(start_left=False, reverse_sweeps=False),
            generate_2d_variant(start_left=True, reverse_sweeps=True),
            generate_2d_variant(start_left=False, reverse_sweeps=True)
        ]
        
        variants = [v for v in variants if len(v) > 0]
        if not variants: return
        
        best_variant = None
        min_dist = float('inf')
        for v in variants:
            first_pt = rotate(Point(v[0]), angle_math, origin=centroid)
            dx = first_pt.x - state['lng']
            dy = first_pt.y - state['lat']
            dist = dx*dx + dy*dy
            if dist < min_dist:
                min_dist = dist
                best_variant = v
                
        raw_waypoints_2d = []
        for pt in best_variant:
            rot_pt = rotate(Point(pt), angle_math, origin=centroid)
            raw_waypoints_2d.append([rot_pt.x, rot_pt.y])
            
        open_rasters = []
        if HAS_GEO:
            for src_item in [s for s in state['sources'] if s['active'] and s['type'] in ['DSM', 'DTM']]:
                try:
                    src = rasterio.open(src_item['path'])
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
            
        if is_tracking:
            stop_tracking()
        state['route'] = new_route_3d
        tracking_index = 0
        tracking_position_label.set_text('Position: —')
        tracking_status_badge.set_text('Ready')
        tracking_status_badge.props('color=grey')
        tracking_progress_label.set_text('Progress: 0%')
        check_and_close_route() 
        update_path_display()
        ui.run_javascript('window.clearSimulatedDevice();')

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
        ui.run_javascript(f"window.updateBoundary({json.dumps({'type': 'FeatureCollection', 'features': features})});")

    def update_path_display():
        wp_label.set_text(f"Route points: {len(state['route'])}")
        start_tracking_button.set_enabled(len(state['route']) >= 2 and not is_tracking)
        features = []
        if state['route']:
            start = state['route'][0]['coords']
            end = state['route'][-1]['coords']
            if len(state['route']) > 1:
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [[p['coords'][0], p['coords'][1]] for p in state['route']],
                    },
                })
            endpoints = [(start, 'Inicio')]
            if start != end:
                endpoints.append((end, 'Fin'))
            for point, label in endpoints:
                features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': [point[0], point[1]]},
                    'properties': {'label': label},
                })
                
        ui.run_javascript(f"window.updatePath({json.dumps({'type': 'FeatureCollection', 'features': features})});")

    async def poll_waypoints():
        # Skip polling if the browser tab isn't fully connected yet
        if not ui.context.client.has_socket_connection:
            return
            
        js_code = 'if (window.waypointQueue && window.waypointQueue.length > 0) { let q = window.waypointQueue; window.waypointQueue = []; return q; } return [];'
        
        try:
            # Execute JS and wait for the response
            new_clicks = await ui.run_javascript(js_code, timeout=1.0)
            # TODO: Reset timeout counter
            if new_clicks:
                for pt in new_clicks:
                    if state['click_mode'] == 'Boundary':
                        state['boundary'].append({'coords': pt, 'action': state['current_action']})
                        update_boundary_display()
                    else:
                        if is_tracking:
                            stop_tracking()
                            ui.run_javascript('window.clearSimulatedDevice();')
                        pt_3d = [pt[0], pt[1], get_elevation(pt[0], pt[1]) + state['agl_m']]
                        state['route'].append({'coords': pt_3d, 'action': state['current_action']})
                        check_and_close_route() 
                        update_path_display()
                        
        except TimeoutError:
            # Client is busy or loading, silently skip this tick
            # TODO: Implement a counter, display error if timeout takes to long
            pass
        except Exception as e:
            # Only print actual runtime crashes, ignore disconnection warnings
            if "JavaScript did not respond" not in str(e):
                print(f"Polling Error: {e}")
    
    ui.timer(0.1, poll_waypoints)

ui.run(host='127.0.0.1', port=int(os.environ.get('PORT', 8091)), title="Crop Health Monitor")