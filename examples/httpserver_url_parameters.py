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


class Device:
    def turn_on(self):  # pylint: disable=no-self-use
        print("Turning on device.")

    def turn_off(self):  # pylint: disable=no-self-use
        print("Turning off device.")


def get_device(device_id: str) -> Device:  # pylint: disable=unused-argument
    """
    This is a **made up** function that returns a `Device` object.
    """
    return Device()


@server.route("/device/<device_id>/action/<action>")
@server.route("/device/emergency-power-off/<device_id>")
def perform_action(
    request: HTTPRequest, device_id: str, action: str = "emergency_power_off"
):
    """
    Performs an "action" on a specified device.
    """

    device = get_device(device_id)

    if action in ["turn_on"]:
        device.turn_on()
    elif action in ["turn_off", "emergency_power_off"]:
        device.turn_off()
    else:
        with HTTPResponse(request, content_type=MIMEType.TYPE_TXT) as response:
            response.send(f"Unknown action ({action})")
        return

    with HTTPResponse(request, content_type=MIMEType.TYPE_TXT) as response:
        response.send(f"Action ({action}) performed on device with ID: {device_id}")


@server.route("/something/<route_param_1>/<route_param_2>")
def different_name_parameters(
    request: HTTPRequest,
    handler_param_1: str,  #  pylint: disable=unused-argument
    handler_param_2: str = None,  #  pylint: disable=unused-argument
):
    """
    Presents that the parameters can be named anything.

    ``route_param_1`` -> ``handler_param_1``
    ``route_param_2`` -> ``handler_param_2``
    """

    with HTTPResponse(request, content_type=MIMEType.TYPE_TXT) as response:
        response.send("200 OK")


print(f"Listening on http://{wifi.radio.ipv4_address}:80")
server.serve_forever(str(wifi.radio.ipv4_address))
