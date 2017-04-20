OnionBalance
============

Introduction
------------

The OnionBalance software allows for Tor hidden service requests to be
distributed across multiple backend Tor instances. OnionBalance provides
load-balancing while also making onion services more resilient and reliable
by eliminating single points-of-failure.

- Documentation: https://onionbalance.readthedocs.org
- GitHub: https://github.com/DonnchaC/onionbalance/
- Issue tracker: https://github.com/DonnchaC/onionbalance/issues
- PyPI: https://pypi.python.org/pypi/OnionBalance
- IRC: #onionbalance @ OFTC

|build-status| |docs|

Getting Started
---------------

Installation and usage documentation is available at https://onionbalance.readthedocs.org.

Contact
-------

This software is under active development and likely contains many bugs. Please
open bugs reports on Github if you discover any issues with the software or
documentation.

I can also be contacted by PGP email or on IRC at ``#onionbalance`` on the OFTC network.

::

    pub   4096R/0x3B0D706A7FBFED86 2013-06-27 [expires: 2016-07-11]
          Key fingerprint = 7EFB DDE8 FD21 11AE A7BE  1AA6 3B0D 706A 7FBF ED86
    uid                 [ultimate] Donncha O'Cearbhaill <donncha@donncha.is>
    sub   3072R/0xD60D64E73458F285 2013-06-27 [expires: 2016-07-11]
    sub   3072R/0x7D49FC2C759AA659 2013-06-27 [expires: 2016-07-11]
    sub   3072R/0x2C9C6F4ABBFCF7DD 2013-06-27 [expires: 2016-07-11]

.. |build-status| image:: https://img.shields.io/travis/DonnchaC/onionbalance.svg?style=flat
    :alt: build status
    :scale: 100%
    :target: https://travis-ci.org/DonnchaC/onionbalance


.. |coverage| image:: https://coveralls.io/repos/github/DonnchaC/onionbalance/badge.svg?branch=master
    :alt: Code coverage
    :target: https://coveralls.io/github/DonnchaC/onionbalance?branch=master

.. |docs| image:: https://readthedocs.org/projects/onionbalance/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://onionbalance.readthedocs.org/en/latest/
