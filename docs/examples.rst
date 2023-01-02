Simple file serving
-------------------

Serving the content of index.html from the filesystem.

.. literalinclude:: ../examples/httpserver_simple_serve.py
    :caption: examples/httpserver_simple_serve.py
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

.. literalinclude:: ../examples/httpserver_cpu_information.py
    :caption: examples/httpserver_cpu_information.py
    :linenos:

Change NeoPixel color
---------------------

If you want your code to do more than just serve web pages,
use the start/poll methods as shown in this example.

For example by going to ``/change-neopixel-color?r=255&g=0&b=0`` you can change the color of the NeoPixel to red.
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
