import math
from fastapi import HTTPException
from sqlalchemy import or_
from backend.app.db.models import SignRecord
from backend.app.schemas.sign import SignRecordResponse
from backend.app.schemas.navigation import NavigationSignItem
from backend.app.services.geo_service import radius_bounds,haversine_distance_meters,route_projection

VISIBLE=('active','pending_revalidation','expired')


def nearby_signs(db,latitude,longitude,radius):
    low,high,ranges=radius_bounds(latitude,longitude,radius)
    candidates=db.query(SignRecord).filter(SignRecord.status.in_(VISIBLE),SignRecord.latitude.between(low,high),
        or_(*[SignRecord.longitude.between(left,right) for left,right in ranges])).all()
    matched=[]
    for record in candidates:
        distance=haversine_distance_meters(latitude,longitude,record.latitude,record.longitude)
        if distance<=radius: matched.append({'sign':SignRecordResponse.model_validate(record),'distance_meters':round(distance,1)})
    return sorted(matched,key=lambda row:(row['distance_meters'],row['sign'].id))


def route_signs(db,points,buffer):
    coordinates=[(point.latitude,point.longitude) for point in points]
    latitudes,longitudes=[p[0] for p in coordinates],[p[1] for p in coordinates]
    pad=math.degrees(buffer/6371000)*1.01
    lon_pad=pad/max(.001,math.cos(math.radians(max(abs(min(latitudes)),abs(max(latitudes))))))
    query=db.query(SignRecord).filter(SignRecord.status.in_(VISIBLE),SignRecord.latitude.between(min(latitudes)-pad,max(latitudes)+pad))
    if max(longitudes)-min(longitudes)<180 and min(longitudes)-lon_pad>=-180 and max(longitudes)+lon_pad<=180:
        query=query.filter(SignRecord.longitude.between(min(longitudes)-lon_pad,max(longitudes)+lon_pad))
    candidates=query.limit(5001).all()
    if len(candidates)>5000: raise HTTPException(413,'Route area contains too many signs; use a shorter route')
    matched=[]
    for record in candidates:
        lateral,progress=route_projection(record.latitude,record.longitude,coordinates)
        if lateral<=buffer:
            matched.append(NavigationSignItem(sign=SignRecordResponse.model_validate(record),distance_to_route_meters=round(lateral,1),distance_along_route_meters=round(progress,1)))
    return sorted(matched,key=lambda item:(item.distance_along_route_meters,item.distance_to_route_meters,item.sign.id))
