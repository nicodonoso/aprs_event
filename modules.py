"""Module to handle different formats of APRS packets.

Types:
    normal/compressed position reports
    mic-e position reports
    objects reports
    weather reports
    status reports
    messages (inc. telemetry, bulletins, etc)
    base91 comment telemetry extension
    altitude extension
    beacons

Reference:
    - http://www.aprs-is.net/javaprsfilter.aspx
    - http://aprs-python.readthedocs.io/en/stable/parse_formats.html#supported-formats
"""

import abc
import pprint
import threading
import time

import location


class Module(object):
    """Abstract format module class defining the interface."""

    __metaclass__ = abc.ABCMeta

    def __init__(self, reverse_geo=False):
        """Initializer.

        Args:
            reverse_geo: Boolean flag defining whether to reverse lookup
                coordinates for output. Note that his is costly.
        """
        self._locator = location.GetLocator(reverse_geo=reverse_geo)

    @abc.abstractmethod
    def name(self):
        """Name for identification."""

    @abc.abstractmethod
    def format(self):
        """Supported formats."""

    @abc.abstractmethod
    def handle(self, packet):
        """Function to handle the packet of the given format type.

        Args:
            packet: Dictionary containing one APRS packet of the given format.
        """


class GenericModule(Module):
    """Generic module able to handle all formats in a simplistic way."""

    def name(self):
        return 'Generic'

    def format(self):
        return 'generic'

    def handle(self, packet):
        pprint.pprint(packet)


class PositionModule(GenericModule):
    """Module handling position reports."""

    def name(self):
        return 'Position Reports'

    def format(self):
        return 'uncompressed,compressed,mic-e'

    def handle(self, packet):
        location = None
        loc = self._locator.Lookup(packet)
        if loc:
            location = self._locator.PreciseLocation(loc)

        comment = packet.get('comment', 'n/a')
        lat = packet.get('latitude', 'n/a')
        lon = packet.get('longitude', 'n/a')
        alt = packet.get('altitude', 'n/a')

        parts = ['position(%s):' % packet.get('from', 'n/a'),
                 'coordinates(%s,%s),' % (lat, lon),
                 'altitude(%s),' % alt,
                 'comment(%s),' % comment]
        if location:
            parts.append('location(%s),' % location)
        print ' '.join(parts)


class ObjectModule(GenericModule):
    """Module handing object reports."""

    def name(self):
        return 'Objects Reports'

    def format(self):
        return 'object'

    def handle(self, packet):
        location = None
        loc = self._locator.Lookup(packet)
        if loc:
            location = self._locator.CoarseLocation(loc)

        comment = packet.get('comment', 'n/a')
        object_name = packet.get('object_name', 'n/a').strip()
        course = packet.get('course', 'n/a')
        lat = packet.get('latitude', 'n/a')
        lon = packet.get('longitude', 'n/a')
        alt = packet.get('altitude', 'n/a')

        parts = ['object(%s):' % packet.get('from', 'n/a'),
                 'coordinates(%s,%s),' % (lat, lon),
                 'altitude(%s),' % alt,
                 'course(%s),' % course,
                 'object_name(%s),' % object_name,
                 'comment(%s),' % comment]
        if location:
            parts.append('location(%s),' % location)
        print ' '.join(parts)


class WeatherModule(Module):
    """Module handling weather reports."""

    def name(self):
        return 'Weather Reports'

    def format(self):
        return 'wx'

    def handle(self, packet):
        weather = packet.get('weather', None)
        if not weather:
            return

        loc = self._locator.Lookup(packet)
        if loc:
            location = self._locator.CoarseLocation(loc)
        else:
            location = packet.get('from', 'n/a')

        temperature = 'n/a'
        if weather.get('temperature'):
            temperature = '%.1f' % weather['temperature']
        humidity = weather.get('humidity', 'n/a')
        pressure = weather.get('pressure', 'n/a')
        wind = weather.get('wind', 'n/a')
        print 'weather(%s): temp(%s), humidity(%s)' % (
            location, temperature, humidity)

        parts = ['weather(%s):' % location,
                 'temp(%s),' % temperature,
                 'humidity(%s),' % humidity,
                 'pressure(%s),' % pressure,
                 'wind(%s),' % wind]
        print ' '.join(parts)


class StatusModule(GenericModule):
    """Module handling status reports."""

    def name(self):
        return 'Status Reports'

    def format(self):
        return 'status'

    def handle(self, packet):
        print 'status(%s): %s' % (packet.get('from', 'n/a'),
                                  packet.get('status', 'n/a'))


class MessageModule(GenericModule):
    """Module handling messages."""

    def name(self):
        return 'Messages'

    def format(self):
        return 'message'

    def handle(self, packet):
        parts = ['message(%s):' % packet['addresse'],
                 'to(%s),' % packet['to'],
                 'from(%s),' % packet['from'],
                 'text(%s),' % packet['text']]
        print ' '.join(parts)


class TelemetryModule(GenericModule):
    """Module handling telemetry messages."""

    def __init__(self, reverse_geo=False):
        super(TelemetryModule, self).__init__(reverse_geo=reverse_geo)

        # Telemetry cache
        # k: 'addresse,from,to'
        # v: {'time': time, 'ready': bool, 'values': [[name, value, unit]]}
        self._cache = {}
        self._cache_lock = threading.RLock()
        self._cache_clean_time = 60
        self._cache_max_age = 3600
        self._cache_timer = threading.Timer(
            self._cache_clean_time, self._cache_clean)

    def _cache_clean(self):
        if self._cache_timer:
            self._cache_timer.cancel()
        self._cache_timer = threading.Timer(
            self._cache_clean_time, self._cache_clean)
        self._cache_timer.start()

        to_delete = []
        for key, item in self._cache.iteritems():
            if item[0] + self._cache_max_age < time.time():
                to_delete.append(key)

        with self._cache_lock:
            for key in to_delete:
                del self._cache[key]

    def name(self):
        return 'Telemetry'

    def format(self):
        return 'telemetry-message'

    def handle(self, packet):
        key = ','.join([packet['addresse'], packet['from'], packet['to']])
        entry = self._cache.get(key, {})
        entry['time'] = int(time.time())
        values = entry.get('values', [])

        # Check which flavor this update is of.
        if 'tPARM' in packet:
            if len(values) != len(packet['tPARM']):
                values = []
            if len(values) == 0:
                for p in packet['tPARM']:
                    values.append([p, None, None])
            else:
                for i, p in enumerate(packet['tPARM']):
                    values[i][0] = p

        if 'tUNIT' in packet:
            if len(values) == 0:
                for u in packet['tUNIT']:
                    values.append([None, None, u])
            else:
                for i, u in enumerate(packet['tUNIT']):
                    values[i][2] = u

        if 'tEQNS' in packet:
            if len(values) == 0:
                for e in packet['tEQNS']:
                    values.append([None, e, None])
            else:
                for i, e in enumerate(packet['tEQNS']):
                    values[i][1] = e

        if 'tBITS' in packet:
            pass  # Not sure how this one works but seen it in the wild.

        if not values:
            return
        # Update the cache.
        entry['values'] = values
        with self._cache_lock:
            self._cache[key] = entry

        # Check if entry is complete before printing.
        if not values[0][0] or not values[0][1] or not values[0][2]:
            return

        parts = ['telemetry(%s):' % packet['addresse'],
                 'to(%s),' % packet['to'],
                 'from(%s),' % packet['from'],
                 'data(%s),' % entry]
        print ' '.join(parts)


# List of all supported module classes.
_MODULES = [GenericModule,
            PositionModule,
            ObjectModule,
            WeatherModule,
            StatusModule,
            MessageModule,
            TelemetryModule]


class ModuleFactory(object):
    """Class to create module handlers on demand."""

    def __init__(self, reverse_geo=False):
        """Initializer.

        Args:
            reverse_geo: Boolean flag defining whether to reverse lookup
                coordinates for output. Note that his is costly.
        """
        self._instances = {}
        for m in _MODULES:
            instance = m(reverse_geo=reverse_geo)
            self._instances[instance.format()] = instance

    def get(self, packet):
        """Retrievees the right module for the packet.

        Args:
            packet: Dictionary holding a parsed APRS packet.

        Returns:
            Module instance supporting the format of the given packet.
        """
        # Weather packets sometimes are sent in "uncompressed" packets.
        if 'weather' in packet:
            return self._instances['wx']

        for form, instance in self._instances.iteritems():
            if packet.get('format', 'generic') in form:
                return instance
