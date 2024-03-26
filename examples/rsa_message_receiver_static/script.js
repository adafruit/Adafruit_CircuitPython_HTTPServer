/*
SPDX-FileCopyrightText: 2024 Tim Cocks
SPDX-License-Identifier: Unlicense
 */
import {parseBigInt} from "./jsbn.js";

let $sendBtn = document.querySelector("#send");
let $messageTxt = document.querySelector("#message");
let $publicKey = document.querySelector("#pubkey");
let $output = document.querySelector("#output");

let pubKeyHexArgs = JSON.parse(getCookie("pub_key"));
const nStr = pubKeyHexArgs["public_key_arguments"][0];
const eStr = pubKeyHexArgs["public_key_arguments"][1];

const n = parseBigInt(nStr, 16);
const e = parseInt(eStr, 16);

const encrypt = new JSEncrypt();
const key = encrypt.getKey();
key.parsePropertiesFrom({n, e});

$publicKey.innerText = key.getPublicKey();


$sendBtn.addEventListener("click", function () {
    console.log("send click");

    postData("/send", {
        "message": encrypt.encrypt($messageTxt.value)
    }).then(function (respData) {
        console.log(respData);
        if (respData["success"] === true) {
            console.log("POST send message success");
            $messageTxt.value = "";
            $output.innerText = "Message sent";
        }else{
            $output.innerText = "Error";
        }
    });
});

async function postData(url = "", data = {}) {
    // Default options are marked with *
    const response = await fetch(url, {
        method: "POST", // *GET, POST, PUT, DELETE, etc.
        mode: "cors", // no-cors, *cors, same-origin
        cache: "no-cache", // *default, no-cache, reload, force-cache, only-if-cached
        credentials: "same-origin", // include, *same-origin, omit
        headers: {
            "Content-Type": "application/json",
            // 'Content-Type': 'application/x-www-form-urlencoded',
        },
        redirect: "follow", // manual, *follow, error
        referrerPolicy: "no-referrer", // no-referrer, *no-referrer-when-downgrade, origin, origin-when-cross-origin, same-origin, strict-origin, strict-origin-when-cross-origin, unsafe-url
        body: JSON.stringify(data), // body data type must match "Content-Type" header
    });
    return response.json(); // parses JSON response into native JavaScript objects
}

function getCookie(c_name) {
    var c_start, c_end;
    if (document.cookie.length > 0) {
        c_start = document.cookie.indexOf(c_name + "=");
        if (c_start != -1) {
            c_start = c_start + c_name.length + 1;
            c_end = document.cookie.indexOf(";", c_start);
            if (c_end == -1) {
                c_end = document.cookie.length;
            }
            return unescape(document.cookie.substring(c_start, c_end));
        }
    }
    return "";
}
