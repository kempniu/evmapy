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
Unit tests for the EventMultiplexer class
"""

import unittest
import unittest.mock

import evmapy.config
import evmapy.multiplexer

import tests.util


CONFIG_POLL_EVENT = [(tests.util.CONFIG_FD, 0)]
DEVICE_POLL_EVENT = [(tests.util.DEVICE_FD, 0)]


class FooError(Exception):
    """
    Class simulating an unhandled exception
    """
    pass


@unittest.mock.patch('evdev.list_devices')
@unittest.mock.patch('select.poll')
@unittest.mock.patch('evdev.UInput')
@unittest.mock.patch('logging.getLogger')
def mock_eventmultiplexer(*args):
    """
    Generate an EventMultiplexer with mocked attributes
    """
    (exception, fake_logger, fake_uinput, fake_poll, fake_listdevices) = args
    if exception:
        fake_uinput.side_effect = FooError()
    fake_listdevices.return_value = []
    try:
        multiplexer = evmapy.multiplexer.EventMultiplexer()
    except FooError as exc:
        multiplexer = exc
    return {
        'logger':       fake_logger.return_value,
        'multiplexer':  multiplexer,
        'poll':         fake_poll.return_value,
        'uinput':       fake_uinput.return_value,
    }


class TestMultiplexer(unittest.TestCase):

    """
    Test EventMultiplexer behavior
    """

    def setUp(self):
        """
        Create an EventMultiplexer to use with all tests
        """
        self.logger = None
        self.multiplexer = None
        self.poll = None
        self.uinput = None
        tests.util.set_attrs_from_dict(self, mock_eventmultiplexer(False))

    def test_multiplexer_init_exception(self):
        """
        Check EventMultiplexer behavior when an exception is raised upon
        its initialization
        """
        retval = mock_eventmultiplexer(True)
        self.assertIsInstance(retval['multiplexer'], FooError)
        self.assertEqual(retval['logger'].exception.call_count, 1)

    def test_multiplexer_interrupt(self):
        """
        Check if EventMultiplexer properly cleans up after itself after
        being interrupted
        """
        self.poll.poll.side_effect = KeyboardInterrupt()
        self.multiplexer.run()
        self.uinput.close.assert_called_once_with()

    def test_multiplexer_exception(self):
        """
        Check if EventMultiplexer properly cleans up after itself after
        an unhandled exception is raised
        """
        self.poll.poll.side_effect = FooError()
        with self.assertRaises(FooError):
            self.multiplexer.run()
        self.assertEqual(self.logger.exception.call_count, 1)
        self.uinput.close.assert_called_once_with()

    @unittest.mock.patch('evdev.InputDevice')
    @unittest.mock.patch('evdev.list_devices')
    def multiplexer_loop(self, *args):
        """
        Add a fake device with the given path to EventMultiplexer, then
        run the latter while replacing poll() results with provided
        values and finally interrupt it by simulating a
        KeyboardInterrupt
        """
        (poll_results, source, fake_list, _) = args
        fake_list.return_value = ['/dev/input/event0']
        source.return_value.fds = {
            'config':   tests.util.CONFIG_FD,
            'device':   tests.util.DEVICE_FD,
        }
        poll_results.insert(0, evmapy.multiplexer.SIGHUPReceivedException())
        poll_results.append(KeyboardInterrupt())
        self.poll.poll.side_effect = poll_results
        self.multiplexer.run()

    @unittest.mock.patch('evmapy.source.EventSource')
    def test_multiplexer_add_device_bad(self, fake_eventsource):
        """
        Check EventMultiplexer behavior when requested to add a device
        which has an invalid configuration file
        """
        fake_error = evmapy.config.ConfigError('/foo.json', ValueError())
        fake_eventsource.side_effect = fake_error
        self.multiplexer_loop([], fake_eventsource)
        self.assertFalse(self.poll.register.called)

    @unittest.mock.patch('evmapy.source.EventSource')
    def test_multiplexer_add_device_ok(self, fake_eventsource):
        """
        Check EventMultiplexer behavior when requested to add a device
        which has a valid configuration file
        """
        self.multiplexer_loop([], fake_eventsource)
        self.assertEqual(fake_eventsource.call_count, 1)
        self.assertEqual(self.poll.register.call_count, 2)

    @unittest.mock.patch('evmapy.source.EventSource')
    def test_multiplexer_remove_device(self, fake_eventsource):
        """
        Check EventMultiplexer behavior when a handled device is removed
        """
        fake_eventsource.return_value.process.side_effect = OSError()
        self.multiplexer_loop([DEVICE_POLL_EVENT], fake_eventsource)
        self.assertEqual(self.poll.unregister.call_count, 2)
        fake_eventsource.return_value.cleanup.assert_called_once_with()

    @unittest.mock.patch('evmapy.source.EventSource')
    def test_multiplexer_device_fd(self, fake_eventsource):
        """
        Check if EventMultiplexer properly reacts to device descriptor
        activity
        """
        self.multiplexer_loop([DEVICE_POLL_EVENT], fake_eventsource)
        fake_eventsource.return_value.process.assert_called_once_with(
            tests.util.DEVICE_FD
        )

    @unittest.mock.patch('evmapy.source.EventSource')
    def test_multiplexer_config_fd(self, fake_eventsource):
        """
        Check if EventMultiplexer properly reacts to configuration
        descriptor activity
        """
        self.multiplexer_loop([CONFIG_POLL_EVENT], fake_eventsource)
        fake_eventsource.return_value.process.assert_called_once_with(
            tests.util.CONFIG_FD
        )

    @unittest.mock.patch('os.system')
    @unittest.mock.patch('evmapy.source.EventSource')
    def multiplexer_check_action(self, *args):
        """
        Run an EventMultiplexer loop, synthesizing the requested action
        in both directions and returning either the device descriptor or
        an empty list on each subsequent poll() call
        """
        (action, poll_device, fake_eventsource, fake_system) = args
        actions = [
            [(action, 'down')],
            [(action, 'up')],
        ]
        fake_eventsource.return_value.process.side_effect = actions
        poll_results = [DEVICE_POLL_EVENT if d else [] for d in poll_device]
        self.multiplexer_loop(poll_results, fake_eventsource)
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
