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
:py:class:`Multiplexer` class implementation
"""

import logging
import os
import select
import signal
import time

import evdev

import evmapy.config
import evmapy.controller
import evmapy.source
import evmapy.util


class SIGHUPReceivedException(Exception):
    """
    Exception raised when a SIGHUP signal is received.
    """
    pass


class SIGTERMReceivedException(Exception):
    """
    Exception raised when a SIGTERM signal is received.
    """
    pass


class Multiplexer(object):

    """
    Class monitoring input device file descriptors and the control
    socket for incoming data. Whenever any of these is ready for
    reading, its associated object (:py:class:`evmapy.source.Source` or
    :py:class:`evmapy.controller.Controller` instance, respectively) is
    asked to process pending data. If the result of this processing in
    an action list, these actions are then performed.
    """

    def __init__(self):
        self._fds = {}
        self._delayed = []
        self._logger = logging.getLogger()
        self._poll = None
        self._uinput = None
        try:
            signal.signal(signal.SIGHUP, signal.SIG_IGN)
            info = evmapy.util.get_app_info()
            app_with_user = (info['name'], info['user'].pw_name)
            # Create the control socket
            self._controller = evmapy.controller.Controller(self)
            # Try to open /dev/uinput, failing gracefully
            try:
                self._uinput = evdev.UInput(name='%s (%s)' % app_with_user)
            except evdev.uinput.UInputError as exc:
                self._logger.warning(
                    "injecting keypresses will not be possible: %s", str(exc)
                )
            # Start processing events from all configured devices
            self._poll = select.poll()
            self._scan_devices()
            # Start monitoring the control socket
            self._fds[self._controller.fileno()] = self._controller
            self._poll.register(self._controller, select.POLLIN)
        except evmapy.controller.SocketInUseError:
            error_msg = "%s is already running as %s" % app_with_user
            self._logger.error(error_msg)
            exit(1)
        except:
            self._logger.exception("unhandled exception while initializing:")
            raise

    @property
    def devices(self):
        """
        Return a list of handled :py:class:`evmapy.source.Source`
        instances.

        :returns: list of handled :py:class:`evmapy.source.Source`
            instances
        :rtype: list
        """
        retval = []
        for processor in self._fds.values():
            if getattr(processor, 'device', 'socket') != 'socket':
                retval.append(processor)
        return retval

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
            source = evmapy.source.Source(device)
            self._fds[source.device['fd']] = source
            self._poll.register(source.device['fd'], select.POLLIN)
        except evmapy.config.ConfigError as exc:
            if not exc.not_found:
                self._logger.error(str(exc))

    def _remove_device(self, source, quiet=False):
        """
        Stop processing events emitted by the device associated with the
        given source.

        :param source: source to stop listening to
        :type source: evmapy.source.Source
        :param quiet: whether to log device removal or not
        :type quiet: bool
        :returns: None
        """
        del self._fds[source.device['fd']]
        self._poll.unregister(source.device['fd'])
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
        except SIGTERMReceivedException:
            self._logger.info("SIGTERM received")
        except:
            self._logger.exception("unhandled exception:")
            raise
        finally:
            # Always cleanup, even if an unhandled exception was raised
            del self._fds[self._controller.fileno()]
            self._poll.unregister(self._controller)
            self._controller.cleanup()
            for source in self.devices:
                self._remove_device(source, quiet=True)
            if self._uinput:
                self._uinput.close()
            self._logger.info("quitting")

    def _run(self):

        """
        Run a :py:meth:`select.poll.poll()` loop processing both
        synchronous and asynchronous events.

        :returns: None
        """

        def raise_signal_exception(signum, _):     # pragma: no cover
            """
            Raise an exception based on received signal.

            :raises evmapy.multiplexer.SIGHUPReceivedException:
                when SIGHUP is received
            :raises evmapy.multiplexer.SIGTERMReceivedException:
                when SIGTERM is received
            """
            if signum == signal.SIGHUP:
                raise SIGHUPReceivedException
            elif signum == signal.SIGTERM:
                raise SIGTERMReceivedException

        signal.signal(signal.SIGHUP, raise_signal_exception)
        signal.signal(signal.SIGTERM, raise_signal_exception)
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
                    processor = self._fds[fdesc]
                    actions = processor.process()
                except evmapy.source.DeviceRemovedException:
                    self._remove_device(processor)
                    continue
                if actions:
                    self._perform_normal_actions(actions)
            if not results:
                # It's time for the next delayed action
                self._perform_delayed_actions()
            if self._uinput:
                self._logger.debug("writing: code 00, type 00, val 00")
                self._uinput.syn()

    def _perform_normal_actions(self, actions):
        """
        Perform the actions requested by a source in response to the
        events it processed.

        :param actions: list of *(action, direction)* tuples, each of
            which specifies which action to perform in which "direction"
        :type actions: list
        :returns: None
        """
        for (action, direction) in actions:
            self._logger.debug("action=%s, direction=%s", action, direction)
            if not action['hold']:
                if direction == 'down':
                    if action['type'] == 'key':
                        self._uinput_synthesize(action, press=True)
                    elif action['type'] == 'exec':
                        self._execute_program(action)
                else:
                    if action['type'] == 'key':
                        self._uinput_synthesize(action, press=False)
            else:
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
                        # Action has already been removed from the queue
                        # by _perform_delayed_actions()
                        pass

    def _perform_delayed_actions(self):
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
            self._execute_program(action)
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
        if not self._uinput:
            return
        keys = evmapy.util.as_list(action['target'])
        for key in keys:
            etype = evdev.ecodes.ecodes['EV_KEY']
            ecode = evdev.ecodes.ecodes[key]
            self._logger.debug(
                "writing: code %02d, type %02d, val %02d", ecode, etype, press
            )
            self._uinput.write(etype, ecode, int(press))

    def _execute_program(self, action):
        """
        Run external program(s) associated with the given action.

        :param action: action dictionary containing a `target` key which
            specifies the command(s) to be run
        :type action: dict
        :returns: None
        """
        commands = evmapy.util.as_list(action['target'])
        for command in commands:
            self._logger.debug("running: '%s'", command)
            os.system(command)

    def load_device_config(self, dev_path, config_file):
        """
        Loads configuration for the :py:class:`evmapy.source.Source`
        instance associated with the device under the given path from
        the configuration file with the given name.

        :param dev_path: path to the device which the
            :py:class:`evmapy.source.Source` to be configured is
            associated with
        :type dev_path: str
        :param config_file: name of the configuration file to load
        :type config_file: str
        :returns: None
        """
        for source in self.devices:
            if source.device['path'] == dev_path:
                try:
                    source.load_config(config_file)
                except evmapy.config.ConfigError as exc:
                    self._logger.error(
                        "%s: failed to load %s",
                        source.device['path'], str(exc)
                    )
