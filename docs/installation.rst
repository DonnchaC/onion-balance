Installation
============

OnionBalance requires at least one system that is running the OnionBalance
management server.

The OnionBalance software does not need to be installed on the
backend servers which provide the hidden service content (i.e. web site,
IRC server etc.).

OnionBalance is not yet packaged for most Linux and BSD. The tool can be
installed from PyPI or directly from the Git repository:

.. code-block:: console

    # pip install onionbalance

or

.. code-block:: console

    $ git clone https://github.com/DonnchaC/onionbalance.git
    $ cd onionbalance
    # python setup.py install

All tagged releases on Github or PyPi are signed with my GPG key:

::

    pub   4096R/0x3B0D706A7FBFED86 2013-06-27 [expires: 2016-07-11]
          Key fingerprint = 7EFB DDE8 FD21 11AE A7BE  1AA6 3B0D 706A 7FBF ED86
    uid                 [ultimate] Donncha O'Cearbhaill <donncha@donncha.is>
    sub   3072R/0xD60D64E73458F285 2013-06-27 [expires: 2016-07-11]
    sub   3072R/0x7D49FC2C759AA659 2013-06-27 [expires: 2016-07-11]
    sub   3072R/0x2C9C6F4ABBFCF7DD 2013-06-27 [expires: 2016-07-11]

If you are running Debian unstable or testing, you can install onionshare with the following command:

.. code-block:: console

   # apt-get install onionshare
