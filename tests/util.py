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
    'axes': [
        {
            'alias':        'Foo',
            'code':         100,
            'min': {
                'value':    0,
                'hold':     False,
                'type':     'key',
                'target':   'KEY_LEFT',
            },
            'max': {
                'value':    255,
                'hold':     False,
                'type':     'key',
                'target':   'KEY_RIGHT',
            },
        },
    ],
    'buttons': [
        {
            'alias':        'Bar',
            'code':         200,
            'press': {
                'hold':     False,
                'type':     'key',
                'target':   'KEY_ENTER',
            },
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
