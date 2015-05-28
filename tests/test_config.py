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
Unit tests for the config module
"""

import evdev
import json
import tempfile
import unittest
import unittest.mock

import evmapy.config
import evmapy.util

import tests.util


class TestConfig(unittest.TestCase):

    """
    Test all functions
    """

    def test_config_create_invalid_path(self):
        """
        Test create() with an invalid device path
        """
        self.assertIsNotNone(evmapy.config.create('/foo/bar'))

    @unittest.mock.patch('os.path.exists')
    @unittest.mock.patch('evdev.InputDevice')
    def test_config_create_overwrite(self, fake_device, fake_exists):
        """
        Test create() with a configuration file path that already exists
        """
        fake_device.return_value.name = 'Foo Bar'
        fake_exists.return_value = True
        self.assertIsNotNone(evmapy.config.create('/dev/input/event0'))

    @unittest.mock.patch('evmapy.config.save')
    @unittest.mock.patch('evmapy.config.generate')
    @unittest.mock.patch('evdev.InputDevice')
    def test_config_create(self, fake_inputdevice, fake_generate, fake_save):
        """
        Test create() with a valid device path and a non-existent
        configuration file
        """
        fake_inputdevice.return_value.name = 'Foo Bar'
        self.assertIsNone(evmapy.config.create('/dev/input/event0'))
        self.assertEqual(fake_generate.call_count, 1)
        self.assertEqual(fake_save.call_count, 1)

    @unittest.mock.patch('evdev.InputDevice')
    def test_config_generate(self, fake_inputdevice):
        """
        Test generate()
        """
        fake_axes = [
            (('ABS_X', 0), evdev.device.AbsInfo(
                value=128, min=0, max=255, fuzz=0, flat=15, resolution=0
            )),
            (('ABS_HAT0X', 16), evdev.device.AbsInfo(
                value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0
            )),
        ]
        fake_buttons = [
            (['BTN_A', 'BTN_GAMEPAD', 'BTN_SOUTH'], 304),
            ('BTN_C', 306),
        ]
        fake_device_capabilities = {
            ('EV_ABS', 3): fake_axes,
            ('EV_KEY', 1): fake_buttons,
        }
        fake_capabilities = fake_inputdevice.return_value.capabilities
        fake_capabilities.return_value = fake_device_capabilities
        device = fake_inputdevice()
        config = evmapy.config.generate(device)
        self.assertEqual(len(config['axes']), len(fake_axes))
        self.assertEqual(len(config['buttons']), len(fake_buttons))
        self.assertFalse(config['grab'])

    @unittest.mock.patch('os.mkdir')
    def test_config_save(self, fake_mkdir):
        """
        Test save()
        """
        info = evmapy.util.get_app_info()
        fake_mkdir.side_effect = FileExistsError()
        with tempfile.NamedTemporaryFile(mode='w+') as temp:
            evmapy.config.save(temp.name, tests.util.get_fake_config())
            temp.seek(0)
            config = json.load(temp)
        fake_mkdir.assert_called_once_with(info['config_dir'])
        self.assertDictEqual(tests.util.get_fake_config(), config)

    @unittest.mock.patch('evmapy.config.read')
    def check_load_error(self, *args):
        """
        Test load() with an explicit configuration file name, raising
        the given exception when read() is called
        """
        (error, fake_read) = args
        fake_read.side_effect = error
        with self.assertRaises(evmapy.config.ConfigError):
            evmapy.config.load(unittest.mock.Mock(), 'Foo.Bar.json')

    def test_config_load_not_found(self):
        """
        Check load() behavior when a FileNotFoundError is raised by
        read()
        """
        self.check_load_error(FileNotFoundError())

    def test_config_load_bad_json(self):
        """
        Check load() behavior when a ValueError is raised by read()
        """
        self.check_load_error(ValueError())

    def test_config_load_error(self):
        """
        Check load() behavior when any other exception is raised by
        read()
        """
        self.check_load_error(Exception())

    @unittest.mock.patch('evmapy.config.read')
    def check_parse_error(self, *args):
        """
        Check parse() behavior when configuration contains errors
        """
        (extra_action, fake_read) = args
        bad_config = tests.util.get_fake_config()
        bad_config['actions'].append(extra_action)
        fake_read.return_value = bad_config
        with self.assertRaises(evmapy.config.ConfigError):
            evmapy.config.load(unittest.mock.Mock(), 'Foo.Bar.json')

    def test_config_parse_hold(self):
        """
        Check parse() behavior when action's hold time is negative
        """
        self.check_parse_error({
            'trigger':  'Foo',
            'hold':     1.0 * -1,
            'type':     'key',
            'target':   'KEY_BACKSPACE',
        })

    def test_config_parse_hold_seq(self):
        """
        Check parse() behavior when contradicting properties are set for
        an action
        """
        self.check_parse_error({
            'trigger':  ['Foo:min', 'Foo:max'],
            'mode':     'sequence',
            'hold':     1.0,
            'type':     'key',
            'target':   'KEY_BACKSPACE',
        })

    @unittest.mock.patch('logging.getLogger')
    @unittest.mock.patch('evmapy.config.read')
    def test_config_load_relative(self, fake_read, _):
        """
        Check if load() properly sanitizes the provided file name
        """
        evmapy.config.load(unittest.mock.Mock(), '../foo.json')
        read_arg = fake_read.call_args[0][0]
        with self.assertRaises(ValueError):
            read_arg.index('..')

    @unittest.mock.patch('logging.getLogger')
    def test_config_load_ok(self, _):
        """
        Test load() with a valid, default configuration file
        """
        fake_config_json = json.dumps(tests.util.get_fake_config())
        fake_open = unittest.mock.mock_open(read_data=fake_config_json)
        fake_device = unittest.mock.Mock()
        fake_device.name = 'Foo Bar'
        fake_device.fn = '/dev/input/event0'
        with unittest.mock.patch('evmapy.config.open', fake_open, create=True):
            config = evmapy.config.load(fake_device, None)
        self.assertSetEqual(set(config.keys()), set(['events', 'grab', 'map']))
        self.assertEqual(len(config['map'][100]), 2)
        self.assertEqual(len(config['map'][101]), 1)
        self.assertEqual(len(config['map'][200]), 1)
        self.assertEqual(len(config['map'][300]), 0)
