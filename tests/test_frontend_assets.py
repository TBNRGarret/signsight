"""MapLibre assets are served locally; no CDN is required for the renderer."""
import base64
import hashlib
import re

def test_maplibre_assets_work_without_a_third_party_cdn(client):
    for page in ('index.html', 'observations.html'):
        html = client.get('/web/' + page).text
        for name in ('maplibre-gl.css', 'maplibre-gl.js'):
            match = re.search(r'(?:src|href)="vendor/maplibre/' + re.escape(name) + r'[^"]*" integrity="sha256-([^"]+)"', html)
            assert match, f'{page}: missing local asset integrity for {name}'
            response = client.get('/web/vendor/maplibre/' + name)
            assert response.status_code == 200
            assert base64.b64encode(hashlib.sha256(response.content).digest()).decode() == match[1]
        assert 'vendor/leaflet/' not in html

def test_maplibre_license_is_served(client):
    response = client.get('/web/vendor/maplibre/LICENSE.txt')
    assert response.status_code == 200
    assert 'Redistribution and use' in response.text


def test_maplibre_worker_is_served_with_javascript_mime(client):
    response = client.get("/web/vendor/maplibre/maplibre-gl-worker.mjs")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
