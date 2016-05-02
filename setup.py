# -*- coding: utf-8 -*-

"""setup.py: setuptools control."""

import io
import os

from setuptools import setup

# Read version and other info from package's __init.py file
module_info = {}
init_path = os.path.join(os.path.dirname(__file__), 'onionbalance',
                         '__init__.py')
with open(init_path) as init_file:
    exec(init_file.read(), module_info)


def read(*names, **kwargs):
    return io.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8")
    ).read()

setup(
    name="OnionBalance",
    packages=["onionbalance"],
    entry_points={
        "console_scripts": [
            'onionbalance = onionbalance.manager:main',
            'onionbalance-config = onionbalance.settings:generate_config',
        ]},
    description="OnionBalance provides load-balancing and redundancy for Tor "
                "hidden services by distributing requests to multiple backend "
                "Tor instances.",
    long_description=read('README.rst'),
    version=module_info.get('__version__'),
    author=module_info.get('__author__'),
    author_email=module_info.get('__contact__'),
    url=module_info.get('__url__'),
    license=module_info.get('__license__'),
    keywords='tor',
    install_requires=[
        'setuptools',
        'stem>=1.4.0-dev',
        'PyYAML>=3.11',
        'pycrypto>=2.6.1',
        'future>=0.14.0',
        ],
    tests_require=['tox', 'pytest-mock', 'pytest', 'mock', 'pexpect'],
    package_data={'onionbalance': ['data/*']},
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ]
)
