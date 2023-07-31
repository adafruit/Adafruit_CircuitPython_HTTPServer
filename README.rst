Introduction
============


.. image:: https://readthedocs.org/projects/adafruit-circuitpython-httpserver/badge/?version=latest
    :target: https://docs.circuitpython.org/projects/httpserver/en/latest/
    :alt: Documentation Status


.. image:: https://raw.githubusercontent.com/adafruit/Adafruit_CircuitPython_Bundle/main/badges/adafruit_discord.svg
    :target: https://adafru.it/discord
    :alt: Discord


.. image:: https://github.com/adafruit/Adafruit_CircuitPython_HTTPServer/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_CircuitPython_HTTPServer/actions
    :alt: Build Status


.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black
    :alt: Code Style: Black

HTTP Server for CircuitPython.

- Supports `socketpool` or `socket` as a source of sockets; can be used in CPython.
- HTTP 1.1.
- Serves files from a designated root.
- Routing for serving computed responses from handlers.
- Gives access to request headers, query parameters, form data, body and client's address (the one from which the request came).
- Supports chunked transfer encoding.
- Supports URL parameters and wildcard URLs.
- Supports HTTP Basic and Bearer Authentication on both server and route per level.
- Supports Websockets and Server-Sent Events.


Dependencies
=============
This driver depends on:

* `Adafruit CircuitPython <https://github.com/adafruit/circuitpython>`_

Please ensure all dependencies are available on the CircuitPython filesystem.
This is easily achieved by downloading
`the Adafruit library and driver bundle <https://circuitpython.org/libraries>`_
or individual libraries can be installed using
`circup <https://github.com/adafruit/circup>`_.


Installing from PyPI
=====================
On supported GNU/Linux systems like the Raspberry Pi, you can install the driver locally `from
PyPI <https://pypi.org/project/adafruit-circuitpython-httpserver/>`_.
To install for current user:

.. code-block:: shell

    pip3 install adafruit-circuitpython-httpserver

To install system-wide (this may be required in some cases):

.. code-block:: shell

    sudo pip3 install adafruit-circuitpython-httpserver

To install in a virtual environment in your current project:

.. code-block:: shell

    mkdir project-name && cd project-name
    python3 -m venv .venv
    source .venv/bin/activate
    pip3 install adafruit-circuitpython-httpserver



Installing to a Connected CircuitPython Device with Circup
==========================================================

Make sure that you have ``circup`` installed in your Python environment.
Install it with the following command if necessary:

.. code-block:: shell

    pip3 install circup

With ``circup`` installed and your CircuitPython device connected use the
following command to install:

.. code-block:: shell

    circup install adafruit_httpserver

Or the following command to update an existing version:

.. code-block:: shell

    circup update

Security
========

The HTTP server implementation in this package is not robust and should only be deployed on trusted networks.
For instance, there are trivial denial of service attacks against adafruit_httpserver.
Pull requests that improve the server's security and robustness are of course welcome.

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_CircuitPython_HTTPServer/blob/HEAD/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

Documentation
=============
API documentation for this library can be found on `Read the Docs <https://docs.circuitpython.org/projects/httpserver/en/latest/>`_.

For information on building library documentation, please check out
`this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.
