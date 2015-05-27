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
import logging
import os
import re

import evdev

import evmapy.util


class ConfigError(Exception):

    """
    Exception thrown when an error occurs when trying to load a device
    configuration file.

    :param path: path to the configuration file which caused the error
    :type path: str
    :param reason: last raised exception
    :type reason: Exception
    """

    def __init__(self, reason, path=None):
        super().__init__()
        self.path = path
        self.not_found = False
        if isinstance(reason, ConfigError):
            self.error = reason.error
        elif isinstance(reason, ValueError):
            self.error = "Invalid JSON file: %s" % str(reason)
        elif isinstance(reason, FileNotFoundError):
            self.error = "File not found"
            self.not_found = True
        else:
            self.error = str(reason)

    def __str__(self):
        return "%s: %s" % (self.path, self.error)


def _get_device_config_path(device):
    """
    Return the path to the default configuration file for the given
    input device.

    :param device: input device to get the default configuration file
        path for
    :type device: evdev.InputDevice
    :returns: path to the default configuration file for the given input
        device
    :rtype: str
    """
    info = evmapy.util.get_app_info()
    config_filename = re.sub(r'[^\w]', '.', device.name) + '.json'
    return os.path.join(info['config_dir'], config_filename)


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
    config_path = _get_device_config_path(device)
    if os.path.exists(config_path):
        return "%s already exists, not overwriting" % config_path
    config = generate(device)
    save(config_path, config)


def generate(device):
    """
    Generate a default configuration dictionary for a given input
    device.

    :param device: device to generate configuration for
    :type device: evdev.InputDevice
    :returns: default configuration dictionary
    :rtype: dict
    """
    config = {
        'grab':     False,
        'actions':  [],
        'axes':     [],
        'buttons':  [],
    }
    capabilities = device.capabilities(verbose=True, absinfo=True)
    for ((_, event_type_id), events) in capabilities.items():
        for (event_names, activator) in events:
            event_name = evmapy.util.first_element(event_names)
            action_base = {
                'sequence': False,
                'hold':     False,
                'type':     'exec',
                'target':   'echo %s' % event_name,
            }
            if event_type_id == evdev.ecodes.ecodes['EV_KEY']:
                config['buttons'].append({
                    'name': event_name,
                    'code': activator,
                })
                action = action_base.copy()
                action['trigger'] = event_name
                config['actions'].append(action)
            elif event_type_id == evdev.ecodes.ecodes['EV_ABS']:
                config['axes'].append({
                    'name': event_name,
                    'code': event_names[1],
                    'min':  activator.min,
                    'max':  activator.max,
                })
                for limit in ('min', 'max'):
                    action = action_base.copy()
                    action['trigger'] = '%s:%s' % (event_name, limit)
                    action['target'] += ' %s' % limit
                    config['actions'].append(action)
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


def load(device, name):
    """
    Load configuration for the given device.

    :param device: device to load configuration for
    :type device: evdev.InputDevice
    :param name: name of the configuration file to load (`None` and `''`
        cause the default configuration file to be used)
    :type name: str
    :returns: processed configuration from the loaded configuration file
    :rtype: dict
    :raises evmapy.config.ConfigError: if an error occurred while
        loading the specified configuration file
    """
    if name:
        info = evmapy.util.get_app_info()
        path = os.path.join(info['config_dir'], os.path.basename(name))
    else:
        path = _get_device_config_path(device)
    try:
        config_input = read(path)
        config = parse(config_input)
    except Exception as exc:
        raise ConfigError(exc, path)
    logging.getLogger().info("%s: loaded %s", device.fn, path)
    return config


def read(path):
    """
    Read configuration file under the given path and return the
    dictionary it represents.

    :param path: path to the file to read
    :type path: str
    :returns: configuration dictionary represented by the given file
    :rtype: dict
    """
    with open(path) as config_file:
        config_input = json.load(config_file)
    return config_input


def parse(config_input):
    """
    Transform the given configuration dictionary into one ready to use
    by the application.

    :param config_input: configuration dictionary to process
    :type config_input: dict
    :returns: processed configuration dictionary
    :rtype: dict
    :raises evmapy.config.ConfigError: when an error is found while
        processing the configuration
    """
    config = {
        'events':   {},
        'grab':     config_input['grab'],
        'map':      {},
    }
    # Every action needs a unique identifier in order for the event
    # multiplexer to be able to remove it from the list of delayed
    # actions; note that we can't directly compare the dictionaries as
    # there may be identical actions configured for two different events
    current_id = 0
    events = config_input['axes'] + config_input['buttons']
    for event in events:
        if 'min' in event and 'max' in event:
            # Axis event
            idle = (event['min'] + event['max']) // 2
        else:
            # Button event
            idle = 0
        event['previous'] = idle
        config['events'][event['code']] = event
        config['map'][event['code']] = []
    for action in config_input['actions']:
        if action['sequence'] and action['hold']:
            raise ConfigError("'hold' cannot be set for sequences")
        action['trigger'] = evmapy.util.as_list(action['trigger'])
        action['trigger_active'] = [False for trigger in action['trigger']]
        action['sequence_cur'] = 1
        action['sequence_done'] = False
        for trigger in action['trigger']:
            event_name = trigger.split(':')[0]
            event = next(e for e in events if e['name'] == event_name)
            if action not in config['map'][event['code']]:
                config['map'][event['code']].append(action)
        action['id'] = current_id
        current_id += 1
    return config
