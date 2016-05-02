# -*- coding: utf-8 -*-
"""
Load balance a hidden service across multiple (remote) Tor instances by
create a hidden service descriptor containing introduction points from
each instance.
"""
import os
import sys
import argparse
import logging

# import Crypto.PublicKey
import stem
from stem.control import Controller, EventType

from onionbalance import log
from onionbalance import settings
from onionbalance import config
from onionbalance import eventhandler
from onionbalance import scheduler
from onionbalance import status

import onionbalance.service
import onionbalance.instance

logger = log.get_logger()


def parse_cmd_args():
    """
    Parses and returns command line arguments.
    """

    parser = argparse.ArgumentParser(
        description="onionbalance distributes the requests for a Tor hidden "
        "services across multiple Tor instances.")

    parser.add_argument("-i", "--ip", type=str, default=None,
                        help="Tor controller IP address")

    parser.add_argument("-p", "--port", type=int, default=None,
                        help="Tor controller port")

    parser.add_argument("-c", "--config", type=str,
                        default=os.environ.get('ONIONBALANCE_CONFIG',
                                               "config.yaml"),
                        help="Config file location")

    parser.add_argument("-v", "--verbosity", type=str, default=None,
                        help="Minimum verbosity level for logging.  Available "
                             "in ascending order: debug, info, warning, "
                             "error, critical).  The default is info.")

    parser.add_argument('--version', action='version',
                        version='onionbalance %s' % onionbalance.__version__)

    return parser


def main():
    """
    Entry point when invoked over the command line.
    """
    args = parse_cmd_args().parse_args()
    config_file_options = settings.parse_config_file(args.config)

    # Update global configuration with options specified in the config file
    for setting in dir(config):
        if setting.isupper() and config_file_options.get(setting):
            setattr(config, setting, config_file_options.get(setting))

    # Override the log level if specified on the command line.
    if args.verbosity:
        config.LOG_LEVEL = args.verbosity.upper()

    # Write log file if configured in environment variable or config file
    if config.LOG_LOCATION:
        log.setup_file_logger(config.LOG_LOCATION)

    logger.setLevel(logging.__dict__[config.LOG_LEVEL.upper()])

    # Create a connection to the Tor control port
    try:
        tor_address = (args.ip or config.TOR_ADDRESS)
        tor_port = (args.port or config.TOR_PORT)

        controller = Controller.from_port(address=tor_address, port=tor_port)
    except stem.SocketError as exc:
        logger.error("Unable to connect to Tor control port: %s", exc)
        sys.exit(1)
    else:
        logger.debug("Successfully connected to the Tor control port.")

    try:
        controller.authenticate(password=config.TOR_CONTROL_PASSWORD)
    except stem.connection.AuthenticationFailure as exc:
        logger.error("Unable to authenticate to Tor control port: %s", exc)
        sys.exit(1)
    else:
        logger.debug("Successfully authenticated to the Tor control port.")

    status_socket = status.StatusSocket(config.STATUS_SOCKET_LOCATION)
    eventhandler.SignalHandler(controller, status_socket)

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
    controller.add_event_listener(handler.new_status,
                                  EventType.STATUS_GENERAL)
    controller.add_event_listener(handler.new_desc,
                                  EventType.HS_DESC)
    controller.add_event_listener(handler.new_desc_content,
                                  EventType.HS_DESC_CONTENT)

    # Schedule descriptor fetch and upload events
    scheduler.add_job(config.REFRESH_INTERVAL,
                      onionbalance.instance.fetch_instance_descriptors,
                      controller)
    scheduler.add_job(config.PUBLISH_CHECK_INTERVAL,
                      onionbalance.service.publish_all_descriptors)

    try:
        # Run initial fetch of HS instance descriptors
        scheduler.run_all(delay_seconds=30)

        # Begin main loop to poll for HS descriptors
        scheduler.run_forever(check_interval=1,
                              catch_all_exceptions=True)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping the "
                    "management server.")
    return 0
