.. image:: https://img.shields.io/travis/kempniu/evmapy/master.svg
   :target: https://travis-ci.org/kempniu/evmapy

.. image:: https://img.shields.io/coveralls/kempniu/evmapy/master.svg
   :target: https://coveralls.io/r/kempniu/evmapy

evmapy
======

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
- Dynamic configuration switching
- Adding and removing devices on-the-fly
- Runs in foreground or as a daemon (using external software like ``start-stop-daemon``)
- Supported events:

  - key/button presses
  - absolute events (e.g. analog stick movements)

- Supported actions:

  - key press injection
  - external program execution

- Supported action triggering modes:

  - single event, immediate
  - single event, hold
  - combined events, immediate
  - combined events, hold
  - sequence of events, immediate

Installation
------------

*evmapy* is **not** currently available through `PyPI`_, so you'll need to handle it manually:

::

  pip3 install evdev
  git clone https://github.com/kempniu/evmapy.git
  cd evmapy
  python3 setup.py test

**NOTE:** Commands for your favorite Linux distribution may be a bit different, e.g. you might have to use ``pip`` instead of ``pip3`` etc.

If you get any errors from running the last command (and you're positive you're running Python 3.3+), please let me know.

Now, to play with the package without installing it, invoke it in the following way:

::

  python3 -m evmapy

If you decide to install it in your system, run:

::

  python3 setup.py install


and it will be available simply as ``evmapy``.

Crash course
------------

::

  # evmapy --list-all
  /dev/input/event3: Logitech Logitech Cordless RumblePad 2
  /dev/input/event2: Video Bus
  /dev/input/event1: Power Button
  /dev/input/event0: Power Button
  # evmapy --generate /dev/input/event3
  # vim ~/.evmapy/Logitech.Logitech.Cordless.RumblePad.2.json
  # evmapy
  evmapy 1.0 initializing
  running as user root
  using configuration directory /root/.evmapy
  scanning devices...
  /dev/input/event3: loaded /root/.evmapy/Logitech.Logitech.Cordless.RumblePad.2.json
  handling 1 device(s)

**NOTE:** *evmapy* doesn't need to be run with root privileges as long as the user you're running it as is allowed to read from ``/dev/input/eventX``. However, running it as root for testing purposes is a good way to make sure you're not facing a permissions-related issue.

**NOTE:** Use ``python3 -m evmapy`` instead of ``evmapy`` if you haven't installed the package in your system yet.

If all goes well, pressing any button on your input device will cause the default name of that button to be printed to the console.

Configuration
-------------

Configuration is stored in JSON files. You can generate one automatically using the ``--generate DEVICE`` command line option (or ``--generate-minimal DEVICE`` if you don't want the default actions to be generated). Each configuration file is a representation of an object with the following (mandatory) properties:

- *actions*: actions to take in response to events; each action has the following properties:

  - *trigger*: value(s) of the *name* property(-ies) of the event(s) which trigger(s) this action (*:min* or *:max* suffix is required for axes),
  - *type*:

    - *key*: event(s) will be translated to a key press,
    - *exec*: event(s) will cause an external program to be executed,

  - *target*:

    - if *type* is *key*: the key(s) to "press" (see ``/usr/include/linux/input.h`` for a list of valid values),
    - if *type* is *exec*: the command(s) to run,

  - *(optional) mode*: triggering mode for actions with *trigger* containing more than one event:

    - *all (default)*: *trigger* will be treated as a combination of events,
    - *sequence*: *trigger* will be treated as a sequence of events,
    - *any*: *trigger* will be treated as a list of alternative events, any of which causes the action to be performed,

  - *(optional) hold*: if set to a positive value (which is only allowed when *mode* is **not** *sequence*), this action will only be triggered once sufficient triggers will have been active for the given number of seconds; otherwise, it will be triggered immediately once sufficient triggers are active; this value is a floating point number, i.e. fractions of seconds can be used; defaults to *0* (i.e. immediate triggering),

- *grab*: if set to *true*, *evmapy* will become the only recipient of the events emitted by this input device.

The following properties are only required to be set in the initial configuration file for a device:

- *axes*: list of input device axes, each of which must have all of the following properties assigned:

  - *name*: user-friendly name of this axis,
  - *code*: don't touch it (*evmapy* relies on it for proper functioning),
  - *min*: lowest possible value of this axis,
  - *max*: highest possible value of this axis,

  **NOTE:** Don't forget that a typical analog stick on a joypad consists of 2 axes (horizontal and vertical)!

- *buttons*: list of input device keys/buttons, each of which must have all of the following properties assigned:

  - *name*: see *axes*,
  - *code*: see *axes*.

If all this sounds too complicated, here are some examples to clear things up:

- Translate *Button 1* presses to *ALT+ENTER* presses

  ::

    "actions": [
        {
            "trigger": "Button 1",
            "type": "key",
            "target": [ "KEY_LEFTALT", "KEY_ENTER" ]
        },
    ...
    ],
    "buttons": [
        {
            "name": "Button 1",
            "code": 304
        },
    ...
    ]

- Shutdown system when *Right analog stick* is tilted to the left for 1 second

  ::

    "actions": [
        {
            "trigger": "Right analog stick (horizontal):min",
            "hold": 1.0,
            "type": "exec",
            "target": "shutdown -h now"
        },
    ...
    ],
    "axes": [
        {
            "name": "Right analog stick (horizontal)",
            "code": 4,
            "min": 0,
            "max": 255
        },
    ...
    ]

- Translate *SHIFT+Q* presses to *ESC* presses

  ::

    "actions": [
        {
            "trigger": [ "SHIFT", "Q" ],
            "type": "key",
            "target": "KEY_ESC"
        },
    ...
    ],
    "buttons": [
        {
            "name": "SHIFT",
            "code": 42
        },
        {
            "name": "Q",
            "code": 16
        },
    ...
    ]

- Send *ALT+CTRL+DEL* when you make a circular, clockwise motion with an analog stick

  ::

    "actions": [
        {
            "trigger": [ "L-R:min", "U-D:min", "L-R:max", "U-D:max" ],
            "mode": "sequence",
            "type": "key",
            "target": [ "KEY_LEFTALT", "KEY_LEFTCTRL", "KEY_DELETE" ]
        },
    ...
    ],
    "axes": [
        {
            "name": "L-R",
            "code": 0,
            "min": 0,
            "max": 255
        },
        {
            "name": "U-D",
            "code": 1,
            "min": 0,
            "max": 255
        },
    ...
    ]

- Print ``yo`` to all user terminals when either *Y* or *O* is pressed

  ::

    "actions": [
        {
            "trigger": [ "Y", "O" ],
            "mode": "any",
            "type": "exec",
            "target": "echo yo | wall"
        },
    ...
    ],
    "buttons": [
        {
            "name": "Y",
            "code": 21
        },
        {
            "name": "O",
            "code": 24
        },
    ...
    ]

How do I...
-----------

- *...change the configuration for a given device?*

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

    ACTION=="add", KERNEL=="event[0-9]*", RUN+="/usr/bin/pkill -HUP -f evmapy"

- *...shutdown the application cleanly?*

  Send a *SIGINT* signal to it (if it's running in the foreground, *CTRL+C* will do).

- *...diagnose why the application doesn't react to events the way I want it to?*

  If you're expecting *evmapy* to inject keypresses, make sure the user you're running it as is allowed to **write** to ``/dev/uinput`` - *evmapy* warns you upon its startup if it encounters a problem with that. If that's not your case, you can try running *evmapy* with the ``--debug`` command line option. This will cause every event received from any handled input device to be logged, along with any actions *evmapy* is attempting to perform. If you see the events coming, but the actions you expect aren't performed, double-check your configuration first and if this doesn't help, feel free to contact me.

- *...run it as a daemon?*

  I wanted to keep the source code as clean as possible and to avoid depending on third party Python modules which aren't absolutely necessary, so there is no "daemon mode" implementation *per se* in *evmapy*. Instead, please use the relevant tools available in your favorite distribution, like ``start-stop-daemon``:

  ::

    start-stop-daemon --start --background --pidfile /run/evmapy.pid --make-pidfile --exec /usr/bin/evmapy
    start-stop-daemon --stop --pidfile /run/evmapy.pid --retry INT/5/KILL/5

  When running in the background, *evmapy* will output its messages to syslog (``LOG_DAEMON`` facility).

- *...run it as a systemd service?*

  You can use the following service file as a starting point:

  ::

    [Unit]
    Description=evdev event mapper

    [Service]
    #User=nobody
    ExecStart=/usr/bin/evmapy
    ExecReload=/usr/bin/kill -HUP $MAINPID

    [Install]
    WantedBy=multi-user.target

  This enables you to initiate a device rescan using ``systemctl reload evmapy``.

- *...run it automatically when my X session starts?*

  Put the following contents in ``/etc/xdg/autostart/evmapy.desktop``:

  ::

    [Desktop Entry]
    Version=1.0
    Type=Application
    Name=evmapy
    Comment=evdev event mapper
    Exec=/usr/bin/evmapy

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
