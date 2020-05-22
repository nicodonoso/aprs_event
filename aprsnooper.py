#!/usr/bin/env python

"""APRS Receiver through aprs-is.net."""

import aprslib
import argparse
import logging
import pprint
import signal
import sqlite3
import threading
import time

import modules

from logging.config import dictConfig


class Error(Exception):
    """Base error class to use for this module."""


class InProgressError(Error):
    """Error class to use when connection is already established."""


class APRSnooper(object):
    """APRS receiver and processor."""

    def __init__(self, callsign, server, port, db_string='', aprs_filter='',
                 reverse_geo=False):
        """Initializes aprsnooper 

        Args:
            callsign: Callsign to log in with.
            server: Server to connect to.
            port: Port to connect to on the server.
            db_string: SQL database to connect to.
            aprs_filter: APRS filter string to apply.
            reverse_geo: Boolean flag defining whether to reverse lookup
                coordinates for output. Note that his is costly.
        """
        self._callsign = callsign
        self._server = server
        self._port = port
        self._aprs_filter = aprs_filter

        self._consumer_thread = None
        self._abort_consume = False
        self._db = None
        self._db_string = db_string
        self._packet_count = 0
        self._consume_start = 0

        self._module_factory = modules.ModuleFactory(
            reverse_geo=reverse_geo)
        self._logger = logging.getLogger(
            "%s.%s" % (__name__, self.__class__.__name__))

    def _callback(self, packet):
        """Callback function for received packets.

        Args:
            packet: Dictionary representing a parsed packet from aprslib.
        """
        if self._abort_consume:
            raise StopIteration()

        self._packet_count += 1
        if self._packet_count % 1000 == 0:
            logging.info('received %d packets in %d sec' % (
                self._packet_count, int(time.time()-self._consume_start)))

        if self._db:
            with self._db:
                cur = self._db.cursor()
                cur.execute('CREATE TABLE IF NOT EXISTS aprs (Id INTEGER PRIMARY KEY, raw TEXT)')
                cur.execute("INSERT INTO aprs(raw) VALUES (?);", [packet['raw']])
            return

        #logging.info(packet)
        module = self._module_factory.get(packet)
        if not module:
            logging.debug('no module found for packet: %s', packet)
            return
        module.handle(packet)

    def IsAlive(self):
        """Returns whether or not there is a live connection."""
        if not self._consumer_thread:
            return False
        return self._consumer_thread.isAlive()

    def _consume(self):
        """Blocking function to receive and parse messages.

        Note: This function is meant to be started as a separate thread and
            only exits when StopIteration is raised in the callback.
        """
        # Setup connection.
        ais = aprslib.IS(self._callsign,
                         host=self._server,
                         port=self._port)
        if self._aprs_filter:
            ais.set_filter(self._aprs_filter)
        ais.connect(blocking=False)

        # Actually consume APRS packets.
        self._abort_consume = False
        self._packet_count = 0
        self._consume_start = time.time()
        if self._db_string:
            self._db = sqlite3.connect(self._db_string)
        ais.consumer(self._callback, raw=False, blocking=True, immortal=True)

        # The above is blocking. This will be called once we're done.
        self._consumer_thread = None
        if self._db:
            self._db.close()
            self._db = None

    def Start(self):
        """Starts listening for APRS messages.

        Raises:
            InProgressError: Connection already established.
        """
        if self._consumer_thread:
            raise InProgressError('connection in progress already')

        self._consumer_thread = threading.Thread(
            name='consumer', target=self._consume)
        self._consumer_thread.start()

    def Stop(self):
        """Stop receiving APRS messages."""
        self._abort_consume = True
        if self._consumer_thread:
            self._consumer_thread.join(5)


if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    LOGGING_CONFIG = dict(
        version=1,
        formatters={
            'f': {
                'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                },
            },
        handlers={
            'h': {
                'class': 'logging.StreamHandler',
                'formatter': 'f',
                'level': logging.INFO,
                },
            },
        root={
            'handlers': ['h'],
            'level': logging.DEBUG,
            },
    )
    dictConfig(LOGGING_CONFIG)

    p = argparse.ArgumentParser(description='APRSnooper')
    p.add_argument('--callsign', '-c', default='anon',
                   metavar='<callsign>',
                   help='Callsign to log in with')
    p.add_argument('--server', '-s', default='rotate.aprs.net',
                   metavar='<server>',
                   help='APRS IS server address (default: rotate.aprs.net)')
    p.add_argument('--aprs_filter', '-f', default='',
                   metavar='<aprs_filter>',
                   help='Filter string to use (if server port supports it).')
    p.add_argument('--db', '-d', default='',
                   metavar='<db>',
                   help='Database to connect to.')
    p.add_argument('--reverse_geo', '-g', type=bool, default=False,
                   metavar='reverse_geo>',
                   help='Do reverse geo lookups (Default: False)')
    args = p.parse_args()

    port = 10152     # this is the full feed port
    if args.aprs_filter:
        port = 14580  # this is the default port for user defined filtering
    else:
        logging.warn('Careful: Not setting a filter may result in missed '
                     'messages.')

    t = APRSnooper(args.callsign, args.server, port, args.db,
                   aprs_filter=args.aprs_filter, reverse_geo=args.reverse_geo)
    t.Start()

    # Set up signal handler to abort with CTRL-C.
    def signal_handler(unused_signal, unused_frame):
        """Signal handler that aborts all threads/timers nicely."""
        logging.info('Signal handler called. Aborting.')
        t.Stop()

    signal.signal(signal.SIGINT, signal_handler)

    # Loop
    while t.IsAlive():
        time.sleep(1)
