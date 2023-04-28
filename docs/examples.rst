Simple Test
-----------

This is the minimal example of using the library.
This example is serving a simple static text message.

It also manually connects to the WiFi network.

.. literalinclude:: ../examples/httpserver_simpletest_manual.py
    :caption: examples/httpserver_simpletest_manual.py
    :linenos:

Although there is nothing wrong with this approach, from the version 8.0.0 of CircuitPython,
`it is possible to use the environment variables <https://docs.circuitpython.org/en/latest/docs/environment.html#circuitpython-behavior>`_
defined in ``settings.toml`` file to store secrets and configure the WiFi network.

This is the same example as above, but it uses the ``settings.toml`` file to configure the WiFi network.

**From now on, all the examples will use the** ``settings.toml`` **file to configure the WiFi network.**

.. literalinclude:: ../examples/settings.toml
    :caption: settings.toml
    :linenos:

Note that we still need to import ``socketpool`` and ``wifi`` modules.

.. literalinclude:: ../examples/httpserver_simpletest_auto.py
    :caption: examples/httpserver_simpletest_auto.py
    :linenos:

Serving static files
--------------------

It is possible to serve static files from the filesystem.
In this example we are serving files from the ``/static`` directory.

In order to save memory, we are unregistering unused MIME types and registering additional ones.
`More about MIME types. <https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types>`_

.. literalinclude:: ../examples/httpserver_static_files_serving.py
    :caption: examples/httpserver_static_files_serving.py
    :linenos:

You can also serve a specific file from the handler.
By default ``Response.send_file()`` looks for the file in the server's ``root_path`` directory, but you can change it.

.. literalinclude:: ../examples/httpserver_handler_serves_file.py
    :caption: examples/httpserver_handler_serves_file.py
    :linenos:

.. literalinclude:: ../examples/home.html
    :language: html
    :caption: www/home.html
    :linenos:

Tasks in the background
-----------------------

If you want your code to do more than just serve web pages,
use the ``.start()``/``.poll()`` methods as shown in this example.

Between calling ``.poll()`` you can do something useful,
for example read a sensor and capture an average or
a running total of the last 10 samples.

.. literalinclude:: ../examples/httpserver_start_and_poll.py
    :caption: examples/httpserver_start_and_poll.py
    :linenos:

Server with MDNS
----------------

It is possible to use the MDNS protocol to make the server
accessible via a hostname in addition to an IP address.

In this example, the server is accessible via ``http://custom-mdns-hostname/`` and ``http://custom-mdns-hostname.local/``.

.. literalinclude:: ../examples/httpserver_mdns.py
    :caption: examples/httpserver_mdns.py
    :linenos:

Handling different methods
---------------------------------------

On every ``server.route()`` call you can specify which HTTP methods are allowed.
By default, only ``GET`` method is allowed.

You can pass a list of methods or a single method as a string.

It is recommended to use the the values in ``adafruit_httpserver.methods`` module to avoid typos and for future proofness.

In example below, handler for ``/api`` route will be called when any of ``GET``, ``POST``, ``PUT``, ``DELETE`` methods is used.

.. literalinclude:: ../examples/httpserver_methods.py
    :caption: examples/httpserver_methods.py
    :linenos:

Change NeoPixel color
---------------------

If you want your code to do more than just serve web pages,
use the start/poll methods as shown in this example.

For example by going to ``/change-neopixel-color?r=255&g=0&b=0`` or ``/change-neopixel-color/255/0/0``
you can change the color of the NeoPixel to red.
Tested on ESP32-S2 Feather.

.. literalinclude:: ../examples/httpserver_neopixel.py
    :caption: examples/httpserver_neopixel.py
    :linenos:

Get CPU information
-------------------

You can return data from sensors or any computed value as JSON.
That makes it easy to use the data in other applications.

.. literalinclude:: ../examples/httpserver_cpu_information.py
    :caption: examples/httpserver_cpu_information.py
    :linenos:

Chunked response
----------------

Library supports chunked responses. This is useful for streaming data.
To use it, you need to set the ``chunked=True`` when creating a ``Response`` object.

.. literalinclude:: ../examples/httpserver_chunked.py
    :caption: examples/httpserver_chunked.py
    :linenos:

URL parameters
--------------

Alternatively to using query parameters, you can use URL parameters.

In order to use URL parameters, you need to wrap them inside ``<>`` in ``Server.route``, e.g. ``<my_parameter>``.

All URL parameters values are **passed as keyword arguments** to the handler function.

Notice how the handler function in example below accepts two additional arguments : ``device_id`` and ``action``.

If you specify multiple routes for single handler function and they have different number of URL parameters,
make sure to add default values for all the ones that might not be passed.
In the example below the second route has only one URL parameter, so the ``action`` parameter has a default value.

Keep in mind that URL parameters are always passed as strings, so you need to convert them to the desired type.
Also note that the names of the function parameters **have to match** with the ones used in route, but they **do not have to** be in the same order.

.. literalinclude:: ../examples/httpserver_url_parameters.py
    :caption: examples/httpserver_url_parameters.py
    :linenos:

Authentication
--------------

In order to increase security of your server, you can use ``Basic`` and ``Bearer`` authentication.

If you want to apply authentication to the whole server, you need to call ``.require_authentication`` on ``Server`` instance.

.. literalinclude:: ../examples/httpserver_authentication_server.py
    :caption: examples/httpserver_authentication_server.py
    :linenos:

On the other hand, if you want to apply authentication to a set of routes, you need to call ``require_authentication`` function.
In both cases you can check if ``request`` is authenticated by calling ``check_authentication`` on it.

.. literalinclude:: ../examples/httpserver_authentication_handlers.py
    :caption: examples/httpserver_authentication_handlers.py
    :linenos:
