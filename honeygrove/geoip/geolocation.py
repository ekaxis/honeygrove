import logging


class Geolocation(dict):
    """
    {
        'query': (str,),
        'continent': (str,),
        'continentCode': (str,),
        'country': (str,),
        'countryCode': (str,),
        'region': (str,),
        'regionName': (str,),
        'city': (str,),
        'district': (str,),
        'zip': (str,),
        'lat': (float,),
        'lon': (float,),
        'timezone': (str,),
        'isp': (str,),
        'org': (str,),
        'as': (str,),
        'reverse': (str,),
    }
    """

    @property
    def location(self):
        return f'{self.lat}, {self.location}'

    @property
    def address(self):
        return f'{self.continent}, {self.country}, {self.region_name}, {self.city}'

    @property
    def ip(self):
        return self['query']

    @property
    def continent(self):
        return self['continent']

    @property
    def continent_code(self):
        return self['continentCode']

    @property
    def country(self):
        return self['country']

    @property
    def country_code(self):
        return self['countryCode']

    @property
    def region(self):
        return self['region']

    @property
    def region_name(self):
        return self['regionName']

    @property
    def city(self):
        return self['city']

    @property
    def district(self):
        return self['district']

    @property
    def zip(self):
        return self['zip']

    @property
    def lat(self):
        return self['lat']

    @property
    def lon(self):
        return self['lon']

    @property
    def timezone(self):
        return self['timezone']

    @property
    def isp(self):
        return self['isp']

    @property
    def org(self):
        return self['org']

    @property
    def reverse(self):
        return self['reverse']
