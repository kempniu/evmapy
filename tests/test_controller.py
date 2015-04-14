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
Unit tests for the Controller class
"""

import json
import unittest
import unittest.mock

import evmapy.controller

import tests.util


@unittest.mock.patch('logging.getLogger')
@unittest.mock.patch('os.chmod')
@unittest.mock.patch('socket.socket')
def mock_controller(*args):
    """
    Generate a Controller with mocked attributes
    """
    (fake_socket, _, fake_logger) = args
    fake_target = unittest.mock.Mock()
    controller = evmapy.controller.Controller(fake_target)
    return {
        'controller':   controller,
        'logger':       fake_logger.return_value,
        'target':       fake_target,
        'socket':       fake_socket,
    }


class TestController(unittest.TestCase):

    """
    Test Controller behavior
    """

    def setUp(self):
        """
        Create a Controller to use with all tests
        """
        self.controller = None
        self.logger = None
        self.target = None
        self.socket = None
        tests.util.set_attrs_from_dict(self, mock_controller())

    def test_controller_socket(self):
        """
        Test socket creation
        """
        self.assertEqual(self.socket.call_count, 1)
        self.assertEqual(self.socket.return_value.bind.call_count, 1)
        fileno = self.controller.fileno()
        self.assertIs(fileno, self.socket.return_value.fileno.return_value)

    def check_controller_process(self, request, jsonize=True):
        """
        Check process() behavior when the given control request is
        passed to it
        """
        if jsonize:
            request = json.dumps(request).encode()
        self.socket.return_value.recv.return_value = request
        self.controller.process()

    def test_controller_bad_json(self):
        """
        Check Controller behavior when processing a request which is not
        valid JSON
        """
        self.check_controller_process(b'foo', jsonize=False)
        self.assertEqual(self.logger.error.call_count, 1)

    def test_controller_no_command(self):
        """
        Check Controller behavior when processing a request with no
        command specified
        """
        request = {}
        self.check_controller_process(request)
        self.assertEqual(self.logger.error.call_count, 1)

    def test_controller_bad_command(self):
        """
        Check Controller behavior when a request with an unknown command
        is received
        """
        request = {
            'command':  'foo',
        }
        self.check_controller_process(request)
        self.assertEqual(self.logger.error.call_count, 1)

    def test_controller_missing_param(self):
        """
        Check Controller behavior when the request received is missing a
        required command parameter
        """
        setattr(self.controller, 'do_foo', lambda request: request['bar'])
        request = {
            'command':  'foo',
        }
        self.check_controller_process(request)
        self.assertEqual(self.logger.error.call_count, 1)

    @unittest.mock.patch('os.remove')
    def test_controller_cleanup(self, fake_remove):
        """
        Check if Controller properly cleans up after itself
        """
        self.controller.cleanup()
        self.assertEqual(self.socket.return_value.close.call_count, 1)
        self.assertEqual(fake_remove.call_count, 1)
