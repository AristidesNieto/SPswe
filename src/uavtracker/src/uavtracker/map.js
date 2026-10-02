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
                // NEW: FOSS Mapzen Terrarium tiles for 3D elevation
                'terrainSource': {
                    'type': 'raster-dem',
                    'tiles': ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
                    'encoding': 'terrarium',
                    'tileSize': 256,
                    'maxzoom': 14
                }
            },
            'layers': [{ 'id': 'osm', 'type': 'raster', 'source': 'osm' }],
            // NEW: Enable 3D terrain rendering with slight height exaggeration
            'terrain': { 'source': 'terrainSource', 'exaggeration': 1.5 }
        },
        center: [window.MAP_CONFIG.lng, window.MAP_CONFIG.lat],
        zoom: 14.5, 
        pitch: 65,     // Increased pitch to see the horizon and 3D shapes better
        maxPitch: 85   // Allow the user to tilt the camera further down
    });

    // NEW: Add a 3D navigation control to the bottom right
    window.mapInstance.addControl(
        new maplibregl.NavigationControl({
            visualizePitch: true,
            showZoom: true,
            showCompass: true
        }), 
        'bottom-right'
    );

    window.mapInstance.on('load', () => {
        // Change the cursor to a crosshair natively
        window.mapInstance.getCanvas().style.cursor = 'crosshair';

        // --- Boundary Layers ---
        window.mapInstance.addSource('boundary', {
            'type': 'geojson',
            'data': { 'type': 'FeatureCollection', 'features': [] }
        });

        window.mapInstance.addLayer({
            'id': 'boundary-fill',
            'type': 'fill',
            'source': 'boundary',
            'filter': ['==', '$type', 'Polygon'], 
            'paint': { 'fill-color': '#facc15', 'fill-opacity': 0.3 }
        });

        window.mapInstance.addLayer({
            'id': 'boundary-line',
            'type': 'line',
            'source': 'boundary',
            'filter': ['in', '$type', 'Polygon', 'LineString'],
            'paint': { 'line-color': '#ca8a04', 'line-width': 2, 'line-dasharray': [2, 2] }
        });

        window.mapInstance.addLayer({
            'id': 'boundary-points',
            'type': 'circle',
            'source': 'boundary',
            'filter': ['==', '$type', 'Point'], 
            'paint': { 'circle-radius': 10, 'circle-color': '#facc15', 'circle-stroke-width': 2, 'circle-stroke-color': '#ca8a04' }
        });

        window.mapInstance.addLayer({
            'id': 'boundary-labels',
            'type': 'symbol',
            'source': 'boundary',
            'filter': ['==', '$type', 'Point'],
            'layout': { 'text-field': ['get', 'label'], 'text-size': 12, 'text-allow-overlap': true },
            'paint': { 'text-color': '#000000' } 
        });

        // --- Path Layers ---
        window.mapInstance.addSource('path', {
            'type': 'geojson',
            'data': { 'type': 'FeatureCollection', 'features': [] }
        });

        window.mapInstance.addLayer({
            'id': 'path-line',
            'type': 'line',
            'source': 'path',
            'filter': ['==', '$type', 'LineString'],
            'paint': { 'line-color': '#3b82f6', 'line-width': 3 }
        });

        window.mapInstance.addLayer({
            'id': 'path-points',
            'type': 'circle',
            'source': 'path',
            'filter': ['==', '$type', 'Point'],
            'paint': { 'circle-radius': 10, 'circle-color': '#3b82f6', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' }
        });

        window.mapInstance.addLayer({
            'id': 'path-labels',
            'type': 'symbol',
            'source': 'path',
            'filter': ['==', '$type', 'Point'],
            'layout': { 'text-field': ['get', 'label'], 'text-size': 12, 'text-allow-overlap': true },
            'paint': { 'text-color': '#ffffff' } 
        });

        // --- UAV Layers ---
        window.mapInstance.addSource('uav', {
            'type': 'geojson',
            'data': { 'type': 'Point', 'coordinates': [window.MAP_CONFIG.lng, window.MAP_CONFIG.lat] }
        });

        window.mapInstance.addLayer({
            'id': 'uav-shadow',
            'type': 'circle',
            'source': 'uav',
            'paint': { 'circle-radius': 8, 'circle-color': '#000', 'circle-blur': 0.8, 'circle-opacity': 0.4, 'circle-translate': [0, 20] }
        });

        window.mapInstance.addLayer({
            'id': 'uav-marker',
            'type': 'circle',
            'source': 'uav',
            'paint': { 'circle-radius': 8, 'circle-color': '#ef4444', 'circle-stroke-width': 3, 'circle-stroke-color': '#ffffff' }
        });
        
        setTimeout(() => window.mapInstance.resize(), 100);
    });

    window.mapInstance.on('click', (e) => {
        window.waypointQueue.push([e.lngLat.lng, e.lngLat.lat]);
    });
};

window.updateUAV = function(lng, lat) {
    if (window.mapInstance && window.mapInstance.getSource('uav')) {
        window.mapInstance.getSource('uav').setData({ 'type': 'Point', 'coordinates': [lng, lat] });
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