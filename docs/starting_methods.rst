
Manual WiFi
-----------

This is the minimal example of using the library with CircuitPython.
This example is serving a simple static text message.

It also manually connects to the WiFi network. SSID and password are stored in the code, but they
can as well be stored in the ``settings.toml`` file, and then read from there using ``os.getenv()``.

.. literalinclude:: ../examples/httpserver_simpletest_manual_wifi.py
    :caption: examples/httpserver_simpletest_manual_wifi.py
    :emphasize-lines: 10-17
    :linenos:

Manual AP (access point)
------------------------

If there is no external network available, it is possible to create an access point (AP) and run a server on it.
It is important to note that only devices connected to the AP will be able to access the server and depending on the device,
it may not be able to access the internet.

.. literalinclude:: ../examples/httpserver_simpletest_manual_ap.py
    :caption: examples/httpserver_simpletest_manual_ap.py
    :emphasize-lines: 11-16,30
    :linenos:

Manual Ethernet
---------------

Most of the time, the WiFi will be a preferred way of connecting to the network.
Nevertheless it is also possible to use Ethernet instead of WiFi.
The only difference in usage is related to configuring the ``socket_source`` differently.

.. literalinclude:: ../examples/httpserver_simpletest_manual_ethernet.py
    :caption: examples/httpserver_simpletest_manual_ethernet.py
    :emphasize-lines: 9-10,13-25,38
    :linenos:

Automatic WiFi using ``settings.toml``
--------------------------------------

From the version 8.0.0 of CircuitPython,
`it is possible to use the environment variables <https://docs.circuitpython.org/en/latest/docs/environment.html#circuitpython-behavior>`_
defined in ``settings.toml`` file to store secrets and configure the WiFi network
using the ``CIRCUITPY_WIFI_SSID`` and ``CIRCUITPY_WIFI_PASSWORD`` variables.

By default the library uses ``0.0.0.0`` and port ``5000`` for the server, as port ``80`` is reserved for the CircuitPython Web Workflow.
If you want to use port ``80`` , you need to set ``CIRCUITPY_WEB_API_PORT`` to any other port, and then set ``port`` parameter in ``Server`` constructor to ``80`` .

This is the same example as above, but it uses the ``settings.toml`` file to configure the WiFi network.

.. note::
    From now on, all the examples will use the ``settings.toml`` file to configure the WiFi network.

.. literalinclude:: ../examples/settings.toml
    :caption: settings.toml
    :lines: 5-
    :linenos:

Note that we still need to import ``socketpool`` and ``wifi`` modules.

.. literalinclude:: ../examples/httpserver_simpletest_auto_settings_toml.py
    :caption: examples/httpserver_simpletest_auto_settings_toml.py
    :emphasize-lines: 11
    :linenos:


Helper for socket pool using ``adafruit_connection_manager``
------------------------------------------------------------

If you do not want to configure the socket pool manually, you can use the ``adafruit_connection_manager`` library,
which provides helpers for getting socker pool and SSL context for common boards.

Note that it is not installed by default.
You can read `more about the it here <https://docs.circuitpython.org/projects/connectionmanager/en/latest/index.html>`_.


.. literalinclude:: ../examples/httpserver_simpletest_auto_connection_manager.py
    :caption: examples/httpserver_simpletest_auto_connection_manager.py
    :emphasize-lines: 7,11
    :linenos:
