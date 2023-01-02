# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import secrets  # pylint: disable=no-name-in-module

import board
import neopixel
import socketpool
import wifi

from adafruit_httpserver.mime_type import MIMEType
from adafruit_httpserver.request import HTTPRequest
from adafruit_httpserver.response import HTTPResponse
from adafruit_httpserver.server import HTTPServer


ssid, password = secrets.WIFI_SSID, secrets.WIFI_PASSWORD  # pylint: disable=no-member

print("Connecting to", ssid)
wifi.radio.connect(ssid, password)
print("Connected to", ssid)

pool = socketpool.SocketPool(wifi.radio)
server = HTTPServer(pool)

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)


@server.route("/change-neopixel-color")
def change_neopixel_color_handler(request: HTTPRequest):
    """
    Changes the color of the built-in NeoPixel.
    """
    r = request.query_params.get("r")
    g = request.query_params.get("g")
    b = request.query_params.get("b")

    pixel.fill((int(r or 0), int(g or 0), int(b or 0)))

    with HTTPResponse(request, content_type=MIMEType.TYPE_TXT) as response:
        response.send(f"Changed NeoPixel to color ({r}, {g}, {b})")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
