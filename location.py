"""Module to hold location related classes and functions."""

import logging

from cachepy import *
from geopy import geocoders
from geopy.exc import GeocoderServiceError


# Cache for expensive calls for location lookups.
_memoize = Cache(ttl=3600)

# Locator (global) singleton instance.
_locator = None


def GetLocator(reverse_geo=False):
    """Get a Locator singleton.

    Args:
        reverse_geo: Boolean flag defining whether to reverse lookup
            coordinates for output. Note that his is costly.
    """
    global _locator
    if not _locator:
        _locator = Locator(reverse_geo=reverse_geo)
    return _locator


class Locator(object):
    """Geo location handler."""

    def __init__(self, reverse_geo=False):
        """Initializer.

        Args:
            reverse_geo: Boolean flag defining whether to reverse lookup
                coordinates for output. Note that his is costly.
        """
        self._reverse_geo = reverse_geo
        if self._reverse_geo:
            self._geolocator = geocoders.Nominatim()

    def Lookup(self, packet):
        """Lookup (coordinates to location) based on APRS packet.

        Args:
            packet: Dictionary representing an APRS packet.

        Returns:
            Location object or None if lookup failed.
        """
        if not self._reverse_geo:
            return None
        if 'latitude' not in packet or 'longitude' not in packet:
            return None
        return self._Lookup(packet['latitude'], packet['longitude'])

    @_memoize
    def _Lookup(self, lat, lon):
        """Lookup (coordinates to location) based on coordinates.

        Args:
            lat: Latitude as a float.
            long: Longitude as a float.

        Returns:
            Location object or None if lookup failed.
        """
        if not self._reverse_geo:
            return None
        try:
            return self._geolocator.reverse(
                '%s, %s' % (lat, lon), exactly_one=True)
        except GeocoderServiceError as e:
            logging.warn('geo lookup failed: %s', e)
            return None

    def PreciseLocation(self, loc):
        """Get an as precise location string.

        Args:
            loc: Location object to get the coarse description for.

        Returns:
            String describing the location as precise.
        """
        if not loc:
            return 'n/a'

        address = loc.raw.get('address')
        if not address:
            return 'n/a'

        pieces = []
        if 'village' in address:
            pieces.append(address['village'])
        elif 'county_district' in address:
            pieces.append(address['county_district'])
        elif 'county' in address:
            pieces.append(address['county'])
        if 'state' in address:
            pieces.append(address['state'])
        if 'country_code' in address:
            pieces.append(address['country_code'].upper())
        return ', '.join(pieces)

    def CoarseLocation(self, loc):
        """Get a coarse location string.

        Args:
            loc: Location object to get the coarse description for.

        Returns:
            String describing the location coarsly.
        """
        location = 'n/a'
        if not loc:
            return location

        address = loc.raw.get('address')
        if not address:
            return location

        location = address.get('country_code', '').upper() or location
        place = (address.get('village') or
                 address.get('county_district') or
                 address.get('county') or
                 address.get('state'))
        if place:
            location = '%s %s' % (place, location)
        return location
