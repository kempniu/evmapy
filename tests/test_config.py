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


FAKE_CONFIG = {
    'axes': [
        {
            'alias':    'Foo',
            'code':     1,
            'min': {
                'value':    0,
                'type':     'key',
                'trigger':  'normal',
                'target':   'KEY_LEFT',
            },
            'max': {
                'value':    255,
                'type':     'key',
                'trigger':  'normal',
                'target':   'KEY_RIGHT',
            },
        },
    ],
    'buttons': [
        {
            'alias':    'Bar',
            'code':     2,
            'press': {
                'type':     'key',
                'trigger':  'normal',
                'target':   'KEY_SPACE',
            },
        },
    ],
    'grab': False,
}


class TestConfig(unittest.TestCase):

    """
    Test all functions
    """

    def test_config_create_invalid_path(self):
        """
        Test create() with an invalid device path
        """
        self.assertIsNotNone(evmapy.config.create('/foo/bar'))

    @unittest.mock.patch('evmapy.util.get_device_config_path')
    @unittest.mock.patch('evdev.InputDevice')
    def test_config_create_overwrite(self, _, fake_config_path):
        """
        Test create() with a configuration file path that already exists
        """
        fake_config_path.return_value = '/'
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
            evmapy.config.save(temp.name, FAKE_CONFIG)
            temp.seek(0)
            config = json.load(temp)
        fake_mkdir.assert_called_once_with(info['config_dir'])
        self.assertDictEqual(FAKE_CONFIG, config)

    def test_config_load(self):
        """
        Test load()
        """
        with tempfile.NamedTemporaryFile(mode='w+') as temp:
            json.dump(FAKE_CONFIG, temp)
            temp.seek(0)
            eventmap = evmapy.config.load(temp.name)
        self.assertSetEqual(set(eventmap.keys()), set([1, 2, 'grab']))
        ids = [
            eventmap[1]['min']['id'],
            eventmap[1]['max']['id'],
            eventmap[2]['press']['id'],
        ]
        self.assertEqual(len(set(ids)), len(ids))
