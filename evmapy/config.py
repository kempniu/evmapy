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
Functions handling configuration generation, saving and loading
"""

import json
import os

import evdev

import evmapy.util


def create(dev_path):
    """
    Generate and save a default configuration file for the input device
    under the given path.

    :param dev_path: path to the device to create configuration for
    :type dev_path: str
    :returns: nothing on success, error string otherwise
    :rtype: None or str
    """
    try:
        device = evdev.InputDevice(dev_path)
    except FileNotFoundError:
        return "No such device %s" % dev_path
    config_path = evmapy.util.get_device_config_path(device)
    if os.path.exists(config_path):
        return "%s already exists, not overwriting" % config_path
    config = generate(device)
    save(config_path, config)


def generate(device):
    """
    Generate a default configuration dictionary for a given input
    device.

    :param device: device to generate configuration for
    :type device: :py:class:`evdev.InputDevice`
    :returns: default configuration dictionary
    :rtype: dict
    """
    config = {
        'grab':     False,
        'axes':     [],
        'buttons':  [],
    }
    capabilities = device.capabilities(verbose=True, absinfo=True)
    for ((_, event_type_id), events) in capabilities.items():
        for (event_names, activator) in events:
            event_name = evmapy.util.first_element(event_names)
            action = {
                'trigger':  'normal',
                'type':     'exec',
                'target':   'echo %s' % event_name,
            }
            if event_type_id == evdev.ecodes.ecodes['EV_KEY']:
                config['buttons'].append({
                    'alias':    event_name,
                    'code':     activator,
                    'press':    action,
                })
            elif event_type_id == evdev.ecodes.ecodes['EV_ABS']:
                actions = {
                    'min':  action.copy(),
                    'max':  action.copy(),
                }
                actions['min']['value'] = activator.min
                actions['min']['target'] += ' min'
                actions['max']['value'] = activator.max
                actions['max']['target'] += ' max'
                config['axes'].append({
                    'alias':    event_name,
                    'code':     event_names[1],
                    'min':      actions['min'],
                    'max':      actions['max'],
                })
    return config


def save(path, config):
    """
    Save provided configuration under the given path, creating the
    configuration directory if necesary.

    :param path: path to save configuration under
    :type path: str
    :param config: configuration dictionary to save
    :type config: dict
    :returns: None
    """
    try:
        info = evmapy.util.get_app_info()
        os.mkdir(info['config_dir'])
    except FileExistsError:
        pass
    with open(path, 'w') as config_file:
        json.dump(config, config_file, indent=4, sort_keys=True)


def load(path):
    """
    Load device configuration from the file provided.

    :param path: path to load configuration from
    :type path: str
    :returns: event map generated from the loaded configuration
    :rtype: dict
    """
    retval = {}
    # Every action needs a unique identifier in order for the event
    # multiplexer to be able to remove it from the list of delayed
    # actions; note that we can't directly compare the dictionaries as
    # there may be identical actions configured for two different events
    current_id = 0
    with open(path) as config_file:
        config = json.load(config_file)
    retval['grab'] = config['grab']
    # Transform lists into an event map keyed by event ID
    for button in config['buttons']:
        button['press']['id'] = current_id
        current_id += 1
        retval[button['code']] = button
    for axis in config['axes']:
        for limit in ('min', 'max'):
            axis[limit]['id'] = current_id
            # Needed for proper handling of axis hysteresis
            axis[limit]['state'] = 'up'
            current_id += 1
        retval[axis['code']] = axis
    return retval
