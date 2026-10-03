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

        // --- Path Layers (Ground Track, Points, and Labels) ---
        window.mapInstance.addSource('path', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({ 'id': 'path-line', 'type': 'line', 'source': 'path', 'filter': ['==', '$type', 'LineString'], 'paint': { 'line-color': '#3b82f6', 'line-width': 3 } });

        // NEW: Draw waypoints as circles
        window.mapInstance.addLayer({
            'id': 'path-points',
            'type': 'circle',
            'source': 'path',
            'filter': ['==', '$type', 'Point'],
            'paint': { 'circle-radius': 6, 'circle-color': '#3b82f6', 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' }
        });

        // NEW: Draw numbered labels next to path points
        window.mapInstance.addLayer({
            'id': 'path-labels',
            'type': 'symbol',
            'source': 'path',
            'filter': ['==', '$type', 'Point'],
            'layout': {
                'text-field': ['get', 'label'],
                'text-font': ['Open Sans Regular'],
                'text-size': 12,
                'text-anchor': 'left',
                'text-offset': [0.8, 0],
                'text-allow-overlap': true
            },
            'paint': { 'text-color': '#000000', 'text-halo-color': '#ffffff', 'text-halo-width': 2 }
        });

        // --- UAV Shadow & True 3D Marker ---
        window.mapInstance.addSource('uav-shadow', { 'type': 'geojson', 'data': { 'type': 'FeatureCollection', 'features': [] } });
        window.mapInstance.addLayer({ 'id': 'uav-shadow-layer', 'type': 'fill', 'source': 'uav-shadow', 'paint': { 'fill-color': '#000000', 'fill-opacity': 0.5 } });

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
                    window.mapInstance.addLayer({ 'id': layerId, 'type': 'raster', 'source': sourceId, 'layout': { 'visibility': 'visible' } }, 'boundary-fill');
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

window.updateUAV = function (lng, lat, alt_msl, agl, uavSize) {
    if (!agl) agl = 30;
    if (!uavSize) uavSize = 3.0;

    if (window.mapInstance) {
        const currentZoom = window.mapInstance.getZoom();
        const metersPerPixel = (156543.03392 * Math.cos(lat * Math.PI / 180)) / Math.pow(2, currentZoom);

        const radiusMeters = (uavSize / 2.0) * metersPerPixel;
        const radiusDegLat = radiusMeters / 111111.0;
        const radiusDegLng = radiusMeters / (111111.0 * Math.cos(lat * Math.PI / 180));

        const circleCoords = [];
        for (let i = 0; i < 32; i++) {
            const theta = (i / 32) * (2 * Math.PI);
            circleCoords.push([lng + (radiusDegLng * Math.cos(theta)), lat + (radiusDegLat * Math.sin(theta))]);
        }
        circleCoords.push(circleCoords[0]);

        if (window.mapInstance.getSource('uav-shadow')) {
            window.mapInstance.getSource('uav-shadow').setData({ 'type': 'Feature', 'geometry': { 'type': 'Polygon', 'coordinates': [circleCoords] } });
        }
        if (window.mapInstance.getSource('uav-marker')) {
            const thickness = Math.min(0.5, radiusMeters / 2.0);
            window.mapInstance.getSource('uav-marker').setData({
                'type': 'Feature',
                'properties': { 'base': agl - thickness, 'height': agl + thickness },
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