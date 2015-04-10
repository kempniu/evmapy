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
Various helper functions used by other modules
"""

import os
import pwd
import re


def as_list(var):
    """
    Return a one-element list containing `var` or `var` itself if it is
    already a list.

    :param var: variable to process
    :returns: processed variable
    :rtype: list
    """
    return [var] if not isinstance(var, list) else var


def first_element(var):
    """
    Return the first element of `var` or `var` itself if it is neither a
    list nor a tuple.

    :param var: variable to process
    :returns: first element of variable or variable itself
    """
    if isinstance(var, list) or isinstance(var, tuple):
        return var[0]
    else:
        return var


def get_app_info():
    """
    Return a dictionary of frequently used application information.

    :returns: frequently used application information
    :rtype: dict
    """
    info = {
        'name':     'evmapy',
        'version':  '1.0',
        'user':     pwd.getpwuid(os.geteuid()),
    }
    info['config_dir'] = os.path.join(info['user'].pw_dir, '.' + info['name'])
    return info


def get_device_config_path(device):
    """
    Return the path to the configuration file for the given input device.

    :param device: input device to get the configuration file path for
    :type device: :py:class:`evdev.InputDevice`
    :returns: path to the configuration file for the given input device
    :rtype: str
    """
    info = get_app_info()
    config_filename = re.sub(r'[^\w]', '.', device.name) + '.json'
    return os.path.join(info['config_dir'], config_filename)
