#
# Copyright (C) 2015 Michał Kępień <github@kempniu.pl>
#
# This file is part of evmapy.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

"""
:py:class:`EventMultiplexer` class implementation
"""

import logging
import os
import select
import signal
import time

import evdev

import evmapy.source
import evmapy.util


def _execute_program(action):
    """
    Run external program(s) associated with the given action.

    :param action: action dictionary containing a `target` key which
        specifies the command(s) to be run
    :type action: dict
    :returns: None
    """
    commands = evmapy.util.as_list(action['target'])
    for command in commands:
        os.system(command)


class SIGHUPReceivedException(Exception):
    """
    Exception raised when a SIGHUP signal is received.
    """
    pass


class EventMultiplexer(object):

    """
    Class monitoring multiple file descriptors for incoming data. These
    file descriptors are both evdev descriptors and Unix domain sockets
    which enable :py:class:`evmapy.source.EventSource` instances to be
    dynamically reconfigured.  Whenever any monitored descriptor is
    ready for reading, it is passed to its associated
    :py:class:`evmapy.source.EventSource` for processing. If the result
    of this processing in an action list, these actions are then
    performed.
    """

    def __init__(self):
        self._fds = {}
        self._delayed = []
        self._logger = logging.getLogger()
        self._poll = None
        self._uinput = None
        try:
            # Open /dev/uinput for future use
            info = evmapy.util.get_app_info()
            app_with_pid = '%s[%d]' % (info['name'], os.getpid())
            self._uinput = evdev.UInput(name=app_with_pid)
            # Start processing events from all configured devices
            self._poll = select.poll()
            self._scan_devices()
        except:
            self._logger.exception("unhandled exception while initializing:")
            raise

    @property
    def devices(self):
        """
        Return a list of handled :py:class:`evmapy.source.EventSource`
        instances.

        :returns: list of handled :py:class:`evmapy.source.EventSource`
            instances
        :rtype: set
        """
        return set(self._fds.values())

    def _log_device_count(self):
        """
        Log the number of currently handled devices.

        :returns: None
        """
        self._logger.info("handling %d device(s)", len(self.devices))

    def _scan_devices(self):
        """
        Scan all evdev devices in the system and attempt to subscribe to
        their events.

        :returns: None
        """
        self._logger.info("scanning devices...")
        processed_devices = [source.device['path'] for source in self.devices]
        for dev_path in evdev.list_devices():
            if dev_path not in processed_devices:
                self._add_device(dev_path)
        self._log_device_count()

    def _add_device(self, path):
        """
        Start processing events emitted by the device under the given
        path.

        :param path: path to device whose events to listen to
        :type path: str
        :returns: None
        """
        device = evdev.InputDevice(path)
        self._logger.debug("trying to add %s (%s)", device.fn, device.name)
        try:
            source = evmapy.source.EventSource(device)
            for fdesc in source.fds.values():
                self._fds[fdesc] = source
                self._poll.register(fdesc, select.POLLIN)
        except evmapy.config.ConfigError as exc:
            if not exc.not_found:
                self._logger.error(str(exc))

    def _remove_device(self, source, quiet=False):
        """
        Stop processing events emitted by the device associated with the
        given event source.

        :param source: event source to stop listening to
        :type source: :py:class:`evmapy.source.EventSource`
        :param quiet: whether to log device removal or not
        :type quiet: bool
        :returns: None
        """
        for fdesc in source.fds.values():
            del self._fds[fdesc]
            self._poll.unregister(fdesc)
        source.cleanup()
        if not quiet:
            self._logger.info("removed %(path)s (%(name)s)", source.device)
            self._log_device_count()

    def run(self):
        """
        Run a :py:meth:`select.poll.poll()` loop while handling
        exceptions nicely.

        :returns: None
        """
        try:
            self._run()
        except KeyboardInterrupt:
            self._logger.info("user requested shutdown")
        except:
            self._logger.exception("unhandled exception:")
            raise
        finally:
            # Always cleanup, even if an unhandled exception was raised
            for source in set(self._fds.values()):
                self._remove_device(source, quiet=True)
            self._uinput.close()
            self._logger.info("quitting")

    def _run(self):

        """
        Run a :py:meth:`select.poll.poll()` loop processing both
        synchronous and asynchronous events.

        :returns: None
        """

        def sighup_handler(*_):     # pragma: no cover
            """
            Raise an exception to signal SIGHUP reception.

            :raises: :py:exc:`SIGHUPReceivedException`
            """
            raise SIGHUPReceivedException

        signal.signal(signal.SIGHUP, sighup_handler)
        while True:
            # Calculate time until the next delayed action triggers
            try:
                now = time.time()
                timeout = max(0, (self._delayed[0]['when'] - now) * 1000)
            except IndexError:
                timeout = None
            # Wait for either an input event or the moment when the next
            # delayed action should be triggered, whichever comes first
            try:
                results = self._poll.poll(timeout)
            except SIGHUPReceivedException:
                self._logger.info("SIGHUP received")
                self._scan_devices()
                continue
            for (fdesc, _) in results:
                try:
                    source = self._fds[fdesc]
                    actions = source.process(fdesc)
                except OSError:
                    self._remove_device(source)
                    continue
                # source.process() called with a configuration
                # descriptor should always return None
                if actions:
                    self._perform_normal_actions(actions)
            if not results:
                # It's time for the next delayed action
                self._perform_delayed()
            self._uinput.syn()

    def _perform_normal_actions(self, actions):
        """
        Perform the actions requested by an event source in response to
        the events it processed.

        :param actions: list of *(action, direction)* tuples, each of
            which specifies which action to perform in which "direction"
        :type actions: list
        :returns: None
        """
        for (action, direction) in actions:
            self._logger.debug("action=%s, direction=%s", action, direction)
            if action['trigger'] == 'normal':
                if direction == 'down':
                    if action['type'] == 'key':
                        self._uinput_synthesize(action, press=True)
                    elif action['type'] == 'exec':
                        _execute_program(action)
                else:
                    if action['type'] == 'key':
                        self._uinput_synthesize(action, press=False)
            elif action['trigger'] == 'long':
                if direction == 'down':
                    # Schedule delayed action to trigger after 1 second
                    action['when'] = time.time() + 1
                    action['direction'] = 'down'
                    self._delayed.append(action)
                else:
                    # Cancel delayed action
                    try:
                        index = next(
                            i for (i, a) in enumerate(self._delayed)
                            if a['id'] == action['id']
                        )
                        del self._delayed[index]
                    except StopIteration:
                        # Action has already been removed from the queue by
                        # _perform_delayed()
                        pass

    def _perform_delayed(self):
        """
        Perform the next queued delayed action.

        :returns: None
        """
        action = self._delayed[0]
        if action['type'] == 'key':
            if action['direction'] == 'down':
                # Simulate a key press and queue its release in 10 ms to
                # make the synthesized event semi-realistic
                self._uinput_synthesize(action, press=True)
                action['when'] = time.time() + 0.01
                action['direction'] = 'up'
                self._delayed.append(action)
            else:
                self._uinput_synthesize(action, press=False)
        elif action['type'] == 'exec':
            _execute_program(action)
        del self._delayed[0]

    def _uinput_synthesize(self, action, press):
        """
        Inject a fake key press into the input subsystem using uinput

        :param action: action dictionary containing a `target` key which
            specifies the key to synthesize
        :type action: dict
        :param press: whether to simulate a key press (`True`) or a key
            release (`False`)
        :type press: bool
        :returns: None
        """
        keys = evmapy.util.as_list(action['target'])
        for key in keys:
            ecode = evdev.ecodes.ecodes['EV_KEY']
            etype = evdev.ecodes.ecodes[key]
            self._uinput.write(ecode, etype, int(press))
