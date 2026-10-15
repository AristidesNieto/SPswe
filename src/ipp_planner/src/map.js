console.log("[map.js] File loaded successfully! Waiting for clicks...");
window.waypointQueue = [];
window.historicalHotspotsVisible = true;

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
        zoom: 15, pitch: 0, maxPitch: 70
    });

    window.mapInstance.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showZoom: true, showCompass: true }), 'bottom-right');

    window.mapInstance.on('load', () => {
        window.mapInstance.getCanvas().style.cursor = 'crosshair';

        try {
            const historicalIncidents = [
                [-0.0013, -0.0007, 0.95], [-0.0010, -0.0004, 0.86],
                [-0.0008, -0.0008, 0.82], [-0.0005, -0.0005, 0.94],
                [-0.0002, -0.0007, 0.75], [0.0001, -0.0004, 0.88],
                [0.0003, -0.0008, 0.72], [0.0006, -0.0005, 0.83],
                [0.0008, -0.0001, 0.92], [0.0011, 0.0002, 0.78],
                [0.0005, 0.0001, 0.76], [0.0002, 0.0004, 0.90],
                [-0.0002, 0.0002, 0.68], [-0.0006, 0.0005, 0.84],
                [-0.0009, 0.0008, 0.74], [0.0009, 0.0007, 0.65],
                [0.0013, 0.0005, 0.72], [-0.0013, 0.0002, 0.62]
            ].map(([offsetLng, offsetLat, intensity]) => ({
                type: 'Feature',
                properties: { intensity },
                geometry: {
                    type: 'Point',
                    coordinates: [
                        window.MAP_CONFIG.lng + offsetLng,
                        window.MAP_CONFIG.lat + offsetLat
                    ]
                }
            }));
            window.mapInstance.addSource('historical-incidents', {
                type: 'geojson',
                data: { type: 'FeatureCollection', features: historicalIncidents }
            });
            window.mapInstance.addLayer({
                id: 'historical-hotspots',
                type: 'circle',
                source: 'historical-incidents',
                layout: { visibility: window.historicalHotspotsVisible ? 'visible' : 'none' },
                paint: {
                    'circle-radius': ['interpolate', ['linear'], ['get', 'intensity'], 0.6, 22, 1, 32],
                    'circle-color': [
                        'interpolate', ['linear'], ['get', 'intensity'],
                        0.6, '#a3e635',
                        0.75, '#facc15',
                        0.88, '#fb923c',
                        1, '#dc2626'
                    ],
                    'circle-blur': 0.8,
                    'circle-opacity': 0.8
                }
            });

            // --- Boundary Layers ---
            window.mapInstance.addSource('boundary', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
            window.mapInstance.addLayer({ 'id': 'boundary-fill', 'type': 'fill', 'source': 'boundary', 'filter': ['==', '$type', 'Polygon'], 'paint': { 'fill-color': '#facc15', 'fill-opacity': 0.3 } });
            window.mapInstance.addLayer({ 'id': 'boundary-line', 'type': 'line', 'source': 'boundary', 'filter': ['any', ['==', '$type', 'Polygon'], ['==', '$type', 'LineString']], 'paint': { 'line-color': '#ca8a04', 'line-width': 2, 'line-dasharray': [2, 2] } });
            window.mapInstance.addLayer({ 'id': 'boundary-points', 'type': 'circle', 'source': 'boundary', 'filter': ['==', '$type', 'Point'], 'paint': { 'circle-radius': 10, 'circle-color': '#facc15', 'circle-stroke-width': 2, 'circle-stroke-color': '#ca8a04' } });
            window.mapInstance.addLayer({ 'id': 'boundary-labels', 'type': 'symbol', 'source': 'boundary', 'filter': ['==', '$type', 'Point'], 'layout': { 'text-field': ['get', 'label'], 'text-size': 12, 'text-allow-overlap': true }, 'paint': { 'text-color': '#000000' } });

            // --- Path Layers (Ground Track, Points, and Labels) ---
            window.mapInstance.addSource('path', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
            window.mapInstance.addLayer({ 'id': 'path-line', 'type': 'line', 'source': 'path', 'filter': ['==', '$type', 'LineString'], 'paint': { 'line-color': '#0f766e', 'line-width': 4 } });
            window.mapInstance.addLayer({ 'id': 'path-points', 'type': 'circle', 'source': 'path', 'filter': ['==', '$type', 'Point'], 'paint': { 'circle-radius': 7, 'circle-color': '#0f766e', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' } });
            window.mapInstance.addLayer({ 'id': 'path-labels', 'type': 'symbol', 'source': 'path', 'filter': ['==', '$type', 'Point'], 'layout': { 'text-field': ['get', 'label'], 'text-size': 12, 'text-anchor': 'left', 'text-offset': [0.8, 0], 'text-allow-overlap': true }, 'paint': { 'text-color': '#064e3b', 'text-halo-color': '#ffffff', 'text-halo-width': 2 } });

        } catch (e) {
            console.error("MAP LAYER CRASH:", e);
        }

        setTimeout(() => window.mapInstance.resize(), 100);
    });

    window.mapInstance.on('click', (e) => {
        window.waypointQueue.push([e.lngLat.lng, e.lngLat.lat]);
    });
};

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
            if (!window.mapInstance.getSource(sourceId)) {
                window.mapInstance.addSource(sourceId, {
                    'type': server.type,
                    'tiles': [server.url],
                    'tileSize': 256,
                    ...(server.type === 'raster-dem' ? { 'encoding': 'terrarium', 'maxzoom': 14 } : {})
                });
                if (server.type === 'raster') {
                    const overlayLayer = window.mapInstance.getLayer('historical-hotspots')
                        ? 'historical-hotspots'
                        : window.mapInstance.getLayer('boundary-fill')
                            ? 'boundary-fill'
                            : undefined;
                    const rasterLayer = { 'id': layerId, 'type': 'raster', 'source': sourceId, 'layout': { 'visibility': 'visible' } };
                    if (overlayLayer) window.mapInstance.addLayer(rasterLayer, overlayLayer);
                    else window.mapInstance.addLayer(rasterLayer);
                }
            } else if (server.type === 'raster' && window.mapInstance.getLayer(layerId)) {
                window.mapInstance.setLayoutProperty(layerId, 'visibility', 'visible');
            }
            if (server.type === 'raster-dem') activeDem = sourceId;
        } else {
            if (server.type === 'raster' && window.mapInstance.getLayer(layerId)) window.mapInstance.setLayoutProperty(layerId, 'visibility', 'none');
        }
    });
    if (activeDem) window.mapInstance.setTerrain({ 'source': activeDem, 'exaggeration': 1.5 });
    else window.mapInstance.setTerrain(null);
};

window.updatePath = function (geojson) {
    try {
        if (window.mapInstance && window.mapInstance.getSource('path')) window.mapInstance.getSource('path').setData(geojson);
    } catch (e) {
        console.error("PATH UPDATE ERROR:", e, geojson);
    }
};

window.updateBoundary = function (geojson) {
    try {
        if (window.mapInstance && window.mapInstance.getSource('boundary')) window.mapInstance.getSource('boundary').setData(geojson);
    } catch (e) {
        console.error("BOUNDARY UPDATE ERROR:", e, geojson);
    }
};

window.setHistoricalHotspotsVisible = function (visible) {
    window.historicalHotspotsVisible = visible;
    if (!window.mapInstance || !window.mapInstance.getLayer('historical-hotspots')) return;
    window.mapInstance.setLayoutProperty(
        'historical-hotspots',
        'visibility',
        visible ? 'visible' : 'none'
    );
};