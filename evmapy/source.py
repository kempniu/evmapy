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
:py:class:`Source` class implementation
"""

import errno
import logging

import evdev

import evmapy.config
import evmapy.util


class DeviceRemovedException(Exception):
    """
    Exception raised when the associated input device gets disconnected.
    """
    pass


class Source(object):

    """
    Class encapsulating an :py:class:`evdev.InputDevice` instance which
    translates the events emitted by it to a list of actions to be
    performed by a :py:class:`evmapy.multiplexer.Multiplexer`.

    :param device: input device to use
    :type device: evdev.InputDevice
    """

    def __init__(self, device):
        self.device = {
            'fd':   device.fd,
            'name': device.name,
            'path': device.fn,
        }
        self._device = device
        self._config = {}
        self._grabbed = False
        self._logger = logging.getLogger()
        self.load_config()

    def load_config(self, name=None):
        """
        Load configuration from the given path.

        :param name: name of the configuration file to load (`None`
            and `''` cause the default configuration file to be used)
        :type name: str
        :returns: None
        :raises evmapy.config.ConfigError: if an error occurred while
            loading the specified configuration file
        """
        self._config = evmapy.config.load(self._device, name)
        if self._config['grab'] is True and self._grabbed is False:
            self._device.grab()
            self._grabbed = True
            self._logger.info("%s: device grabbed", self.device['path'])
        elif self._config['grab'] is False and self._grabbed is True:
            self._device.ungrab()
            self._grabbed = False
            self._logger.info("%s: device ungrabbed", self.device['path'])

    def process(self):
        """
        Translate input events into actions to be performed.

        :returns: list of actions to be performed
        :rtype: list
        """

        def _perform_axis_action(limit, direction):
            """
            Set the current state (i.e. direction) of the given action
            and then perform it in the given direction.

            :param limit: whether to perform this axis' `min` or `max`
                action
            :type limit: str
            :param direction: which direction to perform the action in
            :type direction: str
            :returns: None
            """
            actions[limit]['state'] = direction
            pending.append((actions[limit], direction))

        pending = []
        for event in self._pending_events():
            self._logger.debug(event)
            if event.code not in self._config:
                continue
            actions = self._config[event.code]
            if event.type == evdev.ecodes.ecodes['EV_KEY']:
                if event.value == evdev.KeyEvent.key_down:
                    direction = 'down'
                elif event.value == evdev.KeyEvent.key_up:
                    direction = 'up'
                elif event.value == evdev.KeyEvent.key_hold:
                    continue
                pending.append((actions['press'], direction))
            elif event.type == evdev.ecodes.ecodes['EV_ABS']:
                if (event.value <= actions['min']['value'] and
                        actions['min']['state'] == 'up'):
                    _perform_axis_action('min', 'down')
                elif (event.value >= actions['max']['value'] and
                      actions['max']['state'] == 'up'):
                    _perform_axis_action('max', 'down')
                else:
                    for limit in ('min', 'max'):
                        if actions[limit]['state'] == 'down':
                            _perform_axis_action(limit, 'up')

        return pending

    def _pending_events(self):
        """
        Return a generator yielding pending input events and raising an
        exception if the device is no longer available.

        :returns: generator yielding pending input events
        :rtype: generator
        :raises DeviceRemovedException: when the input device is no
            longer available
        """
        try:
            for event in self._device.read():
                yield event
        except OSError as exc:
            if exc.errno == errno.ENODEV:
                raise DeviceRemovedException()
            else:
                raise
