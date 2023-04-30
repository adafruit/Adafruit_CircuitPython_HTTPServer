# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True)


@server.route("/chunked")
def chunked(request: Request):
    """
    Return the response with ``Transfer-Encoding: chunked``.
    """

    with Response(request, chunked=True) as response:
        response.send_chunk("Adaf")
        response.send_chunk("ruit")
        response.send_chunk(" Indus")
        response.send_chunk("tr")
        response.send_chunk("ies")


server.serve_forever(str(wifi.radio.ipv4_address))
