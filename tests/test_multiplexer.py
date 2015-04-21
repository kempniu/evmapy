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
Unit tests for the Multiplexer class
"""

import unittest
import unittest.mock

import evdev

import evmapy.config
import evmapy.multiplexer
import evmapy.source

import tests.util


CONTROL_POLL_EVENT = [(tests.util.CONTROL_FD, 0)]
DEVICE_POLL_EVENT = [(tests.util.DEVICE_FD, 0)]


class FooError(Exception):
    """
    Class simulating an unhandled exception
    """
    pass


@unittest.mock.patch('evdev.list_devices')
@unittest.mock.patch('select.poll')
@unittest.mock.patch('evdev.UInput')
@unittest.mock.patch('evmapy.controller.Controller')
@unittest.mock.patch('logging.getLogger')
def mock_multiplexer(*args):
    """
    Generate a Multiplexer with mocked attributes
    """
    (exception, fake_logger, fake_controller, fake_uinput, fake_poll,
     fake_listdevices) = args
    if exception == 'unhandled':
        fake_controller.side_effect = FooError()
    elif exception == 'controller':
        fake_controller.side_effect = evmapy.controller.SocketInUseError()
    elif exception == 'uinput':
        fake_uinput.side_effect = evdev.uinput.UInputError()
    fake_listdevices.return_value = []
    fake_controller.return_value.device = 'socket'
    fake_controller.return_value.fileno.return_value = tests.util.CONTROL_FD
    try:
        multiplexer = evmapy.multiplexer.Multiplexer()
    except FooError as exc:
        multiplexer = exc
    return {
        'controller':   fake_controller.return_value,
        'logger':       fake_logger.return_value,
        'multiplexer':  multiplexer,
        'poll':         fake_poll.return_value,
        'uinput':       fake_uinput.return_value,
    }


class TestMultiplexerBase(unittest.TestCase):
    """
    Base class for other test classes, to avoid boilerplate
    """
    def setUp(self):
        """
        Create a Multiplexer to use with all tests
        """
        self.controller = None
        self.logger = None
        self.multiplexer = None
        self.poll = None
        self.uinput = None
        tests.util.set_attrs_from_dict(self, mock_multiplexer(None))


class TestMultiplexerExceptions(TestMultiplexerBase):

    """
    Test Multiplexer behavior when various exceptions are raised
    """

    def test_multiplexer_control_in_use(self):
        """
        Check Multiplexer behavior when another instance of evmapy is
        already running as the same user
        """
        with self.assertRaises(SystemExit):
            mock_multiplexer('controller')

    def test_multiplexer_init_exception(self):
        """
        Check Multiplexer behavior when an unhandled exception is raised
        upon its initialization
        """
        retval = mock_multiplexer('unhandled')
        self.assertIsInstance(retval['multiplexer'], FooError)
        self.assertEqual(retval['logger'].exception.call_count, 1)

    def test_multiplexer_interrupt(self):
        """
        Check if Multiplexer properly cleans up after itself after being
        interrupted
        """
        fake_sigint = KeyboardInterrupt()
        self.poll.poll.side_effect = fake_sigint
        self.multiplexer.run()
        self.uinput.close.assert_called_once_with()

    def test_multiplexer_sigterm(self):
        """
        Check if Multiplexer properly cleans up after itself after being
        sent a SIGTERM
        """
        fake_sigterm = evmapy.multiplexer.SIGTERMReceivedException()
        self.poll.poll.side_effect = fake_sigterm
        self.multiplexer.run()
        self.uinput.close.assert_called_once_with()

    def test_multiplexer_exception(self):
        """
        Check if Multiplexer properly cleans up after itself after an
        unhandled exception is raised
        """
        self.poll.poll.side_effect = FooError()
        with self.assertRaises(FooError):
            self.multiplexer.run()
        self.assertEqual(self.logger.exception.call_count, 1)
        self.uinput.close.assert_called_once_with()


class TestMultiplexerLoop(TestMultiplexerBase):

    """
    Test Multiplexer's main loop
    """

    @unittest.mock.patch('evdev.InputDevice')
    @unittest.mock.patch('evdev.list_devices')
    def multiplexer_loop(self, *args):
        """
        Add a fake device with the given path to Multiplexer, then run
        the latter while replacing poll() results with provided values
        and finally interrupt it by simulating a KeyboardInterrupt
        """
        (poll_results, source, fake_list, _) = args
        fake_list.return_value = ['/dev/input/event0']
        if source:
            source.return_value.device = {
                'path': '/dev/input/event0',
                'fd':   tests.util.DEVICE_FD,
            }
            fake_rescan = evmapy.multiplexer.SIGHUPReceivedException()
            poll_results.insert(0, fake_rescan)
        poll_results.append(KeyboardInterrupt())
        self.poll.poll.side_effect = poll_results
        self.multiplexer.run()

    @unittest.mock.patch('evmapy.source.Source')
    def test_multiplexer_add_device_bad(self, fake_source):
        """
        Check Multiplexer behavior when requested to add a device which
        has an invalid configuration file
        """
        fake_error = evmapy.config.ConfigError('/foo.json', ValueError())
        fake_source.side_effect = fake_error
        self.multiplexer_loop([], fake_source)
        self.assertEqual(self.poll.register.call_count, 1)

    @unittest.mock.patch('evmapy.source.Source')
    def test_multiplexer_add_device_ok(self, fake_source):
        """
        Check Multiplexer behavior when requested to add a device which
        has a valid configuration file
        """
        self.multiplexer_loop([], fake_source)
        self.assertEqual(fake_source.call_count, 1)
        self.assertEqual(self.poll.register.call_count, 2)

    @unittest.mock.patch('evmapy.source.Source')
    def test_multiplexer_remove_device(self, fake_source):
        """
        Check Multiplexer behavior when a handled device is removed
        """
        fake_exception = evmapy.source.DeviceRemovedException()
        fake_source.return_value.process.side_effect = fake_exception
        self.multiplexer_loop([DEVICE_POLL_EVENT], fake_source)
        self.assertEqual(self.poll.unregister.call_count, 2)

    @unittest.mock.patch('evmapy.source.Source')
    def test_multiplexer_device_fd(self, fake_source):
        """
        Check if Multiplexer properly reacts to input device file
        descriptor activity
        """
        self.multiplexer_loop([DEVICE_POLL_EVENT], fake_source)
        fake_source.return_value.process.assert_called_once_with()

    def test_multiplexer_control_fd(self):
        """
        Check if Multiplexer properly reacts to control socket activity
        """
        self.multiplexer_loop([CONTROL_POLL_EVENT], None)
        self.controller.process.assert_called_once_with()

    @unittest.mock.patch('os.system')
    @unittest.mock.patch('evmapy.source.Source')
    def multiplexer_check_action(self, *args):
        """
        Run a Multiplexer loop, synthesizing the requested action in
        both directions and returning either the input device file
        descriptor or an empty list on each subsequent poll() call
        """
        (action, poll_device, fake_source, fake_system) = args
        actions = [
            [(action, 'down')],
            [(action, 'up')],
        ]
        fake_source.return_value.process.side_effect = actions
        poll_results = [DEVICE_POLL_EVENT if d else [] for d in poll_device]
        self.multiplexer_loop(poll_results, fake_source)
        return fake_system

    def test_multiplexer_normal_key(self):
        """
        Check key action with normal trigger
        """
        action = {
            'id':       1,
            'type':     'key',
            'trigger':  'normal',
            'target':   'KEY_ENTER',
        }
        poll_device = (True, True)
        self.multiplexer_check_action(action, poll_device)
        self.assertEqual(self.uinput.write.call_count, 2)

    def test_multiplexer_normal_exec(self):
        """
        Check exec action with normal trigger
        """
        action = {
            'id':       1,
            'type':     'exec',
            'trigger':  'normal',
            'target':   'foo',
        }
        poll_device = (True, True)
        fake_system = self.multiplexer_check_action(action, poll_device)
        fake_system.assert_called_once_with(action['target'])

    def test_multiplexer_long_key_full(self):
        """
        Check key action with long trigger, action is performed
        """
        action = {
            'id':       1,
            'type':     'key',
            'trigger':  'long',
            'target':   'KEY_ENTER',
        }
        poll_device = (True, False, False, True)
        self.multiplexer_check_action(action, poll_device)
        self.assertEqual(self.uinput.write.call_count, 2)

    def test_multiplexer_long_exec_full(self):
        """
        Check exec action with long trigger, action is performed
        """
        action = {
            'id':       1,
            'type':     'exec',
            'trigger':  'long',
            'target':   'foo',
        }
        poll_device = (True, False, True)
        fake_system = self.multiplexer_check_action(action, poll_device)
        fake_system.assert_called_once_with(action['target'])

    def test_multiplexer_long_key_stop(self):
        """
        Check key action with long trigger, action is cancelled
        """
        action = {
            'id':       1,
            'type':     'key',
            'trigger':  'long',
            'target':   'KEY_ENTER',
        }
        poll_device = (True, True)
        self.multiplexer_check_action(action, poll_device)
        self.assertFalse(self.uinput.write.called)

    def test_multiplexer_long_exec_stop(self):
        """
        Check exec action with long trigger, action is cancelled
        """
        action = {
            'id':       1,
            'type':     'exec',
            'trigger':  'long',
            'target':   'foo',
        }
        poll_device = (True, True)
        fake_system = self.multiplexer_check_action(action, poll_device)
        self.assertFalse(fake_system.called)

    def test_multiplexer_no_uinput(self):
        """
        Check key action with normal trigger when /dev/uinput was not
        opened correctly
        """
        tests.util.set_attrs_from_dict(self, mock_multiplexer('uinput'))
        action = {
            'id':       1,
            'type':     'key',
            'trigger':  'normal',
            'target':   'KEY_ENTER',
        }
        poll_device = (True, True)
        self.multiplexer_check_action(action, poll_device)
        self.assertEqual(self.uinput.write.call_count, 0)

    @unittest.mock.patch('evmapy.source.Source')
    def test_multiplexer_device_config(self, fake_source):
        """
        Ensure load_device_config() handles exceptions nicely
        """
        def fake_do_config():
            """
            Simulate a load_device_config() call
            """
            self.multiplexer.load_device_config(
                '/dev/input/event0', 'foo.json'
            )
        self.controller.process.side_effect = fake_do_config
        fake_error = evmapy.config.ConfigError('/foo.json', ValueError())
        fake_source.return_value.load_config.side_effect = fake_error
        self.multiplexer_loop([CONTROL_POLL_EVENT], fake_source)
        self.assertEqual(self.logger.error.call_count, 1)
