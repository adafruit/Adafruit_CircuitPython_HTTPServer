# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import secrets  # pylint: disable=no-name-in-module

import socketpool
import wifi

from adafruit_httpserver.request import HTTPRequest
from adafruit_httpserver.response import HTTPResponse
from adafruit_httpserver.server import HTTPServer


ssid, password = secrets.WIFI_SSID, secrets.WIFI_PASSWORD  # pylint: disable=no-member

print("Connecting to", ssid)
wifi.radio.connect(ssid, password)
print("Connected to", ssid)

pool = socketpool.SocketPool(wifi.radio)
server = HTTPServer(pool)


@server.route("/chunked")
def chunked(request: HTTPRequest):
    """
    Return the response with ``Transfer-Encoding: chunked``.
    """

    with HTTPResponse(request, chunked=True) as response:
        response.send_chunk("Adaf")
        response.send_chunk("ruit")
        response.send_chunk(" Indus")
        response.send_chunk("tr")
        response.send_chunk("ies")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
