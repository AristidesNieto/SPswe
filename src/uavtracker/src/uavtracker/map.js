console.log("[map.js] File loaded successfully! Waiting for clicks...");
window.waypointQueue = [];

window.initMap = function () {
    if (!document.getElementById('map')) {
        setTimeout(window.initMap, 50);
        return;
    }
    if (window.mapInstance) return;

    window.mapInstance = new maplibregl.Map({
        container: 'map',
        style: {
            'version': 8,
            'glyphs': 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
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
        zoom: 14.5, pitch: 65, maxPitch: 85
    });

    window.mapInstance.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showZoom: true, showCompass: true }), 'bottom-right');

    window.mapInstance.on('load', () => {
        window.mapInstance.getCanvas().style.cursor = 'crosshair';

        // --- Boundary Layers ---
        window.mapInstance.addSource('boundary', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({ 'id': 'boundary-fill', 'type': 'fill', 'source': 'boundary', 'paint': { 'fill-color': '#facc15', 'fill-opacity': 0.3 } });
        window.mapInstance.addLayer({ 'id': 'boundary-line', 'type': 'line', 'source': 'boundary', 'paint': { 'line-color': '#ca8a04', 'line-width': 2, 'line-dasharray': [2, 2] } });
        window.mapInstance.addLayer({ 'id': 'boundary-points', 'type': 'circle', 'source': 'boundary', 'paint': { 'circle-radius': 10, 'circle-color': '#facc15', 'circle-stroke-width': 2, 'circle-stroke-color': '#ca8a04' } });

        // --- Path Layers (Ground Track) ---
        window.mapInstance.addSource('path', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({ 'id': 'path-line', 'type': 'line', 'source': 'path', 'paint': { 'line-color': '#3b82f6', 'line-width': 3 } });

        // --- UAV Shadow & Marker ---
        window.mapInstance.addSource('uav-shadow', { 'type': 'geojson', 'data': { 'type': 'Point', 'coordinates': [window.MAP_CONFIG.lng, window.MAP_CONFIG.lat] } });
        window.mapInstance.addLayer({ 'id': 'uav-shadow-layer', 'type': 'circle', 'source': 'uav-shadow', 'paint': { 'circle-radius': 8, 'circle-color': '#000', 'circle-blur': 0.8, 'circle-opacity': 0.5 } });

        window.mapInstance.addSource('uav-marker', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({
            'id': 'uav-marker-layer',
            'type': 'fill-extrusion',
            'source': 'uav-marker',
            'paint': {
                'fill-extrusion-color': '#ef4444',
                'fill-extrusion-height': ['get', 'height'],
                'fill-extrusion-base': ['get', 'base'],
                'fill-extrusion-opacity': 1.0
            }
        });

        setTimeout(() => window.mapInstance.resize(), 100);
    });

    window.mapInstance.on('click', (e) => {
        window.waypointQueue.push([e.lngLat.lng, e.lngLat.lat]);
    });
};

// NEW: Dynamically loads, hides, and switches raster/terrain servers
window.syncServers = function (servers) {
    if (!window.mapInstance || !window.mapInstance.isStyleLoaded()) {
        setTimeout(() => window.syncServers(servers), 500);
        return;
    }

    let activeDem = null;

    servers.forEach(server => {
        const sourceId = server.id;
        const layerId = (server.id === 'osm') ? 'osm' : server.id + '-layer';

        if (server.active) {
            // If source doesn't exist, inject it dynamically
            if (!window.mapInstance.getSource(sourceId)) {
                window.mapInstance.addSource(sourceId, {
                    'type': server.type,
                    'tiles': [server.url],
                    'tileSize': 256,
                    ...(server.type === 'raster-dem' ? { 'encoding': 'terrarium', 'maxzoom': 14 } : {})
                });

                if (server.type === 'raster') {
                    // Place new map layers below the drawn boundary and flight path
                    window.mapInstance.addLayer({
                        'id': layerId,
                        'type': 'raster',
                        'source': sourceId,
                        'layout': { 'visibility': 'visible' }
                    }, 'boundary-fill');
                }
            } else if (server.type === 'raster' && window.mapInstance.getLayer(layerId)) {
                // If it exists, just ensure it's visible
                window.mapInstance.setLayoutProperty(layerId, 'visibility', 'visible');
            }

            // Track the active 3D elevation model
            if (server.type === 'raster-dem') {
                activeDem = sourceId;
            }
        } else {
            // Turn off the layer if user disabled it
            if (server.type === 'raster' && window.mapInstance.getLayer(layerId)) {
                window.mapInstance.setLayoutProperty(layerId, 'visibility', 'none');
            }
        }
    });

    // Toggle 3D mesh based on active setting
    if (activeDem) {
        window.mapInstance.setTerrain({ 'source': activeDem, 'exaggeration': 1.5 });
    } else {
        window.mapInstance.setTerrain(null);
    }
};

window.updateUAV = function (lng, lat, alt_msl, agl) {
    if (!agl) agl = 30;
    if (window.mapInstance) {
        if (window.mapInstance.getSource('uav-shadow')) window.mapInstance.getSource('uav-shadow').setData({ 'type': 'Point', 'coordinates': [lng, lat] });
        if (window.mapInstance.getSource('uav-marker')) {
            const radiusDegLat = 3.0 / 111111.0;
            const radiusDegLng = 3.0 / (111111.0 * Math.cos(lat * Math.PI / 180));
            const circleCoords = [];
            for (let i = 0; i < 32; i++) {
                const theta = (i / 32) * (2 * Math.PI);
                circleCoords.push([lng + (radiusDegLng * Math.cos(theta)), lat + (radiusDegLat * Math.sin(theta))]);
            }
            circleCoords.push(circleCoords[0]);
            window.mapInstance.getSource('uav-marker').setData({
                'type': 'Feature',
                'properties': { 'base': agl - 0.5, 'height': agl + 0.5 },
                'geometry': { 'type': 'Polygon', 'coordinates': [circleCoords] }
            });
        }
    }
};

window.updatePath = function (geojson) {
    if (window.mapInstance && window.mapInstance.getSource('path')) window.mapInstance.getSource('path').setData(geojson);
};

window.updateBoundary = function (geojson) {
    if (window.mapInstance && window.mapInstance.getSource('boundary')) window.mapInstance.getSource('boundary').setData(geojson);
};