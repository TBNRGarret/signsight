"""One explicit read-only smoke check of configured OSRM and places providers."""
from backend.app.core.settings import Settings
from backend.app.schemas.navigation import LatLng
from backend.app.services.routing_service import RoutingProvider, make_place_provider


def main():
    settings = Settings.from_env()
    route = RoutingProvider(settings.routing_base_url, settings.provider_user_agent)
    points, distance, duration = route.route(LatLng(latitude=10.7769, longitude=106.7009),
                                            LatLng(latitude=10.7829, longitude=106.6939))
    print(f'OSRM: {len(points)} geometry points, {distance:.0f} m, {duration:.0f} s', flush=True)
    provider = make_place_provider(settings)
    places = provider.search('Ho Chi Minh City')
    print(f'{provider.name}: {len(places)} validated places', flush=True)


if __name__ == '__main__':
    main()
