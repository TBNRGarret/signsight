"""Explicit provider adapters; never invent a route after provider failure."""
from collections import OrderedDict
import math
import re
from threading import Lock
from time import monotonic,sleep
import unicodedata
import httpx
from fastapi import HTTPException
from backend.app.schemas.navigation import LatLng


def fetch_json(url,params,agent,transport=None):
    try:
        with httpx.Client(timeout=12,follow_redirects=False,headers={'User-Agent':agent},transport=transport) as client:
            with client.stream('GET',url,params=params) as response:
                response.raise_for_status(); content=bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content)>4*1024*1024: raise HTTPException(502,'Provider response exceeds size limit')
        import json
        return json.loads(content)
    except (httpx.HTTPError,ValueError,TypeError):
        raise HTTPException(502,'Map provider unavailable; please retry later') from None


class RoutingProvider:
    def __init__(self,base_url,agent='SignSight-Research/1.2',transport=None):
        self.base_url,self.agent,self.transport=base_url.rstrip('/'),agent,transport

    def route(self,origin,destination):
        coordinates=f'{origin.longitude},{origin.latitude};{destination.longitude},{destination.latitude}'
        body=fetch_json(self.base_url+'/route/v1/driving/'+coordinates,
                        {'overview':'full','geometries':'geojson','steps':'false','alternatives':'false'},self.agent,self.transport)
        try:
            if body.get('code')!='Ok': raise ValueError('No route')
            route=body['routes'][0]; geometry=route['geometry']
            if geometry['type']!='LineString' or not 2<=len(geometry['coordinates'])<=20000: raise ValueError('Unsupported geometry')
            points=[LatLng(latitude=pair[1],longitude=pair[0]) for pair in geometry['coordinates'] if len(pair)==2]
            if len(points)!=len(geometry['coordinates']): raise ValueError('Invalid coordinates')
            distance,duration=float(route['distance']),float(route['duration'])
            if not all(math.isfinite(value) and value>=0 for value in (distance,duration)): raise ValueError('Invalid route statistics')
            return points,distance,duration
        except (KeyError,IndexError,ValueError,TypeError,AttributeError):
            raise HTTPException(502,'No valid driving route returned by the provider') from None


HCM_VIEWBOX='106.35,11.15,107.05,10.35'
PLACE_CANDIDATE_LIMIT=20
PLACE_RESULT_LIMIT=5
HCM_REGION_NAMES={
    'ho chi minh','ho chi minh city','thanh pho ho chi minh',
    'tp ho chi minh','tp hcm','tphcm','hcm','sai gon','saigon',
}
PLACE_REGION_FIELDS=('city','municipality','county','state','province','region')


def normalize_region(value):
    text=unicodedata.normalize('NFKD',str(value)).casefold()
    text=''.join(character for character in text if not unicodedata.combining(character))
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',text).split())


def is_hcm_place(item):
    """Use administrative address fields, never a matching business/road name."""
    address=item.get('address') or {}
    if not isinstance(address,dict): raise ValueError('Invalid place address')
    country=str(address.get('country_code','')).casefold()
    if country and country!='vn': return False
    regions=[address[field] for field in PLACE_REGION_FIELDS if address.get(field)]
    if regions:
        return any(normalize_region(region) in HCM_REGION_NAMES for region in regions)
    # Some configured providers omit addressdetails; match complete address segments.
    return any(normalize_region(region) in HCM_REGION_NAMES
               for region in str(item['display_name']).split(',')[1:])


class PlaceProvider:
    """Manual searches, bounded cache, at most one upstream request/second per process."""
    name = 'nominatim'
    def __init__(self,base_url,agent,transport=None):
        self.base_url,self.agent,self.transport=base_url.rstrip('/'),agent,transport
        self.cache=OrderedDict(); self.lock=Lock(); self.last_request=0.0

    def _candidates(self, query):
        # Bias relevance without restricting explicit destinations outside HCM.
        return fetch_json(self.base_url+'/search',{
            'q':query,'format':'jsonv2','limit':PLACE_CANDIDATE_LIMIT,
            'viewbox':HCM_VIEWBOX,'bounded':0,'addressdetails':1,'accept-language':'vi,en',
        },self.agent,self.transport)

    def search(self,query):
        key=' '.join(query.split()).casefold()
        with self.lock:
            now=monotonic(); cached=self.cache.get(key)
            if cached and now-cached[0]<3600:
                self.cache.move_to_end(key); return cached[1]
            delay=1-(now-self.last_request)
            if delay>0: sleep(delay)
            self.last_request=monotonic()
            body=self._candidates(query)
            try:
                if not isinstance(body,list) or len(body)>PLACE_CANDIDATE_LIMIT: raise ValueError('Invalid places')
                places=[]
                for item in body:
                    point=LatLng(latitude=float(item['lat']),longitude=float(item['lon']))
                    place={'id':str(item['place_id']),'name':str(item['display_name'])[:500],**point.model_dump()}
                    places.append((not is_hcm_place(item),place))
                # Stable sort preserves provider relevance within each group, then cap the UI page.
                places=[place for _,place in sorted(places,key=lambda row:row[0])][:PLACE_RESULT_LIMIT]
            except (KeyError,TypeError,ValueError):
                raise HTTPException(502,'Invalid place response from provider') from None
            self.cache[key]=(monotonic(),places)
            while len(self.cache)>256: self.cache.popitem(last=False)
            return places


class PhotonPlaceProvider(PlaceProvider):
    """Adapt Photon's GeoJSON to the same ranked/cached place contract."""
    name = 'photon'

    def _candidates(self, query):
        body = fetch_json(self.base_url+'/api/', {
            'q': query, 'lat': 10.7769, 'lon': 106.7009, 'limit': PLACE_CANDIDATE_LIMIT,
        }, self.agent, self.transport)
        try:
            if not isinstance(body, dict) or body.get('type') != 'FeatureCollection':
                raise ValueError('Expected FeatureCollection')
            features = body['features']
            if not isinstance(features, list) or len(features) > PLACE_CANDIDATE_LIMIT:
                raise ValueError('Invalid feature count')
            candidates = []
            for feature in features:
                geometry, properties = feature['geometry'], feature['properties']
                if feature['type'] != 'Feature' or geometry['type'] != 'Point':
                    raise ValueError('Expected Point feature')
                coordinates = geometry['coordinates']
                if not isinstance(coordinates, list) or len(coordinates) != 2:
                    raise ValueError('Expected longitude/latitude')
                point = LatLng(longitude=coordinates[0], latitude=coordinates[1])
                osm_type, osm_id = properties['osm_type'], properties['osm_id']
                if osm_type not in {'N', 'W', 'R'} or type(osm_id) is not int or osm_id <= 0:
                    raise ValueError('Invalid OSM identity')

                def text(key):
                    value = properties.get(key)
                    if value is None:
                        return ''
                    if not isinstance(value, str):
                        raise ValueError('Invalid place text')
                    return value.strip()

                parts = [text('name'), ' '.join(filter(None, [text('housenumber'), text('street')]))]
                parts += [text(key) for key in ('locality', 'district', 'city', 'county', 'state', 'country')]
                label, seen = [], set()
                for part in parts:
                    if part and part.casefold() not in seen:
                        label.append(part); seen.add(part.casefold())
                if not label:
                    raise ValueError('Missing address label')
                address = {key: text(key) for key in PLACE_REGION_FIELDS if properties.get(key)}
                address['country_code'] = text('countrycode').lower()
                candidates.append({'place_id': f'photon:{osm_type}:{osm_id}', 'display_name': ', '.join(label),
                                   'lat': point.latitude, 'lon': point.longitude, 'address': address})
            return candidates
        except (KeyError, TypeError, ValueError, AttributeError):
            raise HTTPException(502, 'Invalid place response from provider') from None


def make_place_provider(settings):
    provider = PhotonPlaceProvider if settings.places_provider == 'photon' else PlaceProvider
    return provider(settings.places_base_url, settings.provider_user_agent)
