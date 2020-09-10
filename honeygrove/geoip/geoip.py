import json
import urllib.request

from .geolocation import Geolocation

uribase = 'http://ip-api.com/json/'
query = '?fields=20512767'
"""
generated numeric: 20512767

generated fields:
http://ip-api.com/json/{query}?fields=status,message,continent,continentCode,
                                      country,countryCode,region,regionName,city,
                                      district,zip,lat,lon,timezone,isp,org,as,hosting,reverse,query
"""

def decode_bytes_to_utf8(text: bytes):
    if isinstance(text, bytes):
        return text.decode('utf-8', errors='ignore')
    return text


def json_decode(text: str):
    if isinstance(text, str):
        return json.loads(text)
    return text


def create_obj_geolocation(dic):
    if isinstance(dic, str):
        dic = json_decode(dic)
    return Geolocation(dic)


def get_geoip(uri):
    with urllib.request.urlopen(uri) as response:
        body = response.read()
    return decode_bytes_to_utf8(body)


def geoip(ip):
    """
    { 'as': 'AS61592 FORT LINK INTERNET '
            'CORPORATIVA BRASIL LTDA \xad '
            'EPP',
    'city': 'Camaragibe',
    'continent': 'South America',
    'continentCode': 'SA',
    'country': 'Brazil',
    'countryCode': 'BR',
    'district': '',
    'hosting': False,
    'isp': 'FORT LINK INTERNET '
           'CORPORATIVA BRASIL LTDA � EPP',
    'lat': -7.9878,
    'lon': -34.9914,
    'org': 'FORT LINK INTERNET '
           'CORPORATIVA BRASIL LTDA \xad '
           'EPP',
    'query': '45.234.102.103',
    'region': 'PE',
    'regionName': 'Pernambuco',
    'reverse': 'fort2-103.fortlink.net.br',
    'status': 'success',
    'timezone': 'America/Recife',
    'zip': '54750'}
    """
    uri = uribase+ip+query
    addr = create_obj_geolocation(get_geoip(uri))
    return addr
