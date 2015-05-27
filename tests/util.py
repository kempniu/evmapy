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
Constants and functions used by test modules
"""

import copy


CONTROL_FD = 1
DEVICE_FD = 2
FAKE_CONFIG = {
    'actions': [
        {
            'trigger':  'Foo:min',
            'sequence': False,
            'hold':     0.0,
            'type':     'key',
            'target':   'KEY_LEFT',
        },
        {
            'trigger':  'Foo:max',
            'sequence': False,
            'hold':     0.0,
            'type':     'key',
            'target':   'KEY_RIGHT',
        },
        {
            'trigger':  'Bar',
            'sequence': False,
            'hold':     0.0,
            'type':     'key',
            'target':   'KEY_ENTER',
        },
        {
            'trigger':  ['Foobar', 'Foobaz'],
            'sequence': False,
            'hold':     0.0,
            'type':     'key',
            'target':   'KEY_ESC',
        },
        {
            'trigger':  ['Foofoo:max', 'Foofoo:max'],
            'sequence': True,
            'hold':     0.0,
            'type':     'key',
            'target':   ['KEY_UP', 'KEY_DOWN'],
        },
        {
            'trigger':  ['Barbar:min', 'Bazbaz:max'],
            'sequence': True,
            'hold':     0.0,
            'type':     'key',
            'target':   'KEY_SPACE',
        },
    ],
    'axes': [
        {
            'name':     'Foo',
            'code':     100,
            'min':      0,
            'max':      255,
        },
        {
            'name':     'Foofoo',
            'code':     101,
            'min':      0,
            'max':      255,
        },
        {
            'name':     'Barbar',
            'code':     102,
            'min':      0,
            'max':      255,
        },
        {
            'name':     'Bazbaz',
            'code':     103,
            'min':      0,
            'max':      255,
        }
    ],
    'buttons': [
        {
            'name':     'Bar',
            'code':     200,
        },
        {
            'name':     'Foobar',
            'code':     201,
        },
        {
            'name':     'Foobaz',
            'code':     202,
        },
        {
            'name':     'Baz',
            'code':     300,
        },
    ],
    'grab': False,
}


def get_fake_config():
    """
    Return a deep copy of the fake configuration dictionary. Needed
    because evmapy.config.parse() modifies the dictionary passed to it.
    """
    return copy.deepcopy(FAKE_CONFIG)


def set_attrs_from_dict(obj, attrs):
    """
    Set `obj` attributes based on `attrs` dictionary
    """
    for (attr, value) in attrs.items():
        setattr(obj, attr, value)
