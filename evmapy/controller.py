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
:py:class:`Controller` class implementation
"""

import json
import logging
import os
import socket
import stat

import evmapy.util


class Controller(object):

    """
    Class responsible for dynamically changing the behavior of a given
    :py:class:`evmapy.multiplexer.Multiplexer` by processing requests
    sent to a Unix domain socket.
    """

    def __init__(self, target):
        self._logger = logging.getLogger()
        self._target = target
        info = evmapy.util.get_app_info()
        control_socket_path = '/tmp/%s.socket' % info['name']
        control_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        control_socket.bind(control_socket_path)
        os.chmod(control_socket_path, stat.S_IRUSR | stat.S_IWUSR)
        self._socket = {
            'path':     control_socket_path,
            'socket':   control_socket,
        }

    def fileno(self):
        """
        Return the control socket's file descriptor. This enables a
        :py:class:`Controller` instance to be used directly with
        :py:meth:`select.poll.poll()` and :py:func:`select.select()`.

        :returns: control socket's file descriptor
        :rtype: int
        """
        return self._socket['socket'].fileno()

    def process(self):
        """
        Read and process the request sent to the control socket.

        :returns: an empty list (to signal that no actions should be
            performed)
        :rtype: list
        """
        try:
            data = self._socket['socket'].recv(1024)
            request = json.loads(data.decode())
            command = request['command']
            method = getattr(self, 'do_' + command)
            try:
                method(request)
            except KeyError as exc:
                self._logger.error(
                    "missing parameter for command '%s': '%s'",
                    command, exc.args[0]
                )
        except ValueError:
            self._logger.error("invalid control request received")
        except KeyError:
            self._logger.error("no control command specified")
        except AttributeError:
            self._logger.error("unknown control command '%s'", command)
        return []

    def cleanup(self):
        """
        Close the control socket and remove it from the filesystem.

        :returns: None
        """
        self._socket['socket'].close()
        os.remove(self._socket['path'])

    def do_config(self, request):
        """
        Load configuration for the given input device from the specified
        file.

        :param request: request issued by peer
        :type request: dict
        :returns: None
        """
        try:
            config_file = request['file']
        except KeyError:
            config_file = None
        self._target.load_device_config(request['device'], config_file)
