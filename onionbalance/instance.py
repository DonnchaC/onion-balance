# -*- coding: utf-8 -*-
import datetime
import time

import stem.control

from onionbalance import log
from onionbalance import config
from onionbalance import healthchecks
from onionbalance import util

logger = log.get_logger()


def fetch_instance_descriptors(controller):
    """
    Try fetch fresh descriptors for all HS instances
    """
    logger.info("Initiating fetch of descriptors for all service instances.")

    # pylint: disable=no-member

    while True:
        try:
            # Clear Tor descriptor cache before making fetches by sending
            # the NEWNYM singal
            controller.signal(stem.control.Signal.NEWNYM)
            time.sleep(5)  # Sleep to allow Tor time to build new circuits
        except stem.SocketClosed:
            logger.error("Failed to send NEWNYM signal, socket is closed.")
            util.reauthenticate(controller, logger)
        else:
            break

    unique_instances = set(instance for service in config.services
                           for instance in service.instances)

    # Only try to retrieve the descriptor once for each unique instance
    # address. An instance may be configured under multiple master
    # addressed. We do not want to request the same instance descriptor
    # multiple times.
    # OnionBalance will update all of the matching instances when a
    # descriptor is received.
    for instance in unique_instances:
        while True:
            try:
                instance.fetch_descriptor()
            except stem.SocketClosed:
                logger.error("Failed to fecth descriptor, socket "
                             "is closed")
                util.reauthenticate(controller, logger)
            else:
                break


class Instance(object):
    """
    Instance represents a back-end load balancing hidden service.
    """

    def __init__(self, controller, onion_address, authentication_cookie=None):
        """
        Initialise an Instance object.
        """
        self.controller = controller

        # Onion address for the service instance.
        if onion_address:
            onion_address = onion_address.replace('.onion', '')
        self.onion_address = onion_address
        self.authentication_cookie = authentication_cookie

        # Store the latest set of introduction points for this instance
        self.introduction_points = []

        # Timestamp when last received a descriptor for this instance
        self.received = None

        # Timestamp of the currently loaded descriptor
        self.timestamp = None

        # Flag this instance with its introduction points change. A new
        # master descriptor will then be published as the introduction
        # points have changed.
        self.changed_since_published = False

        # Health status. None = never set
        self.is_healthy = None
        # Has the health status changed since previous run
        # The value reset by Service._instances_health_has_changed()
        self.health_changed = False
        self.last_check_time = None
        self.last_check_duration = None

    def fetch_descriptor(self):
        """
        Try fetch a fresh descriptor for this service instance from the HSDirs
        """
        logger.debug("Trying to fetch a descriptor for instance %s.onion.",
                     self.onion_address)
        try:
            self.controller.get_hidden_service_descriptor(self.onion_address,
                                                          await_result=False)
        except stem.SocketClosed:
            # Tor maybe restarting.
            raise
        except stem.DescriptorUnavailable:
            # Could not find the descriptor on the HSDir
            self.received = None
            logger.warning("No descriptor received for instance %s.onion, "
                           "the instance may be offline.", self.onion_address)

    def update_descriptor(self, parsed_descriptor):
        """
        Update introduction points when a new HS descriptor is received

        Parse the descriptor content and update the set of introduction
        points for this HS instance. Returns True if the introduction
        point set has changed, False otherwise.`
        """

        self.received = datetime.datetime.utcnow()

        logger.debug("Received a descriptor for instance %s.onion.",
                     self.onion_address)

        # Reject descriptor if its timestamp is older than the current
        # descriptor. Prevents HSDirs from replaying old, expired
        # descriptors.
        if self.timestamp and parsed_descriptor.published < self.timestamp:
            logger.error("Received descriptor for instance %s.onion with "
                         "publication timestamp (%s) older than the latest "
                         "descriptor (%s). Ignoring the descriptor.",
                         self.onion_address,
                         parsed_descriptor.published,
                         self.timestamp)
            return False
        else:
            self.timestamp = parsed_descriptor.published

        # Parse the introduction point list, decrypting if necessary
        introduction_points = parsed_descriptor.introduction_points(
            authentication_cookie=self.authentication_cookie
        )

        # If the new introduction points are different, flag this instance
        # as modified. Compare the set of introduction point identifiers
        # (fingerprint of the per IP circuit service key).
        if (set(ip.identifier for ip in introduction_points) !=
                set(ip.identifier for ip in self.introduction_points)):
            self.changed_since_published = True
            self.introduction_points = introduction_points
            return True

        else:
            logger.debug("Introduction points for instance %s.onion matched "
                         "the cached set.", self.onion_address)
            return False


    def check_health(self, conf):
        """Run a health check against the instance
        Update self.is_healthy and self.health_changed
        """
        if conf['type'] is None:  # no health checking
            return

        # conf e.g. {'type': 'http', 'port': 80, 'path': '/', 'timeout': 15}
        port = conf['port']
        timeout = conf['timeout']
        if conf['type'] == 'tcp':
            healthy, ctime, cd = healthchecks.check_tcp(
                self.onion_address, port, timeout)
        elif conf['type'] == 'http':
            healthy, ctime, cd = healthchecks.check_http(
                self.onion_address, port, conf['path'], timeout)
        elif conf['type'] == 'https':
            healthy, ctime, cd = healthchecks.check_https(
                self.onion_address, port, conf['path'], timeout)
        else:
            logger.error("Unexpected check type: %r" % conf['type'])
            return

        self.last_check_time = ctime
        self.last_check_duration = cd
        previous = self.is_healthy
        if healthy != previous:
            if healthy:
                logger.info("Instance %s went online", self.onion_address)
            elif previous == None:
                # onionbalance just started - not a server going down
                logger.info("Instance %s went offline", self.onion_address)
            else:
                logger.warn("Instance %s went offline", self.onion_address)

            self.health_changed = True
            self.is_healthy = healthy

    def __eq__(self, other):
        """
        Instance objects are equal if they have the same onion address.
        """
        if isinstance(other, Instance):
            return self.onion_address == other.onion_address
        else:
            return False

    def __hash__(self):
        """
        Define __hash__ method allowing for set comparison between instances.
        """
        return hash(self.onion_address)
