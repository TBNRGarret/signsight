from typing import List
from pydantic import BaseModel,ConfigDict,Field
from backend.app.schemas.sign import SignRecordResponse

class LatLng(BaseModel):
    model_config=ConfigDict(extra='forbid')
    latitude: float=Field(ge=-90,le=90,allow_inf_nan=False)
    longitude: float=Field(ge=-180,le=180,allow_inf_nan=False)

class NavigationQuery(BaseModel):
    model_config=ConfigDict(extra='forbid')
    waypoints: List[LatLng]=Field(min_length=2,max_length=20000)
    buffer_meters: float = Field(35.0,ge=20,le=100,allow_inf_nan=False)

class NavigationSignItem(BaseModel):
    sign: SignRecordResponse
    distance_to_route_meters: float
    distance_along_route_meters: float = 0

class NavigationResponse(BaseModel):
    route_points_count: int
    buffer_meters: float
    total_signs: int
    active_signs_count: int
    uncertain_signs_count: int
    expired_signs_count: int
    signs: List[NavigationSignItem]


class RouteRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    origin:LatLng
    destination:LatLng
    buffer_meters:float=Field(50,ge=20,le=100,allow_inf_nan=False)


class RouteResponse(BaseModel):
    provider:str='osrm'
    geometry:List[LatLng]
    distance_meters:float
    duration_seconds:float
    buffer_meters:float
    signs:List[NavigationSignItem]
