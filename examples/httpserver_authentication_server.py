# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, Basic, Bearer


# Create a list of available authentication methods.
auths = [
    Basic("user", "password"),
    Bearer("642ec696-2a79-4d60-be3a-7c9a3164d766"),
]

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static", debug=True)
server.require_authentication(auths)


@server.route("/implicit-require")
def implicit_require_authentication(request: Request):
    """
    Implicitly require authentication because of the server.require_authentication() call.
    """

    return Response(request, body="Authenticated", content_type="text/plain")


server.serve_forever(str(wifi.radio.ipv4_address))
