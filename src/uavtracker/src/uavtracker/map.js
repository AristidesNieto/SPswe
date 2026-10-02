console.log("[map.js] File loaded successfully!");
window.waypointQueue = [];

window.initMap = function() {
    if (!document.getElementById('map')) {
        setTimeout(window.initMap, 50);
        return;
    }

    if (window.mapInstance) return;

    window.mapInstance = new maplibregl.Map({
        container: 'map',
        style: {
            'version': 8,
            'sources': {
                'osm': {
                    'type': 'raster',
                    'tiles': ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                    'tileSize': 256,
                    'attribution': '&copy; OpenStreetMap'
                },
                'terrainSource': {
                    'type': 'raster-dem',
                    'tiles': ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
                    'encoding': 'terrarium',
                    'tileSize': 256,
                    'maxzoom': 14
                }
            },
            'layers': [{ 'id': 'osm', 'type': 'raster', 'source': 'osm' }],
            'terrain': { 'source': 'terrainSource', 'exaggeration': 1.5 }
        },
        center: [window.MAP_CONFIG.lng, window.MAP_CONFIG.lat],
        zoom: 14.5, 
        pitch: 65,     
        maxPitch: 85   
    });

    window.mapInstance.addControl(
        new maplibregl.NavigationControl({ visualizePitch: true, showZoom: true, showCompass: true }), 
        'bottom-right'
    );

    window.mapInstance.on('load', () => {
        window.mapInstance.getCanvas().style.cursor = 'crosshair';

        // --- Boundary Layers ---
        window.mapInstance.addSource('boundary', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({ 'id': 'boundary-fill', 'type': 'fill', 'source': 'boundary', 'filter': ['==', '$type', 'Polygon'], 'paint': { 'fill-color': '#facc15', 'fill-opacity': 0.3 } });
        window.mapInstance.addLayer({ 'id': 'boundary-line', 'type': 'line', 'source': 'boundary', 'filter': ['in', '$type', 'Polygon', 'LineString'], 'paint': { 'line-color': '#ca8a04', 'line-width': 2, 'line-dasharray': [2, 2] } });
        window.mapInstance.addLayer({ 'id': 'boundary-points', 'type': 'circle', 'source': 'boundary', 'filter': ['==', '$type', 'Point'], 'paint': { 'circle-radius': 10, 'circle-color': '#facc15', 'circle-stroke-width': 2, 'circle-stroke-color': '#ca8a04' } });
        window.mapInstance.addLayer({ 'id': 'boundary-labels', 'type': 'symbol', 'source': 'boundary', 'filter': ['==', '$type', 'Point'], 'layout': { 'text-field': ['get', 'label'], 'text-size': 12, 'text-allow-overlap': true }, 'paint': { 'text-color': '#000000' } });

        // --- Path Layers (Ground Track) ---
        window.mapInstance.addSource('path', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({ 'id': 'path-line', 'type': 'line', 'source': 'path', 'filter': ['==', '$type', 'LineString'], 'paint': { 'line-color': '#3b82f6', 'line-width': 3 } });

        // --- UAV Shadow (Draped on ground) ---
        window.mapInstance.addSource('uav-shadow', { 'type': 'geojson', 'data': { 'type': 'Point', 'coordinates': [window.MAP_CONFIG.lng, window.MAP_CONFIG.lat] } });
        window.mapInstance.addLayer({ 'id': 'uav-shadow-layer', 'type': 'circle', 'source': 'uav-shadow', 'paint': { 'circle-radius': 8, 'circle-color': '#000', 'circle-blur': 0.8, 'circle-opacity': 0.5 } });

        // --- UAV True 3D Marker (Floating Extrusion) ---
        window.mapInstance.addSource('uav-marker', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({
            'id': 'uav-marker-layer',
            'type': 'fill-extrusion',
            'source': 'uav-marker',
            'paint': {
                'fill-extrusion-color': '#ef4444',
                'fill-extrusion-height': ['get', 'height'], // Top of the drone box
                'fill-extrusion-base': ['get', 'base'],     // Bottom of the drone box
                'fill-extrusion-opacity': 1.0
            }
        });
        
        setTimeout(() => window.mapInstance.resize(), 100);
    });

    window.mapInstance.on('click', (e) => {
        window.waypointQueue.push([e.lngLat.lng, e.lngLat.lat]);
    });
};

// NEW: Accepts AGL from Python to float the cube correctly
window.updateUAV = function(lng, lat, alt_msl, agl) {
    if (window.mapInstance) {
        if (window.mapInstance.getSource('uav-shadow')) {
            window.mapInstance.getSource('uav-shadow').setData({ 'type': 'Point', 'coordinates': [lng, lat] });
        }
        if (window.mapInstance.getSource('uav-marker')) {
            // Draw a tiny 4x4 meter box around the coordinate
            const size = 0.00002; 
            window.mapInstance.getSource('uav-marker').setData({
                'type': 'Feature',
                'properties': {
                    'base': agl - 1,   // Extrude starting 1 meter below AGL
                    'height': agl + 1  // Extrude ending 1 meter above AGL (creates a 2m tall floating red block)
                },
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[
                        [lng - size, lat - size],
                        [lng + size, lat - size],
                        [lng + size, lat + size],
                        [lng - size, lat + size],
                        [lng - size, lat - size]
                    ]]
                }
            });
        }
    }
};

window.updatePath = function(geojson) {
    if (window.mapInstance && window.mapInstance.getSource('path')) {
        window.mapInstance.getSource('path').setData(geojson);
    }
};

window.updateBoundary = function(geojson) {
    if (window.mapInstance && window.mapInstance.getSource('boundary')) {
        window.mapInstance.getSource('boundary').setData(geojson);
    }
};