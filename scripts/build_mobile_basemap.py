"""Build SignSight's day/night vector styles from a reviewed OpenFreeMap Liberty JSON.

Usage: python scripts/build_mobile_basemap.py path/to/liberty.json
No tiles, fonts or imagery are downloaded or redistributed by this script.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ORIGIN = 'https://tiles.openfreemap.org/styles/liberty'
PALETTES = {
    'day': dict(land='#f7f5ef', residential='#f1eee5', park='#c9e6b3', wood='#b9d99c',
                grass='#d4e9bd', water='#97cceb', building='#e7e1d3', building_edge='#d9d3c7',
                motorway='#f6bf56', primary='#f9d984', secondary='#ffe9af', street='#ffffff',
                casing='#d1c8ad', path='#d9cfb8', rail='#a3aaa1', text='#3e4b45',
                muted='#59665c', water_text='#234c68', halo='#ffffff', school='#f4ebd6',
                hospital='#f6e4df', air='#deded6', boundary='#b3b5a8'),
    'night': dict(land='#172523', residential='#1c302b', park='#254a37', wood='#1e402f',
                  grass='#2b4b38', water='#1f465c', building='#293e37', building_edge='#31493c',
                  motorway='#be9245', primary='#b19a63', secondary='#73816b', street='#485e58',
                  casing='#192b26', path='#5c6653', rail='#64776b', text='#e4ebdf',
                  muted='#bfccbb', water_text='#c3e0f2', halo='#15231f', school='#3c3b2c',
                  hospital='#43322f', air='#34403a', boundary='#67796c'),
}


def style_for(original, mode, digest):
    style = deepcopy(original)
    p = PALETTES[mode]
    style['name'] = 'SignSight Streets ' + mode.title()
    style['metadata'] = {
        'signsight:origin': ORIGIN,
        'signsight:source-sha256': digest,
        'signsight:design': 'Modified OSM Liberty / OSM Bright; see assets/maps/LICENSE.txt',
    }
    style['sources'] = {'openmaptiles': style['sources']['openmaptiles']}
    style['sources']['openmaptiles']['attribution'] = (
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · '
        '<a href="https://openmaptiles.org/">OpenMapTiles</a> · '
        '<a href="https://github.com/maputnik/osm-liberty">Liberty</a>')
    style['layers'] = [l for l in style['layers']
                       if l['type'] not in ('raster', 'fill-extrusion')]
    fills = {'park': 'park', 'landuse_residential': 'residential', 'landcover_wood': 'wood',
             'landcover_grass': 'grass', 'landcover_wetland': 'grass', 'landuse_pitch': 'park',
             'landuse_track': 'school', 'landuse_cemetery': 'park', 'landuse_hospital': 'hospital',
             'landuse_school': 'school', 'water': 'water', 'aeroway_fill': 'air',
             'building': 'building', 'road_area_pattern': 'street'}
    names = ['coalesce', ['get', 'name:vi'], ['get', 'name'], ['get', 'name:latin']]
    for layer in style['layers']:
        ident, kind = layer['id'], layer['type']
        paint = layer.setdefault('paint', {})
        if kind == 'background':
            paint['background-color'] = p['land']
        elif ident in fills:
            paint['fill-color'] = p[fills[ident]]
            paint.pop('fill-pattern', None)
            if ident == 'park':
                paint['fill-opacity'] = 1
                paint['fill-outline-color'] = p['park']
            if ident == 'building':
                layer.pop('maxzoom', None)
                paint['fill-outline-color'] = p['building_edge']
                paint['fill-opacity'] = ['interpolate', ['linear'], ['zoom'], 13, .3, 15, .65, 17, .85]
        elif kind == 'fill':
            paint['fill-color'] = p['residential']
        elif kind == 'line':
            if ident.startswith('waterway'):
                color = p['water']
            elif ident.startswith('park'):
                color = p['park']
            elif ident.startswith('boundary'):
                color = p['boundary']
            elif ident.startswith('aeroway'):
                color = p['air']
            elif ident.endswith('_casing'):
                color = p['casing']
            elif 'rail' in ident:
                color = p['rail']
            elif 'motorway' in ident:
                color = p['motorway']
            elif 'trunk_primary' in ident:
                color = p['primary']
            elif 'secondary_tertiary' in ident:
                color = p['secondary']
            elif 'path' in ident:
                color = p['path']
            else:
                color = p['street']
            paint['line-color'] = color
        if kind == 'symbol' and 'text-field' in layer.get('layout', {}):
            layout = layer['layout']
            if 'name' in json.dumps(layout['text-field']):
                layout['text-field'] = names
            if 'Italic' in json.dumps(layout.get('text-font')):
                layout['text-font'] = ['Noto Sans Regular']
            paint.update({'text-color': p['text'], 'text-halo-color': p['halo'],
                          'text-halo-width': 1.5, 'text-halo-blur': .5})
            if ident.startswith('water'):
                paint['text-color'] = p['water_text']
            if ident.startswith('poi'):
                paint['text-color'] = p['muted']
                layout['text-size'] = 12
                layout['text-padding'] = 4
                layout['icon-padding'] = 4
            if ident == 'poi_transit':
                layer['minzoom'] = 16
            if ident == 'label_other':
                layout['text-transform'] = 'none'
                layout['text-size'] = ['interpolate', ['linear'], ['zoom'], 12, 10, 16, 12]
                paint['text-color'] = p['muted']
    return style


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    original = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    target = Path(__file__).resolve().parents[1] / 'mobile' / 'assets' / 'maps'
    target.mkdir(parents=True, exist_ok=True)
    for mode in PALETTES:
        (target / f'signsight-{mode}.json').write_text(
            json.dumps(style_for(original, mode, digest), ensure_ascii=False, separators=(',', ':')) + '\n',
            encoding='utf-8')
    print('Generated SignSight day/night styles from Liberty SHA-256 ' + digest)


if __name__ == '__main__':
    main()
