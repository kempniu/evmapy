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
Unit tests for the util module
"""

import pwd
import unittest
import unittest.mock

import evmapy.util


class TestUtil(unittest.TestCase):

    """
    Test all functions
    """

    def test_util_as_list(self):
        """
        Test as_list()
        """
        retval = evmapy.util.as_list('foo')
        self.assertEqual(retval, ['foo'])
        retval = evmapy.util.as_list(['foo', 'bar'])
        self.assertEqual(retval, ['foo', 'bar'])

    def test_util_first_element(self):
        """
        Test first_element()
        """
        retval = evmapy.util.first_element('foo')
        self.assertEqual(retval, 'foo')
        retval = evmapy.util.first_element(['foo', 'bar'])
        self.assertEqual(retval, 'foo')
        retval = evmapy.util.first_element(('foo', 'bar'))
        self.assertEqual(retval, 'foo')

    def test_util_app_info(self):
        """
        Test get_app_info()
        """
        info = evmapy.util.get_app_info()
        self.assertIsInstance(info['name'], str)
        self.assertIsInstance(info['version'], str)
        self.assertIsInstance(info['user'], pwd.struct_passwd)
        self.assertIsInstance(info['config_dir'], str)
