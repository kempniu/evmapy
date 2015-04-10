from setuptools import setup

import evmapy.util


setup(
    name = 'evmapy',
    version = evmapy.util.get_app_info()['version'],
    author = 'Michał Kępień',
    author_email = 'github@kempniu.pl',
    description = 'An evdev event mapper',
    license = 'GPL2',
    url = 'https://github.com/kempniu/evmapy',
    packages = [
        'evmapy',
    ],
    install_requires = [
        'evdev',
    ],
    entry_points = {
        'console_scripts':  [
            'evmapy = evmapy.__main__:main',
        ],
    },
    test_suite = 'tests',
)
