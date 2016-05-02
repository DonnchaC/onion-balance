0.1.4
-----

- Remove the 'schedule' dependency to simplify Debian backporting

0.1.3
-----

- Streamline the integration tests by using Tor and Chutney from the
  upstream repositories.
- Fix bug when HSFETCH is called with a HSDir argument (3d225fd).
- Remove the 'schedule' package from the source code and re-add it as a
  dependency. This Python package is now packaged for Debian.
- Extensively restructure the documentation to make it more comprehensible.
- Add --version argument to the command line
- Add configuration options to output log entries to a log file.

0.1.2
-----

- Remove dependency on the schedule package to prepare for packaging
  OnionBalance in Debian. The schedule code is now included directly in
  onionbalance/schedule.py.
- Fix the executable path in the help messages for onionbalance and
  onionbalance-config.

0.1.1
-----

- Patch to resolve issue when saving generated torrc files from
  onionbalance-config in Python 2.


0.1.0
-----

-  Initial release
