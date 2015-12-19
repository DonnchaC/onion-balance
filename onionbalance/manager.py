# -*- coding: utf-8 -*-
"""
Load balance a hidden service across multiple (remote) Tor instances by
create a hidden service descriptor containing introduction points from
each instance.
"""
import signal
import sys
import argparse
import time
import logging

# import Crypto.PublicKey
import stem
from stem.control import Controller, EventType
from setproctitle import setproctitle
import schedule

from onionbalance import log
from onionbalance import settings
from onionbalance import config
from onionbalance import eventhandler

import onionbalance.service
import onionbalance.instance
from onionbalance import __version__

logger = log.get_logger()


def handle_sigint_sigterm(signum, frame):
    """Handle SIGINT (Ctrl-C) and SIGTERM"""
    logger.info("Signal %d received, exiting", signum)
    handle_sigint_sigterm.__tor_controller.close()
    logging.shutdown()
    sys.exit(0)


def setup_signal_handler(controller):
    handle_sigint_sigterm.__tor_controller = controller
    signal.signal(signal.SIGTERM, handle_sigint_sigterm)
    signal.signal(signal.SIGINT, handle_sigint_sigterm)


def parse_cmd_args():
    """
    Parses and returns command line arguments.
    """

    parser = argparse.ArgumentParser(
        description="onionbalance distributes the requests for a Tor hidden "
        "services across multiple Tor instances.")

    parser.add_argument("-i", "--ip", type=str, default="127.0.0.1",
                        help="Tor controller IP address")

    parser.add_argument("-p", "--port", type=int, default=9051,
                        help="Tor controller port")

    parser.add_argument("-c", "--config", type=str,
                        default="config.yaml", help="Config file location")

    parser.add_argument("-v", "--verbosity", type=str, default="info",
                        help="Minimum verbosity level for logging.  Available "
                             "in ascending order: debug, info, warning, "
                             "error, critical).  The default is info.")

    parser.add_argument("--version", action='store_true',
                        help="Display the onionbalance version and exit.")

    args = parser.parse_args()
    if args.version:
        print("onionbalance version: {}".format(onionbalance.__version__))
        sys.exit(0)

    return args


def main():
    """
    Entry point when invoked over the command line.
    """
    args = parse_cmd_args()
    config_file_options = settings.parse_config_file(args.config)
    setproctitle('onionbalance')

    # Update global configuration with options specified in the config file
    for setting in dir(config):
        if setting.isupper() and config_file_options.get(setting):
            setattr(config, setting, config_file_options.get(setting))

    logger.setLevel(logging.__dict__[args.verbosity.upper()])
    logger.info("Starting OnionBalance v. %s", __version__)

    # Create a connection to the Tor control port
    try:
        controller = Controller.from_port(address=args.ip, port=args.port)
    except stem.SocketError as exc:
        logger.error("Unable to connect to Tor control port: %s", exc)
        sys.exit(1)
    else:
        logger.debug("Successfully connected to the Tor control port.")

    setup_signal_handler(controller)

    try:
        controller.authenticate()
    except stem.connection.AuthenticationFailure as exc:
        logger.error("Unable to authenticate to Tor control port: %s", exc)
        sys.exit(1)
    else:
        logger.debug("Successfully authenticated to the Tor control port.")

    # Disable no-member due to bug with "Instance of 'Enum' has no * member"
    # pylint: disable=no-member

    # Check that the Tor client supports the HSPOST control port command
    if not controller.get_version() >= stem.version.Requirement.HSPOST:
        logger.error("A Tor version >= %s is required. You may need to "
                     "compile Tor from source or install a package from "
                     "the experimental Tor repository.",
                     stem.version.Requirement.HSPOST)
        sys.exit(1)

    # Load the keys and config for each onion service
    settings.initialize_services(controller,
                                 config_file_options.get('services'))

    # Finished parsing all the config file.

    handler = eventhandler.EventHandler()
    controller.add_event_listener(handler.new_desc,
                                  EventType.HS_DESC)
    controller.add_event_listener(handler.new_desc_content,
                                  EventType.HS_DESC_CONTENT)

    # Schedule descriptor fetch and upload events
    schedule.every(config.REFRESH_INTERVAL).seconds.do(
        onionbalance.instance.fetch_instance_descriptors, controller)
    schedule.every(config.PUBLISH_CHECK_INTERVAL).seconds.do(
        onionbalance.service.publish_all_descriptors)

    # Run initial fetch of HS instance descriptors
    schedule.run_all(delay_seconds=30)

    # Begin main loop to poll for HS descriptors
    while True:
        try:
            schedule.run_pending()
        except Exception:
            logger.error("Unexpected exception:", exc_info=True)
        time.sleep(1)

    return 0
