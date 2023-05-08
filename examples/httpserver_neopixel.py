# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import board
import neopixel
import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response, GET, POST


pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static", debug=True)

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)


@server.route("/change-neopixel-color", GET)
def change_neopixel_color_handler_query_params(request: Request):
    """Changes the color of the built-in NeoPixel using query/GET params."""

    # e.g. /change-neopixel-color?r=255&g=0&b=0

    r = request.query_params.get("r") or 0
    g = request.query_params.get("g") or 0
    b = request.query_params.get("b") or 0

    pixel.fill((int(r), int(g), int(b)))

    return Response(request, f"Changed NeoPixel to color ({r}, {g}, {b})")


@server.route("/change-neopixel-color", POST)
def change_neopixel_color_handler_post_body(request: Request):
    """Changes the color of the built-in NeoPixel using POST body."""

    data = request.body  # e.g b"255,0,0"
    r, g, b = data.decode().split(",")  # ["255", "0", "0"]

    pixel.fill((int(r), int(g), int(b)))

    return Response(request, f"Changed NeoPixel to color ({r}, {g}, {b})")


@server.route("/change-neopixel-color/json", POST)
def change_neopixel_color_handler_post_json(request: Request):
    """Changes the color of the built-in NeoPixel using JSON POST body."""

    data = request.json()  # e.g {"r": 255, "g": 0, "b": 0}
    r, g, b = data.get("r", 0), data.get("g", 0), data.get("b", 0)

    pixel.fill((r, g, b))

    return Response(request, f"Changed NeoPixel to color ({r}, {g}, {b})")


@server.route("/change-neopixel-color/<r>/<g>/<b>", GET)
def change_neopixel_color_handler_url_params(
    request: Request, r: str = "0", g: str = "0", b: str = "0"
):
    """Changes the color of the built-in NeoPixel using URL params."""

    # e.g. /change-neopixel-color/255/0/0

    pixel.fill((int(r), int(g), int(b)))

    return Response(request, f"Changed NeoPixel to color ({r}, {g}, {b})")


server.serve_forever(str(wifi.radio.ipv4_address))
