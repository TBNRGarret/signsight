from fastapi import APIRouter
from backend.app.api.v1.endpoints import accounts, auth, signs, navigation, revalidation, images, maps, reports, duplicates

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(accounts.router, tags=["Accounts"])
api_router.include_router(images.router, tags=["Images & Observations"])
api_router.include_router(maps.router, tags=['Map & Nearby'])
api_router.include_router(reports.router, tags=['Reports & Policy'])
api_router.include_router(duplicates.router,tags=['Duplicate review'])
api_router.include_router(signs.router, prefix="/signs", tags=["Traffic Signs"])
api_router.include_router(navigation.router, prefix="/navigation", tags=["Navigation"])
api_router.include_router(revalidation.router, prefix="/revalidation", tags=["Lifecycle & Revalidation"])
