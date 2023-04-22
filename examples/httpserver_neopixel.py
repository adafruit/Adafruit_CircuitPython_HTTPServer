# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import os

import board
import neopixel
import socketpool
import wifi

from adafruit_httpserver.mime_type import MIMEType
from adafruit_httpserver.request import HTTPRequest
from adafruit_httpserver.response import HTTPResponse
from adafruit_httpserver.server import HTTPServer


ssid = os.getenv("WIFI_SSID")
password = os.getenv("WIFI_PASSWORD")

print("Connecting to", ssid)
wifi.radio.connect(ssid, password)
print("Connected to", ssid)

pool = socketpool.SocketPool(wifi.radio)
server = HTTPServer(pool, "/static")

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)


@server.route("/change-neopixel-color")
def change_neopixel_color_handler_query_params(request: HTTPRequest):
    """
    Changes the color of the built-in NeoPixel using query/GET params.
    """
    r = request.query_params.get("r")
    g = request.query_params.get("g")
    b = request.query_params.get("b")

    pixel.fill((int(r or 0), int(g or 0), int(b or 0)))

    with HTTPResponse(request, content_type=MIMEType.TYPE_TXT) as response:
        response.send(f"Changed NeoPixel to color ({r}, {g}, {b})")


@server.route("/change-neopixel-color/<r>/<g>/<b>")
def change_neopixel_color_handler_url_params(
    request: HTTPRequest, r: str, g: str, b: str
):
    """
    Changes the color of the built-in NeoPixel using URL params.
    """
    pixel.fill((int(r or 0), int(g or 0), int(b or 0)))

    with HTTPResponse(request, content_type=MIMEType.TYPE_TXT) as response:
        response.send(f"Changed NeoPixel to color ({r}, {g}, {b})")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
