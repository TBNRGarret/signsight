from fastapi import APIRouter,Depends,Request
from sqlalchemy.orm import Session
from backend.app.core.security import get_current_user
from backend.app.db.database import get_db
from backend.app.schemas.navigation import NavigationQuery,NavigationResponse,RouteRequest,RouteResponse
from backend.app.services.lifecycle_service import check_and_update_lifecycle_status
from backend.app.services.map_service import route_signs

router=APIRouter()


@router.post('/route-signs',response_model=NavigationResponse)
def get_signs_along_route(payload:NavigationQuery,db:Session=Depends(get_db)):
    check_and_update_lifecycle_status(db)
    matched=route_signs(db,payload.waypoints,payload.buffer_meters)
    return NavigationResponse(route_points_count=len(payload.waypoints),buffer_meters=payload.buffer_meters,total_signs=len(matched),
        active_signs_count=sum(item.sign.status=='active' and not item.sign.is_uncertain for item in matched),
        uncertain_signs_count=sum(item.sign.is_uncertain for item in matched),expired_signs_count=sum(item.sign.status=='expired' for item in matched),signs=matched)


@router.post('/route',response_model=RouteResponse)
def driving_route(payload:RouteRequest,request:Request,user=Depends(get_current_user),db:Session=Depends(get_db)):
    request.app.state.auth_limiter.check(request,'routing',20)
    db.rollback()
    geometry,distance,duration=request.app.state.routing_provider.route(payload.origin,payload.destination)
    check_and_update_lifecycle_status(db)
    return RouteResponse(geometry=geometry,distance_meters=distance,duration_seconds=duration,
                         buffer_meters=payload.buffer_meters,signs=route_signs(db,geometry,payload.buffer_meters))
