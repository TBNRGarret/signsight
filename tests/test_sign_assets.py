"""Approved non-square road signs must keep their geometry in Flutter PNGs."""
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def test_rectangular_sign_is_letterboxed_not_stretched_to_a_circle_sized_square():
    svg = ET.parse(ROOT/'frontend/shared/signs/road_reserved_for_cars.svg').getroot()
    _, _, width, height = map(float, svg.attrib['viewBox'].replace(',', ' ').split())
    with Image.open(ROOT/'mobile/assets/signs/road_reserved_for_cars.png') as image:
        x1, y1, x2, y2 = image.getchannel('A').getbbox()
        assert abs((x2-x1)/(y2-y1) - width/height) < .04
