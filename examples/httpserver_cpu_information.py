# SPDX-FileCopyrightText: 2022 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

import secrets  # pylint: disable=no-name-in-module

import json
import microcontroller
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


@server.route("/cpu-information")
def cpu_information_handler(request: HTTPRequest):
    """
    Return the current CPU temperature, frequency, and voltage as JSON.
    """

    data = {
        "temperature": microcontroller.cpu.temperature,
        "frequency": microcontroller.cpu.frequency,
        "voltage": microcontroller.cpu.voltage,
    }

    with HTTPResponse(request, content_type=MIMEType.TYPE_JSON) as response:
        response.send(json.dumps(data))


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
