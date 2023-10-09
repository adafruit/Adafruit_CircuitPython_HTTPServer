Simple Test
-----------

**All examples in this document are using** ``Server`` **in** ``debug`` **mode.**
**This mode is useful for development, but it is not recommended to use it in production.**
**More about Debug mode at the end of Examples section.**

This is the minimal example of using the library.
This example is serving a simple static text message.

It also manually connects to the WiFi network.

.. literalinclude:: ../examples/httpserver_simpletest_manual.py
    :caption: examples/httpserver_simpletest_manual.py
    :emphasize-lines: 12-17
    :linenos:

It is also possible to use Ethernet instead of WiFi.
The only difference in usage is related to configuring the ``socket_source`` differently.

.. literalinclude:: ../examples/httpserver_ethernet_simpletest.py
    :caption: examples/httpserver_ethernet_simpletest.py
    :emphasize-lines: 13-23
    :linenos:

Although there is nothing wrong with this approach, from the version 8.0.0 of CircuitPython,
`it is possible to use the environment variables <https://docs.circuitpython.org/en/latest/docs/environment.html#circuitpython-behavior>`_
defined in ``settings.toml`` file to store secrets and configure the WiFi network.

This is the same example as above, but it uses the ``settings.toml`` file to configure the WiFi network.

**From now on, all the examples will use the** ``settings.toml`` **file to configure the WiFi network.**

.. literalinclude:: ../examples/settings.toml
    :caption: settings.toml
    :lines: 5-
    :linenos:

Note that we still need to import ``socketpool`` and ``wifi`` modules.

.. literalinclude:: ../examples/httpserver_simpletest_auto.py
    :caption: examples/httpserver_simpletest_auto.py
    :emphasize-lines: 11
    :linenos:

Serving static files
--------------------

It is possible to serve static files from the filesystem.
In this example we are serving files from the ``/static`` directory.

In order to save memory, we are unregistering unused MIME types and registering additional ones.
`More about MIME types. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types>`_

.. literalinclude:: ../examples/httpserver_static_files_serving.py
    :caption: examples/httpserver_static_files_serving.py
    :emphasize-lines: 12-18,23-26
    :linenos:

You can also serve a specific file from the handler.
By default ``FileResponse`` looks for the file in the server's ``root_path`` directory, but you can change it.

.. literalinclude:: ../examples/httpserver_handler_serves_file.py
    :caption: examples/httpserver_handler_serves_file.py
    :emphasize-lines: 22
    :linenos:

.. literalinclude:: ../examples/home.html
    :language: html
    :caption: www/home.html
    :lines: 5-
    :linenos:

Tasks between requests
----------------------

If you want your code to do more than just serve web pages,
use the ``.start()``/``.poll()`` methods as shown in this example.

Between calling ``.poll()`` you can do something useful,
for example read a sensor and capture an average or
a running total of the last 10 samples.

``.poll()`` return value can be used to check if there was a request and if it was handled.

.. literalinclude:: ../examples/httpserver_start_and_poll.py
    :caption: examples/httpserver_start_and_poll.py
    :emphasize-lines: 29,38
    :linenos:


If you need to perform some action periodically, or there are multiple tasks that need to be done,
it might be better to use ``asyncio`` module to handle them, which makes it really easy to add new tasks
without needing to manually manage the timing of each task.

``asyncio`` **is not included in CircuitPython by default, it has to be installed separately.**

.. literalinclude:: ../examples/httpserver_start_and_poll_asyncio.py
    :caption: examples/httpserver_start_and_poll_asyncio.py
    :emphasize-lines: 5,33,42,45,50,55-62
    :linenos:

Server with MDNS
----------------

It is possible to use the MDNS protocol to make the server accessible via a hostname in addition
to an IP address. It is worth noting that it takes a bit longer to get the response from the server
when accessing it via the hostname.

In this example, the server is accessible via the IP and ``http://custom-mdns-hostname.local/``.
On some routers it is also possible to use ``http://custom-mdns-hostname/``, but **this is not guaranteed to work**.

.. literalinclude:: ../examples/httpserver_mdns.py
    :caption: examples/httpserver_mdns.py
    :emphasize-lines: 12-14
    :linenos:

Get CPU information
-------------------

You can return data from sensors or any computed value as JSON.
That makes it easy to use the data in other applications.

If you want to use the data in a web browser, it might be necessary to enable CORS.
More info: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS

.. literalinclude:: ../examples/httpserver_cpu_information.py
    :caption: examples/httpserver_cpu_information.py
    :emphasize-lines: 9,15-18,33
    :linenos:

Handling different methods
---------------------------------------

On every ``server.route()`` call you can specify which HTTP methods are allowed.
By default, only ``GET`` method is allowed.

You can pass a list of methods or a single method as a string.

It is recommended to use the the values in ``adafruit_httpserver.methods`` module to avoid typos and for future proofness.

If you want to route a given path with and without trailing slash, use ``append_slash=True`` parameter.

In example below, handler for ``/api`` and ``/api/`` route will be called when any of ``GET``, ``POST``, ``PUT``, ``DELETE`` methods is used.

.. literalinclude:: ../examples/httpserver_methods.py
    :caption: examples/httpserver_methods.py
    :emphasize-lines: 8,19,26,30,49
    :linenos:

Change NeoPixel color
---------------------

There are several ways to pass data to the handler function:

- In your handler function you can access the query/GET parameters using ``request.query_params``
- You can also access the POST data directly using ``request.body`` or if you data is in JSON format,
  you can use ``request.json()`` to parse it into a dictionary
- Alternatively for short pieces of data you can use URL parameters, which are described later in this document
  For more complex data, it is recommended to use JSON format.

All of these approaches allow you to pass data to the handler function and use it in your code.

For example by going to ``/change-neopixel-color?r=255&g=0&b=0`` or ``/change-neopixel-color/255/0/0``
you can change the color of the NeoPixel to red.
Tested on ESP32-S2 Feather.

.. literalinclude:: ../examples/httpserver_neopixel.py
    :caption: examples/httpserver_neopixel.py
    :emphasize-lines: 26-28,41,52,68,74
    :linenos:

Form data parsing
---------------------

Another way to pass data to the handler function is to use form data.
Remember that it is only possible to use it with ``POST`` method.
`More about POST method. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/POST>`_

It is important to use correct ``enctype``, depending on the type of data you want to send.

- ``application/x-www-form-urlencoded`` - For sending simple text data without any special characters including spaces.
    If you use it, values will be automatically parsed as strings, but special characters will be URL encoded
    e.g. ``"Hello World! ^-$%"`` will be saved as ``"Hello+World%21+%5E-%24%25"``
- ``multipart/form-data`` - For sending textwith special characters and files
    When used, non-file values will be automatically parsed as strings and non plain text files will be saved as ``bytes``.
    e.g. ``"Hello World! ^-$%"`` will be saved as ``'Hello World! ^-$%'``, and e.g. a PNG file will be saved as ``b'\x89PNG\r\n\x1a\n\x00\...``.
- ``text/plain`` - For sending text data with special characters.
    If used, values will be automatically parsed as strings, including special characters, emojis etc.
    e.g. ``"Hello World! ^-$%"`` will be saved as ``"Hello World! ^-$%"``, this is the **recommended** option.

If you pass multiple values with the same name, they will be saved as a list, that can be accessed using ``request.form_data.get_list()``.
Even if there is only one value, it will still get a list, and if there multiple values, but you use ``request.form_data.get()`` it will
return only the first one.

.. literalinclude:: ../examples/httpserver_form_data.py
    :caption: examples/httpserver_form_data.py
    :emphasize-lines: 32,47,50
    :linenos:

Cookies
---------------------

You can use cookies to store data on the client side, that will be sent back to the server with every request.
They are often used to store authentication tokens, session IDs, but also user preferences e.g. theme.

To access cookies, use ``request.cookies`` dictionary.
In order to set cookies,  pass ``cookies`` dictionary to ``Response`` constructor or manually add ``Set-Cookie`` header.

.. literalinclude:: ../examples/httpserver_cookies.py
    :caption: examples/httpserver_cookies.py
    :emphasize-lines: 70,74-75,82
    :linenos:

Chunked response
----------------

Library supports chunked responses. This is useful for streaming large amounts of data.
In order to use it, you need pass a generator that yields chunks of data to a ``ChunkedResponse``
constructor.

.. literalinclude:: ../examples/httpserver_chunked.py
    :caption: examples/httpserver_chunked.py
    :emphasize-lines: 8,21-26,28
    :linenos:

URL parameters and wildcards
----------------------------

Alternatively to using query parameters, you can use URL parameters.
They are a better choice when you want to perform different actions based on the URL.
Query/GET parameters are better suited for modifying the behaviour of the handler function.

Of course it is only a suggestion, you can use them interchangeably and/or both at the same time.

In order to use URL parameters, you need to wrap them inside with angle brackets in ``Server.route``, e.g. ``<my_parameter>``.

All URL parameters values are **passed as keyword arguments** to the handler function.

Notice how the handler function in example below accepts two additional arguments : ``device_id`` and ``action``.

If you specify multiple routes for single handler function and they have different number of URL parameters,
make sure to add default values for all the ones that might not be passed.
In the example below the second route has only one URL parameter, so the ``action`` parameter has a default value.

Keep in mind that URL parameters are always passed as strings, so you need to convert them to the desired type.
Also note that the names of the function parameters **have to match** with the ones used in route, but they **do not have to** be in the same order.

Alternatively you can use e.g. ``**params`` to get all the parameters as a dictionary and access them using ``params['parameter_name']``.

It is also possible to specify a wildcard route:

- ``...`` - matches one path segment, e.g ``/api/...`` will match ``/api/123``, but **not** ``/api/123/456``
- ``....`` - matches multiple path segments, e.g ``/api/....`` will match ``/api/123`` and ``/api/123/456``

In both cases, wildcards will not match empty path segment, so ``/api/.../users`` will match ``/api/v1/users``, but not ``/api//users`` or ``/api/users``.

.. literalinclude:: ../examples/httpserver_url_parameters.py
    :caption: examples/httpserver_url_parameters.py
    :emphasize-lines: 30-34,53-54,65-66
    :linenos:

Authentication
--------------

In order to increase security of your server, you can use ``Basic`` and ``Bearer`` authentication.
Remember that it is **not a replacement for HTTPS**, traffic is still sent **in plain text**, but it can be used to protect your server from unauthorized access.

If you want to apply authentication to the whole server, you need to call ``.require_authentication`` on ``Server`` instance.

.. literalinclude:: ../examples/httpserver_authentication_server.py
    :caption: examples/httpserver_authentication_server.py
    :emphasize-lines: 8,11-16,20
    :linenos:

On the other hand, if you want to apply authentication to a set of routes, you need to call ``require_authentication`` function.
In both cases you can check if ``request`` is authenticated by calling ``check_authentication`` on it.

.. literalinclude:: ../examples/httpserver_authentication_handlers.py
    :caption: examples/httpserver_authentication_handlers.py
    :emphasize-lines: 9-16,22-27,35,49,61
    :linenos:

Redirects
---------

Sometimes you might want to redirect the user to a different URL, either on the same server or on a different one.

You can do that by returning ``Redirect`` from your handler function.

You can specify wheter the redirect is permanent or temporary by passing ``permanent=...``  to ``Redirect``.
If you need the redirect to preserve the original request method, you can set ``preserve_method=True``.

Alternatively, you can pass a ``status`` object directly to ``Redirect`` constructor.

.. literalinclude:: ../examples/httpserver_redirects.py
    :caption: examples/httpserver_redirects.py
    :emphasize-lines: 22-26,32,38,50,62
    :linenos:

Server-Sent Events
------------------

All types of responses until now were synchronous, meaning that the response was sent immediately after the handler function returned.
However, sometimes you might want to send data to the client at a later time, e.g. when some event occurs.
This can be overcomed by periodically polling the server, but it is not an elegant solution. Instead, you can use Server-Sent Events (SSE).

Response is initialized on ``return``, events can be sent using ``.send_event()`` method. Due to the nature of SSE, it is necessary to store the
response object somewhere, so that it can be accessed later.

**Because of the limited number of concurrently open sockets, it is not possible to process more than one SSE response at the same time.
This might change in the future, but for now, it is recommended to use SSE only with one client at a time.**

.. literalinclude:: ../examples/httpserver_sse.py
    :caption: examples/httpserver_sse.py
    :emphasize-lines: 10,17,46-53,63
    :linenos:

Websockets
----------

Although SSE provide a simple way to send data from the server to the client, they are not suitable for sending data the other way around.

For that purpose, you can use Websockets. They are more complex than SSE, but they provide a persistent two-way communication channel between
the client and the server.

Remember, that because Websockets also receive data, you have to explicitly call ``.receive()`` on the ``Websocket`` object to get the message.
This is anologous to calling ``.poll()`` on the ``Server`` object.

The following example uses ``asyncio``, which has to be installed separately. It is not necessary to use ``asyncio`` to use Websockets,
but it is recommended as it makes it easier to handle multiple tasks. It can be used in any of the examples, but here it is particularly useful.

**Because of the limited number of concurrently open sockets, it is not possible to process more than one Websocket response at the same time.
This might change in the future, but for now, it is recommended to use Websocket only with one client at a time.**

.. literalinclude:: ../examples/httpserver_websocket.py
    :caption: examples/httpserver_websocket.py
    :emphasize-lines: 12,20,65-72,88,99
    :linenos:

Multiple servers
----------------

Although it is not the primary use case, it is possible to run multiple servers at the same time.
In order to do that, you need to create multiple ``Server`` instances and call ``.start()`` and ``.poll()`` on each of them.
Using ``.serve_forever()`` for this is not possible because of it's blocking behaviour.

Each server **must have a different port number**.

In order to distinguish between responses from different servers a 'X-Server' header is added to each response.
**This is an optional step**, both servers will work without it.

In combination with separate authentication and diffrent ``root_path`` this allows creating moderately complex setups.
You can share same handler functions between servers or use different ones for each server.

.. literalinclude:: ../examples/httpserver_multiple_servers.py
    :caption: examples/httpserver_multiple_servers.py
    :emphasize-lines: 13-14,16-17,20,28,36-37,48-49,54-55
    :linenos:

Debug mode
----------------

It is highly recommended to **disable debug mode in production**.

During development it is useful to see the logs from the server.
You can enable debug mode by setting ``debug=True`` on ``Server`` instance or in constructor,
it is disabled by default.

Debug mode prints messages on server startup, after sending a response to a request and if exception
occurs during handling of the request in ``.serve_forever()``.

This is how the logs might look like when debug mode is enabled::

    Started development server on http://192.168.0.100:80
    192.168.0.101 -- "GET /" 194 -- "200 OK" 154 -- 96ms
    192.168.0.101 -- "GET /example" 134 -- "404 Not Found" 172 -- 123ms
    192.168.0.102 -- "POST /api" 1241 -- "401 Unauthorized" 95 -- 64ms
    Traceback (most recent call last):
        ...
        File "code.py", line 55, in example_handler
    KeyError: non_existent_key
    192.168.0.103 -- "GET /index.html" 242 -- "200 OK" 154 -- 182ms
    Stopped development server

This is the default format of the logs::

    {client_ip} -- "{request_method} {path}" {request_size} -- "{response_status}" {response_size} -- {elapsed_ms}

If you need more information about the server or request, or you want it in a different format you can modify
functions at the bottom of ``adafruit_httpserver/server.py`` that start with ``_debug_...``.

NOTE:
*This is an advanced usage that might change in the future. It is not recommended to modify other parts of the code.*
