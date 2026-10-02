console.log("[map.js] File loaded successfully!");

window.waypointQueue = [];

window.initMap = function () {
    // 1. Ensure the div actually exists on the screen
    if (!document.getElementById('map')) {
        console.log("[map.js] Waiting for Vue.js to draw the #map div...");
        setTimeout(window.initMap, 50);
        return;
    }

    // 2. FIXED: Check for mapInstance to avoid colliding with the HTML id="map"
    if (window.mapInstance) {
        console.log("[map.js] Map already initialized, skipping.");
        return;
    }

    console.log("[map.js] Initializing MapLibre...");

    window.mapInstance = new maplibregl.Map({
        container: 'map',
        style: {
            'version': 8,
            'sources': {
                'osm': {
                    'type': 'raster',
                    'tiles': ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
                    'tileSize': 256,
                    'attribution': '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                }
            },
            'layers': [{ 'id': 'osm', 'type': 'raster', 'source': 'osm' }]
        },
        center: [window.MAP_CONFIG.lng, window.MAP_CONFIG.lat],
        zoom: 15,
        pitch: 55
    });

    window.mapInstance.on('load', () => {
        console.log("[map.js] MapLibre finished loading tiles.");

        window.mapInstance.addSource('path', {
            'type': 'geojson',
            'data': { 'type': 'FeatureCollection', 'features': [] }
        });

        window.mapInstance.addLayer({
            'id': 'path-line',
            'type': 'line',
            'source': 'path',
            'paint': { 'line-color': '#3b82f6', 'line-width': 3, 'line-dasharray': [2, 2] }
        });

        window.mapInstance.addLayer({
            'id': 'path-points',
            'type': 'circle',
            'source': 'path',
            'paint': { 'circle-radius': 5, 'circle-color': '#3b82f6', 'circle-stroke-width': 2, 'circle-stroke-color': '#fff' }
        });

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
        console.log("[map.js] Map clicked at:", e.lngLat);
        window.waypointQueue.push([e.lngLat.lng, e.lngLat.lat]);
    });
};

window.updateUAV = function (lng, lat) {
    if (window.mapInstance && window.mapInstance.getSource('uav')) {
        window.mapInstance.getSource('uav').setData({ 'type': 'Point', 'coordinates': [lng, lat] });
    }
};

window.updatePath = function (geojson) {
    if (window.mapInstance && window.mapInstance.getSource('path')) {
        window.mapInstance.getSource('path').setData(geojson);
    }
};