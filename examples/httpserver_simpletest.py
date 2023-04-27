# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import os

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


@server.route("/")
def base(request: HTTPRequest):
    """
    Serve a default static plain text message.
    """
    with HTTPResponse(request, content_type=MIMEType.TYPE_TXT) as response:
        message = "Hello from the CircuitPython HTTPServer!"
        response.send(message)


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
