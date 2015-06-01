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
Unit tests for the Source class
"""

import errno
import unittest
import unittest.mock

import evdev

import evmapy.config
import evmapy.source
import evmapy.util

import tests.util


@unittest.mock.patch('evmapy.config.load')
@unittest.mock.patch('logging.getLogger')
@unittest.mock.patch('evdev.InputDevice')
def mock_source(*args):
    """
    Generate a Source with mocked attributes
    """
    (fake_inputdevice, fake_logger, fake_config_load) = args
    device_attrs = {
        'name': 'Foo Bar',
        'fn':   '/dev/input/event0',
        'fd':   tests.util.DEVICE_FD,
    }
    tests.util.set_attrs_from_dict(fake_inputdevice.return_value, device_attrs)
    fake_config = evmapy.config.parse(tests.util.FAKE_CONFIG)
    fake_config_load.return_value = (fake_config, None)
    device = fake_inputdevice()
    return {
        'device':   device,
        'logger':   fake_logger.return_value,
        'source':   evmapy.source.Source(device),
    }


class TestSource(unittest.TestCase):

    """
    Test Source behavior
    """

    def setUp(self):
        """
        Create a Source to use with all tests
        """
        self.device = None
        self.logger = None
        self.source = None
        tests.util.set_attrs_from_dict(self, mock_source())

    def test_source_events(self):
        """
        Check if Source properly translates all events
        """
        event_list = [
            (evdev.ecodes.ecodes['EV_SYN'], 0, 0),
            (evdev.ecodes.ecodes['EV_KEY'], 400, evdev.KeyEvent.key_down),
            (evdev.ecodes.ecodes['EV_KEY'], 300, evdev.KeyEvent.key_down),
            (evdev.ecodes.ecodes['EV_KEY'], 200, evdev.KeyEvent.key_down),
            (evdev.ecodes.ecodes['EV_KEY'], 200, evdev.KeyEvent.key_hold),
            (evdev.ecodes.ecodes['EV_KEY'], 200, evdev.KeyEvent.key_up),
            (evdev.ecodes.ecodes['EV_KEY'], 201, evdev.KeyEvent.key_down),
            (evdev.ecodes.ecodes['EV_KEY'], 201, evdev.KeyEvent.key_up),
            (evdev.ecodes.ecodes['EV_KEY'], 201, evdev.KeyEvent.key_down),
            (evdev.ecodes.ecodes['EV_KEY'], 202, evdev.KeyEvent.key_down),
            (evdev.ecodes.ecodes['EV_KEY'], 202, evdev.KeyEvent.key_up),
            (evdev.ecodes.ecodes['EV_KEY'], 201, evdev.KeyEvent.key_up),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 0),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 64),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 192),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 256),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 192),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 100, 64),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 256),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 256),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 256),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 0),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 256),
            (evdev.ecodes.ecodes['EV_ABS'], 101, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 102, 0),
            (evdev.ecodes.ecodes['EV_ABS'], 102, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 103, 256),
            (evdev.ecodes.ecodes['EV_ABS'], 102, 0),
            (evdev.ecodes.ecodes['EV_ABS'], 102, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 103, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 102, 256),
            (evdev.ecodes.ecodes['EV_ABS'], 102, 128),
            (evdev.ecodes.ecodes['EV_ABS'], 103, 0),
            (evdev.ecodes.ecodes['EV_ABS'], 103, 128),
        ]
        expected_list = [
            ('KEY_ENTER', True),
            ('KEY_ENTER', False),
            ('KEY_ESC', True),
            ('KEY_ESC', False),
            ('KEY_LEFT', True),
            ('KEY_LEFT', False),
            ('KEY_RIGHT', True),
            ('KEY_RIGHT', False),
            (['KEY_UP', 'KEY_DOWN'], True),
            (['KEY_UP', 'KEY_DOWN'], False),
            ('KEY_SPACE', True),
            ('KEY_SPACE', False),
            ('KEY_BACKSPACE', True),
            ('KEY_BACKSPACE', False),
            ('KEY_BACKSPACE', True),
            ('KEY_BACKSPACE', False),
        ]
        fake_events = []
        for (ecode, etype, evalue) in event_list:
            fake_event = evdev.events.InputEvent(0, 0, ecode, etype, evalue)
            fake_events.append(fake_event)
        self.device.read.return_value = fake_events
        actions = self.source.process()
        for (action, direction) in actions:
            expected = expected_list.pop(0)
            self.assertTupleEqual((action['target'], direction), expected)
        self.assertEqual(expected_list, [])

    def test_source_device_removed(self):
        """
        Test Source behavior when the input device associated with it
        gets disconnected
        """
        self.device.read.side_effect = OSError(errno.ENODEV, "Foo")
        with self.assertRaises(evmapy.source.DeviceRemovedException):
            self.source.process()

    def test_source_device_error(self):
        """
        Test Source behavior when an unhandled exception is raised while
        reading from its associated input device
        """
        self.device.read.side_effect = OSError()
        with self.assertRaises(OSError):
            self.source.process()

    @unittest.mock.patch('evmapy.config.load')
    def test_source_load_config_grab(self, fake_config_load):
        """
        Check if Source properly grabs its underlying device when
        requested to
        """
        fake_config_load.side_effect = [
            ({'grab': False}, None),
            ({'grab': True}, None),
        ]
        self.source.load_config()
        self.source.load_config()
        self.assertEqual(self.device.grab.call_count, 1)

    @unittest.mock.patch('evmapy.config.load')
    def test_source_load_config_ungrab(self, fake_config_load):
        """
        Check if Source properly ungrabs its underlying device when
        requested to
        """
        fake_config_load.side_effect = [
            ({'grab': True}, None),
            ({'grab': False}, None),
        ]
        self.source.load_config()
        self.source.load_config()
        self.assertEqual(self.device.ungrab.call_count, 1)
