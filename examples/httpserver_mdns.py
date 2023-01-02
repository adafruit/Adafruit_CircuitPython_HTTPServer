# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import secrets  # pylint: disable=no-name-in-module

import mdns
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

mdns_server = mdns.Server(wifi.radio)
mdns_server.hostname = "custom-mdns-hostname"
mdns_server.advertise_service(service_type="_http", protocol="_tcp", port=80)

pool = socketpool.SocketPool(wifi.radio)
server = HTTPServer(pool)


@server.route("/")
def base(request: HTTPRequest):
    """
    Serve the default index.html file.
    """
    with HTTPResponse(request, content_type=MIMEType.TYPE_HTML) as response:
        response.send_file("index.html")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
