# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, GET, POST, PUT, DELETE


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)


@server.route("/api", [GET, POST, PUT, DELETE])
def api(request: Request):
    """
    Performs different operations depending on the HTTP method.
    """

    if request.method == GET:
        # Get objects
        with Response(request) as response:
            response.send("Objects: ...")

    if request.method in [POST, PUT]:
        # Upload or update objects
        with Response(request) as response:
            response.send("Object uploaded/updated")

    if request.method == DELETE:
        # Delete objects
        with Response(request) as response:
            response.send("Object deleted")


server.serve_forever(str(wifi.radio.ipv4_address))
