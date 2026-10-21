"""The map must receive Leaflet styling from the same server as the page."""
import base64
import hashlib
import re


def test_leaflet_assets_work_without_a_third_party_cdn(client):
    html = client.get('/web/index.html').text
    for name, expected in (
        ('leaflet.css', 'p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY='),
        ('leaflet.js', '20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo='),
    ):
        assert f'vendor/leaflet/{name}' in html
        response = client.get(f'/web/vendor/leaflet/{name}')
        assert response.status_code == 200
        assert base64.b64encode(hashlib.sha256(response.content).digest()).decode() == expected
    assert 'unpkg.com/leaflet' not in html


def test_leaflet_css_images_and_license_are_served(client):
    css = client.get('/web/vendor/leaflet/leaflet.css')
    assert css.status_code == 200
    images = re.findall(r'url\((images/[^)]+)\)', css.text)
    assert images
    for image in images:
        response = client.get(f'/web/vendor/leaflet/{image}')
        assert response.status_code == 200
        assert response.content.startswith(b'\x89PNG\r\n\x1a\n')
    license_response = client.get('/web/vendor/leaflet/LICENSE')
    assert license_response.status_code == 200
    assert 'Redistribution and use' in license_response.text
