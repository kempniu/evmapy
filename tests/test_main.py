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
Unit tests for the __main__ module
"""

import io
import logging
import logging.handlers
import socket
import unittest
import unittest.mock

import evmapy.__main__
import evmapy.util


class TestLogging(unittest.TestCase):

    """
    Test initialize_logging()
    """

    @unittest.mock.patch.object(socket.socket, 'connect')
    @unittest.mock.patch('sys.stdout')
    @unittest.mock.patch('os.isatty')
    def check_logging(self, *args):
        """
        Call initialize_logging() with supplied arguments and check
        properties of the returned Logger object
        """
        (params, fake_isatty, *_) = args
        fake_isatty.return_value = params['foreground']
        logger = evmapy.__main__.initialize_logging('foo', params['debug'])
        self.assertEqual(logger.getEffectiveLevel(), params['level'])
        self.assertIsInstance(logger.handlers[-1], params['handler'])

    def test_logging_fg_debug_on(self):
        """
        Test initialize_logging() when running in foreground with
        debugging enabled
        """
        params = {
            'foreground':   True,
            'debug':        True,
            'level':        logging.DEBUG,
            'handler':      logging.StreamHandler,
        }
        self.check_logging(params)

    def test_logging_bg_debug_off(self):
        """
        Test initialize_logging() when running in background with
        debugging disabled
        """
        params = {
            'foreground':   False,
            'debug':        False,
            'level':        logging.INFO,
            'handler':      logging.handlers.SysLogHandler,
        }
        self.check_logging(params)


@unittest.mock.patch('evmapy.__main__.initialize_logging')
@unittest.mock.patch('evmapy.multiplexer.Multiplexer')
def check_main_calls(*args):
    """
    Call main() with supplied arguments and check the calls it made
    """
    (params, fake_multiplexer, fake_logging) = args
    info = evmapy.util.get_app_info()
    fake_run = fake_multiplexer.return_value.run
    evmapy.__main__.main(params['argv'])
    fake_logging.assert_called_once_with(info['name'], params['debug'])
    fake_run.assert_called_once_with()


@unittest.mock.patch('sys.stdout', new_callable=io.StringIO)
class TestMain(unittest.TestCase):

    """
    Test main()
    """

    @unittest.mock.patch('evdev.InputDevice')
    @unittest.mock.patch('evdev.list_devices')
    def test_main_list(self, fake_list_devices, _, fake_stdout):
        """
        $ evmapy --list
        """
        fake_devices = ['/dev/input/event%d' % i for i in range(0, 10)]
        fake_list_devices.return_value = fake_devices
        evmapy.__main__.main(['--list'])
        lines_printed = fake_stdout.getvalue().splitlines()
        self.assertEqual(len(lines_printed), len(fake_devices))

    @unittest.mock.patch('evmapy.config.create')
    def test_main_configure(self, fake_create, fake_stdout):
        """
        $ evmapy --configure /dev/input/event0
        """
        with self.assertRaises(SystemExit):
            evmapy.__main__.main(['--configure', '/dev/input/event0'])
        fake_create.assert_called_with('/dev/input/event0')
        self.assertEqual(fake_stdout.getvalue(), '')

    def test_main_debug_off(self, fake_stdout):
        """
        $ evmapy
        """
        params = {
            'argv':     [],
            'debug':    False,
        }
        check_main_calls(params)
        self.assertEqual(fake_stdout.getvalue(), '')

    def test_main_debug_on(self, fake_stdout):
        """
        $ evmapy --debug
        """
        params = {
            'argv':     ['--debug'],
            'debug':    True,
        }
        check_main_calls(params)
        self.assertEqual(fake_stdout.getvalue(), '')
