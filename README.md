APRS Trigger Event
==========

ARPS message receiver and processor.

APRSte is based on APRSnooper which connects to aprs-is.net servers to retrieve the latest APRS packets
worldwide (optionally based on a filter you may specify) and processes them.

Processing at the moment is basically printing them in a somewhat nice format
or saving them away in a sqlite DB. This may change at a later point.

In order to trigger an emergency email with coordinates of the caller, APRSte is looking for a configurable keyword in the beacon message.

It is best to set server side filter in order to minimize the parsing and computation effort. I suggest to set filters on own callsign as per Example 1B.

Note: This project is primarily aplayground to explore APRS messages.



Requirements
------------

```bash
pip install aprslib geopy cachepy yagmail
```

Usage
-----

```bash
./aprste.py --help
usage: aprsnooper.py [-h] [--callsign <callsign>] [--server <server>]
                     [--aprs_filter <aprs_filter>] [--db <db>]
                     [--reverse_geo reverse_geo>]
```

Example 1: Filter for messages from Swiss stations

    ./aprsnooper.py -f "p/HB3/HB9"
    
Example 1b: Filter for messages related to a specific callsign

    ./aprsnooper.py -f "b/HB9HCM*"

Example 2: Save the full feed to a sqlite DB.

    ./aprsnooper.py --db /tmp/aprs.sqlite

Example 3: Get all Swiss weather reports (and no other messages)

    ./aprsnooper.py -f "p/HB3/HB9 -t/poimqstun"

Example 4: Get Swiss reports and reverse lookup coordinates

    ./aprsnooper.py -f "p/HB3/HB9" --reverse_geo=True

Filtering messages is done on the server side as APRS IS supports that already:

- Filter location to 100km around Zurich: `r/47.378429/8.5389199/100`
- Filter to callsigns from Switzerland: `p/HB3/HB9`

For a comprehensive guide on filtering options, see http://www.aprs-is.net/javaprsfilter.aspx.

References
----------

- http://www.aprs-is.net/
    - http://www.aprs-is.net/Connecting.aspx
    - http://www.aprs-is.net/javaprsfilter.aspx
- http://aprs-python.readthedocs.io/en/latest/index.html
