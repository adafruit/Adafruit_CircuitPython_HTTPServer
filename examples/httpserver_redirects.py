# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, Redirect, NOT_FOUND_404


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)

REDIRECTS = {
    "google": "https://www.google.com",
    "adafruit": "https://www.adafruit.com",
    "circuitpython": "https://circuitpython.org",
}


@server.route("/blinka")
def redirect_blinka(request: Request):
    """
    Always redirect to a Blinka page as permanent redirect.
    """
    return Redirect(request, "https://circuitpython.org/blinka", permanent=True)


@server.route("/<slug>")
def redirect_other(request: Request, slug: str = None):
    """
    Redirect to a URL based on the slug.
    """

    if slug is None or not slug in REDIRECTS:
        return Response(request, "Unknown redirect", status=NOT_FOUND_404)

    return Redirect(request, REDIRECTS.get(slug))


server.serve_forever(str(wifi.radio.ipv4_address))
