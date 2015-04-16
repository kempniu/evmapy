evmapy
======

.. image:: https://img.shields.io/travis/kempniu/evmapy.svg
   :target: https://travis-ci.org/kempniu/evmapy

.. image:: https://img.shields.io/coveralls/kempniu/evmapy.svg
   :target: https://coveralls.io/r/kempniu/evmapy

Summary
-------

*evmapy* is an evdev event mapper written in Python. This mumbo-jumbo translates into English as "an application for the Linux operating system capable of performing arbitrary actions upon detecting certain input events".

In layman's terms, this piece of software enables you to make your system think you pressed a button on the keyboard when you move an analog stick on your joypad or run a program of your choosing when you hold your computer's power button.

Requirements
------------

- Linux kernel with evdev and uinput support (virtually all kernels packaged for modern Linux distributions have it)
- `Python`_ 3.3+
- `python-evdev`_

Features
--------

- Works with any evdev-compatible input device, from a power button to a 6-axis joypad
- Automatic input device configuration generation
- Runs in foreground or as a daemon (using external software like ``start-stop-daemon``)
- Dynamic event map switching
- Adding and removing devices on-the-fly
- Supported events:

  - key/button presses
  - absolute events (e.g. analog stick movements)

- Supported actions:

  - key press injection
  - external program execution

- Supported action triggers:

  - press
  - hold

Installation
------------

*evmapy* is not currently available through `PyPI`_, so you'll need to handle it manually:

::

  pip install evdev
  git clone https://github.com/kempniu/evmapy.git
  cd evmapy
  python3 setup.py test

**NOTE:** Commands for your favorite Linux distribution may be a bit different, e.g. you might have to use ``pip3`` instead of ``pip`` etc.

If you get any errors from running the last command (and you're positive you're running Python 3.3+), please let me know.

Now, to play with the package without installing it, invoke it in the following way:

::

  python3 -m evmapy

If you decide to install it in your system, run:

::

  python3 setup.py install


and it will be available simply as *evmapy*.

Crash course
------------

::

  # evmapy --list
  /dev/input/event0: Power Button
  /dev/input/event1: Power Button
  /dev/input/event2: Video Bus
  /dev/input/event3: Logitech Logitech Cordless RumblePad 2
  # evmapy --generate /dev/input/event3
  # vim ~/.evmapy/Logitech.Logitech.Cordless.RumblePad.2.json
  # evmapy
  evmapy 1.0 initializing
  running as user root
  using configuration directory /root/.evmapy
  scanning devices...
  /dev/input/event3: loaded /root/.evmapy/Logitech.Logitech.Cordless.RumblePad.2.json
  handling 1 device(s)

**NOTE:** *evmapy* doesn't need to be run with root privileges as long as the user you're running it as is allowed to both read from ``/dev/input/eventX`` and write to ``/dev/uinput``. However, running it as root for testing purposes is a good way to make sure you're not facing a permissions-related issue.

**NOTE:** Use ``python3 -m evmapy`` instead of ``evmapy`` if you haven't installed the package in your system yet.

If all goes well, pressing any button on your input device will cause the default name of that button to be printed to the console.

Configuration
-------------

Event maps are read from JSON files. You can generate an example configuration file automatically using the ``--generate DEVICE`` command line option. Each configuration file is a representation of an object with the following properties:

- *axes*: list of input device axes *evmapy* will monitor, each of which must have exactly 2 actions assigned:

  - *min*: performed when the value of this axis is the lowest possible one,
  - *max*: performed when the value of this axis is the highest possible one,

- *buttons*: list of input device keys/buttons *evmapy* will monitor, each of which must have only a single *press* action assigned,
- *grab*: set it to ``True`` if you want *evmapy* to become the only recipient of the events emitted by this input device.

**NOTE:** Don't forget that a typical analog stick on a joypad consists of 2 axes (horizontal and vertical)!

Each action has 3 parameters you can set (don't touch the rest unless you know what you're doing):

- *type*:

  - *key*: event will be translated to a key press,
  - *exec*: event will cause an external program to be executed,

- *target*:

  - if *type* is *key*: the key(s) to "press" (see ``/usr/include/linux/input.h`` for a list of valid values),
  - if *type* is *exec*: the command(s) to run,

- *trigger*:

  - *normal*: action will be performed immediately,
  - *long*: action will only be performed once the event has been active for 1 second (i.e. you keep a key/button pressed or an analog stick tilted for that long).

Each axis and button has 2 more properties:

- *alias*: set it to whatever you want to (stay JSON compliant, though!),
- *code*: don't touch it (*evmapy* relies on it for proper functioning).

If all this sounds too complicated, here are some examples to clear things up:

- Translate *Button 1* presses to *ALT+ENTER* presses

  ::

    "buttons" = [
        {
            "alias": "Button 1",
            "code": 304,
            "press": {
                "type": "key"
                "target": [ "KEY_LEFTALT", "KEY_ENTER" ],
                "trigger": "normal",
            }
        },
    ...
    ]

- Shutdown system when *Right analog stick* is tilted to the left for 1 second

  ::

    "axes": [
        {
            "alias": "Right analog stick (horizontal)",
            "code": 4,
            "min": {
                "type": "exec",
                "target": "shutdown -h now",
                "trigger": "long",
                "value": 0
            }
        },
    ...
    ]

How do I...
-----------

- *...change the event map for a given device?*

  Use the ``--configure DEVICE:FILE`` command line option. ``FILE`` has to exist in ``~/.evmapy``. If you don't specify ``FILE``, default configuration will be restored for ``DEVICE``.

  ::

    # Load configuration file ~/.evmapy/foo.json for /dev/input/event0
    evmapy --configure /dev/input/event0:foo.json
    # Restore default configuration for /dev/input/event1
    evmapy --configure /dev/input/event1:

- *...rescan available devices?*

  Send a *SIGHUP* signal to *evmapy*.

  **HINT:** You can automatically signal *evmapy* when a new input device is plugged in using a udev rule similar to the following:

  ::

    ACTION=="add", KERNEL=="event[0-9]*", RUN+="/usr/local/bin/signal-evmapy.sh"

- *...shutdown the application cleanly?*

  Send a *SIGINT* signal to it (if it's running in the foreground, *CTRL+C* will do).

- *...diagnose why the application doesn't react to events the way I want it to?*

  You can try running it with the ``--debug`` command line option. This will cause *evmapy* to print information about every event received from any handled input device. If you see the events coming, but the actions you expect aren't performed, double-check your configuration first and if this doesn't help, feel free to contact me.

- *...run it as a daemon?*

  I wanted to keep the source code as clean as possible and to avoid depending on third party Python modules which aren't absolutely necessary, so there is no "daemon mode" implementation *per se* in *evmapy*. Instead, please use the relevant tools available in your favorite distribution, like ``start-stop-daemon``:

  ::

    start-stop-daemon --start --background --pidfile /run/evmapy.pid --make-pidfile --exec /usr/bin/evmapy
    start-stop-daemon --stop --pidfile /run/evmapy.pid --retry INT/5/KILL/5

  When running in the background, *evmapy* will output its messages to syslog (``LOG_DAEMON`` facility).

Code maturity
-------------

*evmapy* is a young project and it hasn't been tested widely. While evdev and uinput are powerful mechanisms which put virtually no limits on their applications, *evmapy* was implemented to solve a specific problem, so you are likely to find it lacking in its current form. Unfortunately, I don't have enough spare time at the moment to turn it into a full-blown project. I decided to publish it nevertheless as it may scratch your itch as well as it did mine and if it doesn't, you are free to modify it for your own needs.

Coding principles
-----------------

- Strict `PEP 8`_ conformance
- Try not to make `Pylint`_ angry
- Document all the things!
- 100% unit test code coverage

History
-------

A while ago, I felt a sudden urge to play a bunch of old games on a TV, using a wireless joypad. `DOSBox`_  and `FCEUX`_ themselves worked fine, but for long-forgotten reasons I wasn't entirely happy with their joypad support. The solution I came up with back then was using `joy2key`_ to translate joypad actions into key presses as both emulators supported keyboard input out of the box (obviously) and without any glitches. But creating `joy2key` configuration files and finding correct X window IDs to send events to was a real ordeal.

Fast forward a few years, I started using a joypad to control `Kodi`_, a cross-platform media center solution. While this combo was working great *after* the application was already launched, it got me thinking: how do I launch Kodi, or any program for that matter, using just the joypad? I haven't found a single solution to that problem, which surprised me as, thanks to evdev, it is trivially easy to receive input events generated by the joypad in user space.

This adversity reminded me of the other joypad issues I had faced in the past and I got frustrated that I can't just easily use the joypad the way I want. That frustration became the motivation for creating *evmapy*.

License
-------

*evmapy* is released under the `GPLv2`_.

.. _Python: https://www.python.org/
.. _python-evdev: http://python-evdev.readthedocs.org/en/latest/
.. _PyPI: https://pypi.python.org/
.. _DOSBox: http://www.dosbox.com/
.. _FCEUX: http://www.fceux.com/
.. _joy2key: http://sourceforge.net/projects/joy2key/
.. _Kodi: http://kodi.tv/
.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. _Pylint: http://www.pylint.org/
.. _GPLv2: https://www.gnu.org/licenses/gpl-2.0.html
