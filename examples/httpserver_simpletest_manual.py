# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import os

import socketpool
import wifi

from adafruit_httpserver import Server, Request, Response

ssid = os.getenv("WIFI_SSID")
password = os.getenv("WIFI_PASSWORD")

print("Connecting to", ssid)
wifi.radio.connect(ssid, password)
print("Connected to", ssid)

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, "/static")


@server.route("/")
def base(request: Request):
    """
    Serve a default static plain text message.
    """
    with Response(request, content_type="text/plain") as response:
        message = "Hello from the CircuitPython HTTP Server!"
        response.send(message)


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
