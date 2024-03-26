# SPDX-FileCopyrightText: 2024 Tim Cocks
#
# SPDX-License-Identifier: Unlicense
import binascii
import json

import socketpool
import wifi

import adafruit_rsa
from adafruit_rsa import PrivateKey
from adafruit_httpserver import Server, Request, Response, GET, POST

pool = socketpool.SocketPool(wifi.radio)
server = Server(pool, debug=True, root_path="rsa_message_receiver_static")

context = {"publickey": None, "response": None, "responding": False}

with open("static/basic_chat.html") as f:
    page = f.read()


@server.route("/", GET)
def main_page(request: Request):
    with open("rsa_message_receiver_keys/example512key_pub.json", "r") as pubkey_file:
        key_obj = json.loads(pubkey_file.read())
        for i, val in enumerate(key_obj["public_key_arguments"]):
            key_obj["public_key_arguments"][i] = str(hex(val))[2:]
        cookies = {"pub_key": json.dumps(key_obj)}

    return Response(
        request,
        page,
        content_type="text/html",
        cookies=cookies,
    )


@server.route("/send", POST)
def send(request):
    request_data = request.json()

    # print(request_data)
    with open("rsa_message_receiver_keys/example512key.json", "r") as privkey_file:
        priv_key_obj = json.loads(privkey_file.read())
    private_key = PrivateKey(*priv_key_obj["private_key_arguments"])

    print("Received ciphertext:")
    print(request_data["message"])

    clear_text_message = adafruit_rsa.decrypt(
        binascii.a2b_base64(request_data["message"]), private_key
    )
    print("Received cleartext:")
    print(clear_text_message)

    return Response(
        request, json.dumps({"success": True}), content_type="application/json"
    )


server.start(str(wifi.radio.ipv4_address))

while True:
    server.poll()
