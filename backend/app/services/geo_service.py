import math
from typing import List, Tuple

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees) in meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    a = max(0.0,min(1.0,a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def distance_point_to_segment_meters(
    p_lat: float, p_lon: float,
    a_lat: float, a_lon: float,
    b_lat: float, b_lon: float
) -> float:
    """
    Computes approximate distance in meters from point P to line segment AB.
    """
    # Approximate flat-earth projection for local distances
    mid_lat = math.radians((a_lat + b_lat) / 2.0)
    kx = 111320.0 * math.cos(mid_lat)
    ky = 110540.0

    px, py = p_lon * kx, p_lat * ky
    ax, ay = a_lon * kx, a_lat * ky
    bx, by = b_lon * kx, b_lat * ky

    dx = bx - ax
    dy = by - ay

    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    # Project point P onto segment AB, clamped to [0, 1]
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy

    return math.hypot(px - proj_x, py - proj_y)

def min_distance_to_route_meters(p_lat: float, p_lon: float, waypoints: List[Tuple[float, float]]) -> float:
    """
    Finds minimum distance from a point to a polyline route.
    """
    if not waypoints:
        return float("inf")
    if len(waypoints) == 1:
        return haversine_distance_meters(p_lat, p_lon, waypoints[0][0], waypoints[0][1])

    min_dist = float("inf")
    for i in range(len(waypoints) - 1):
        a_lat, a_lon = waypoints[i]
        b_lat, b_lon = waypoints[i + 1]
        dist = distance_point_to_segment_meters(p_lat, p_lon, a_lat, a_lon, b_lat, b_lon)
        if dist < min_dist:
            min_dist = dist
    return min_dist


def longitude_delta(value):
    return (value+180)%360-180


def route_projection(p_lat,p_lon,waypoints):
    """Nearest polyline point: lateral distance and progress from origin.

    Equirectangular projection per segment suits short road segments; progress
    uses geodesic segment lengths, including dateline crossings.
    """
    nearest,progress,travelled=float('inf'),0.0,0.0
    for (a_lat,a_lon),(b_lat,b_lon) in zip(waypoints,waypoints[1:]):
        mid_lat=math.radians((a_lat+b_lat)/2)
        kx=math.pi/180*6371000*math.cos(mid_lat); ky=math.pi/180*6371000
        dx,dy=longitude_delta(b_lon-a_lon)*kx,(b_lat-a_lat)*ky
        px,py=longitude_delta(p_lon-a_lon)*kx,(p_lat-a_lat)*ky
        length_sq=dx*dx+dy*dy
        fraction=max(0.0,min(1.0,(px*dx+py*dy)/length_sq)) if length_sq else 0.0
        distance=math.hypot(px-fraction*dx,py-fraction*dy)
        length=haversine_distance_meters(a_lat,a_lon,b_lat,b_lon)
        if distance<nearest-1e-6: nearest,progress=distance,travelled+fraction*length
        travelled+=length
    return nearest,progress


def radius_bounds(latitude,longitude,radius):
    angular=radius/6371000; delta=math.degrees(angular)
    low,high=max(-90,latitude-delta),min(90,latitude+delta)
    if low==-90 or high==90: return low,high,[(-180,180)]
    lon_delta=math.degrees(math.asin(min(1,math.sin(angular)/math.cos(math.radians(latitude)))))
    left,right=longitude-lon_delta,longitude+lon_delta
    if left < -180: ranges=[(-180,right),(left+360,180)]
    elif right > 180: ranges=[(left,180),(-180,right-360)]
    else: ranges=[(left,right)]
    return low,high,ranges
