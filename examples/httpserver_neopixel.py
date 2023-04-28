# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import board
import neopixel
import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static")

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)


@server.route("/change-neopixel-color")
def change_neopixel_color_handler_query_params(request: Request):
    """
    Changes the color of the built-in NeoPixel using query/GET params.
    """
    r = request.query_params.get("r")
    g = request.query_params.get("g")
    b = request.query_params.get("b")

    pixel.fill((int(r or 0), int(g or 0), int(b or 0)))

    with Response(request, content_type="text/plain") as response:
        response.send(f"Changed NeoPixel to color ({r}, {g}, {b})")


@server.route("/change-neopixel-color/<r>/<g>/<b>")
def change_neopixel_color_handler_url_params(request: Request, r: str, g: str, b: str):
    """
    Changes the color of the built-in NeoPixel using URL params.
    """
    pixel.fill((int(r or 0), int(g or 0), int(b or 0)))

    with Response(request, content_type="text/plain") as response:
        response.send(f"Changed NeoPixel to color ({r}, {g}, {b})")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
