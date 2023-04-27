Simple Test
-------------------

Serving a simple static text message.

.. literalinclude:: ../examples/httpserver_simpletest.py
    :caption: examples/httpserver_simpletest.py
    :linenos:

If you want your code to do more than just serve web pages,
use the ``.start()``/``.poll()`` methods as shown in this example.

Between calling ``.poll()`` you can do something useful,
for example read a sensor and capture an average or
a running total of the last 10 samples.

.. literalinclude:: ../examples/httpserver_simple_poll.py
    :caption: examples/httpserver_simple_poll.py
    :linenos:

Server with MDNS
----------------

It is possible to use the MDNS protocol to make the server
accessible via a hostname in addition to an IP address.

In this example, the server is accessible via ``http://custom-mdns-hostname/`` and ``http://custom-mdns-hostname.local/``.

.. literalinclude:: ../examples/httpserver_mdns.py
    :caption: examples/httpserver_mdns.py
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
---------------------

You can return data from sensors or any computed value as JSON.
That makes it easy to use the data in other applications.

.. literalinclude:: ../examples/httpserver_cpu_information.py
    :caption: examples/httpserver_cpu_information.py
    :linenos:

Chunked response
---------------------

Library supports chunked responses. This is useful for streaming data.
To use it, you need to set the ``chunked=True`` when creating a ``HTTPResponse`` object.

.. literalinclude:: ../examples/httpserver_chunked.py
    :caption: examples/httpserver_chunked.py
    :linenos:

URL parameters
---------------------

Alternatively to using query parameters, you can use URL parameters.

In order to use URL parameters, you need to wrap them inside ``<>`` in ``HTTPServer.route``, e.g. ``<my_parameter>``.

All URL parameters are **passed as positional (not keyword) arguments** to the handler function, in order they are specified in ``HTTPServer.route``.

Notice how the handler function in example below accepts two additional arguments : ``device_id`` and ``action``.

If you specify multiple routes for single handler function and they have different number of URL parameters,
make sure to add default values for all the ones that might not be passed.
In the example below the second route has only one URL parameter, so the ``action`` parameter has a default value.

Keep in mind that URL parameters are always passed as strings, so you need to convert them to the desired type.
Also note that the names of the function parameters **do not have to match** with the ones used in route, but they **must** be in the same order.
Look at the example below to see how the ``route_param_1`` and ``route_param_1`` are named differently in the handler function.

Although it is possible, it makes more sense be consistent with the names of the parameters in the route and in the handler function.

.. literalinclude:: ../examples/httpserver_url_parameters.py
    :caption: examples/httpserver_url_parameters.py
    :linenos:
