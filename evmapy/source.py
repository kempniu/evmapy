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
:py:class:`EventSource` class implementation
"""

import logging
import os
import re
import socket

import evdev

import evmapy.config
import evmapy.util


class EventSource(object):

    """
    Class encapsulating an :py:class:`evdev.InputDevice` instance which
    translates the events emitted by it to a list of actions to be
    performed by :py:class:`evmapy.multiplexer.EventMultiplexer`. The
    event-to-action mappings can be dynamically changed by writing the
    new configuration filename to a Unix domain socket.
    """

    def __init__(self, device, config_path):
        self.device = {
            'name': device.name,
            'path': device.fn,
        }
        self._device = device
        self._eventmap = {}
        self._grabbed = False
        self._logger = logging.getLogger()
        self._load_config(config_path)
        config_socket_path = '/tmp/%s-%s-%s' % (
            evmapy.util.get_app_info()['name'],
            re.sub(r'[^\w]', '-', device.fn),
            re.sub(r'[^\w]', '-', device.name)
        )
        config_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        config_socket.bind(config_socket_path)
        self.fds = {
            'config':   config_socket.fileno(),
            'device':   device.fd,
        }
        self._config = {
            'path':     config_socket_path,
            'socket':   config_socket,
        }

    def _load_config(self, path):
        """
        Load configuration from the given path.

        :param path: path to load configuration from
        :type path: str
        :returns: None
        """
        self._eventmap = evmapy.config.load(path)
        self._logger.info("%s: loaded %s", self.device['path'], path)
        if self._eventmap['grab'] is True and self._grabbed is False:
            self._device.grab()
            self._grabbed = True
            self._logger.info("%s: device grabbed", self.device['path'])
        elif self._eventmap['grab'] is False and self._grabbed is True:
            self._device.ungrab()
            self._grabbed = False
            self._logger.info("%s: device ungrabbed", self.device['path'])

    def process(self, fileno):
        """
        Process pending input events or configuration request, depending
        on which file descriptor was provided.

        :param fileno: file descriptor to process
        :type fileno: int
        :returns: list of actions to be performed
        :rtype: list
        """
        if fileno == self.fds['device']:
            return self._process_input_events()
        elif fileno == self.fds['config']:
            return self._process_config_request()

    def _process_input_events(self):

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
        for event in self._device.read():
            self._logger.debug(event)
            if event.code not in self._eventmap:
                continue
            actions = self._eventmap[event.code]
            if event.type == evdev.ecodes.ecodes['EV_KEY']:
                if event.value == evdev.KeyEvent.key_up:
                    direction = 'up'
                else:
                    direction = 'down'
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

    def _process_config_request(self):
        """
        Reload configuration from the file name written to the
        configuration socket.

        :returns: an empty list (to signal that no actions should be
            performed)
        :rtype: list
        """
        info = evmapy.util.get_app_info()
        config_name = self._config['socket'].recv(256).decode().strip()
        config_path = os.path.join(info['config_dir'], config_name)
        if config_name:
            try:
                self._load_config(config_path)
            except FileNotFoundError:
                self._logger.error(
                    "%s: no such configuration file: %s",
                    self.device['path'], config_path
                )
        else:
            # Reload default configuration
            config_path = evmapy.util.get_device_config_path(self._device)
            self._load_config(config_path)
        return []

    def cleanup(self):
        """
        Close the configuration socket and remove it from the
        filesystem.

        :returns: None
        """
        self._config['socket'].close()
        os.remove(self._config['path'])
