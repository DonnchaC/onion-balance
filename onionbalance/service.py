# -*- coding: utf-8 -*-
import datetime
import time
import base64

import Crypto.PublicKey.RSA
import stem

from onionbalance import descriptor
from onionbalance import util
from onionbalance import log
from onionbalance import config
from onionbalance import consensus

logger = log.get_logger()


def publish_all_descriptors():
    """
    Called periodically to upload new super-descriptors if needed

    .. todo:: Publishing descriptors for different services at the same time
              will leak that they are related. Descriptors should
              be published individually at a random interval to avoid
              correlation.
    """
    logger.debug("Checking if any master descriptors should be published.")
    for service in config.services:
        service.descriptor_publish()


class Service(object):
    """
    Service represents a front-facing hidden service which should
    be load-balanced.
    """

    def __init__(self, controller, service_key=None, instances=None):
        """
        Initialise a HiddenService object.
        """
        self.controller = controller

        # Service key must be a valid PyCrypto RSA key object
        if isinstance(service_key, Crypto.PublicKey.RSA._RSAobj):
            self.service_key = service_key
        else:
            raise ValueError("Service key is not a valid RSA object.")

        # List of instances for this onion service
        if not instances:
            instances = []
        self.instances = instances

        # Calculate the onion address for this service
        self.onion_address = util.calc_onion_address(self.service_key)

        # Timestamp when this descriptor was last attempted
        self.uploaded = None

    def _intro_points_modified(self):
        """
        Check if the introduction point set has changed since last
        publish.
        """
        return any(instance.changed_since_published
                   for instance in self.instances)

    def _descriptor_not_uploaded_recently(self):
        """
        Check if the master descriptor hasn't been uploaded recently
        """
        if not self.uploaded:
            # Descriptor never uploaded
            return True

        descriptor_age = (datetime.datetime.utcnow() - self.uploaded)
        if (descriptor_age.total_seconds() > config.DESCRIPTOR_UPLOAD_PERIOD):
            return True
        else:
            return False

    def _descriptor_id_changing_soon(self):
        """
        If the descriptor ID will change soon, upload under both descriptor IDs
        """
        permanent_id = base64.b32decode(self.onion_address, 1)
        seconds_valid = util.get_seconds_valid(time.time(), permanent_id)

        # Check if descriptor ID will be changing within the overlap period.
        if seconds_valid < config.DESCRIPTOR_OVERLAP_PERIOD:
            return True
        else:
            return False

    def _select_introduction_points(self):
        """
        Choose set of introduction points from all fresh descriptors

        Returns a descriptor.IntroductionPointSet() which can be used to
        choose introduction points.
        """
        available_intro_points = []

        # Loop through each instance and determine fresh intro points
        for instance in self.instances:
            if not instance.received:
                logger.info("No descriptor received for instance %s.onion "
                            "yet.", instance.onion_address)
                continue

            # The instance may be offline if no descriptor has been received
            # for it recently or if the received descriptor's timestamp is
            # too old
            received_age = datetime.datetime.utcnow() - instance.received
            timestamp_age = datetime.datetime.utcnow() - instance.timestamp
            received_age = received_age.total_seconds()
            timestamp_age = timestamp_age.total_seconds()

            if (received_age > config.DESCRIPTOR_UPLOAD_PERIOD or
                    timestamp_age > (4 * 60 * 60)):
                logger.info("Our descriptor for instance %s.onion is too old. "
                            "The instance may be offline. It's introduction "
                            "points will not be included in the master "
                            "descriptor.", instance.onion_address)
                continue
            else:
                # Include this instance's introduction points
                instance.changed_since_published = False
                available_intro_points.append(instance.introduction_points)

        return descriptor.IntroductionPointSet(available_intro_points)

    def _publish_descriptor(self, deviation=0):
        """
        Create, sign and upload master descriptors for this service
        """

        # Retrieve the set of available introduction points
        intro_point_set = self._select_introduction_points()
        max_intro_points = config.MAX_INTRO_POINTS

        # Upload multiple unique descriptors which contain different
        # subsets of the available introduction points.
        # (https://github.com/DonnchaC/onionbalance/issues/16)
        distinct_descriptors = config.DISTINCT_DESCRIPTORS

        # If we have <= MAX_INTRO_POINTS we should choose the introduction
        # points now and use the same set in every descriptor. Using the
        # same set of introduction points will look more like a standard
        # Tor client.
        num_intro_points = len(intro_point_set)

        if num_intro_points <= max_intro_points:
            intro_points = intro_point_set.choose(num_intro_points)
            logger.debug("We have %d IPs, not using distinct descriptors.",
                         len(intro_point_set))
            distinct_descriptors = False

        for replica in range(0, config.REPLICAS):
            # Using distinct descriptors, choose a new set of intro points
            # for each descriptor and upload it to individual HSDirs.
            if distinct_descriptors:
                descriptor_id = util.calc_descriptor_id_b32(
                    self.onion_address,
                    time=time.time(),
                    replica=replica,
                    deviation=deviation,
                )
                responsible_hsdirs = consensus.get_hsdirs(descriptor_id)

                for hsdir in responsible_hsdirs:
                    intro_points = intro_point_set.choose(max_intro_points)
                    try:
                        signed_descriptor = (
                            descriptor.generate_service_descriptor(
                                self.service_key,
                                introduction_point_list=intro_points,
                                replica=replica,
                                deviation=deviation
                            ))
                    except ValueError as exc:
                        logger.warning("Error generating descriptor: %s", exc)
                        continue

                    # Signed descriptor was generated successfully, upload it
                    # to the respective HSDir
                    self._upload_descriptor(signed_descriptor, replica,
                                            hsdirs=hsdir)
                logger.info("Published distinct master descriptors for "
                            "service %s.onion under replica %d.",
                            self.onion_address, replica)

            else:
                # Not using distinct descriptors, upload one descriptor
                # under each replica and let Tor pick the HSDirs.
                try:
                    signed_descriptor = descriptor.generate_service_descriptor(
                        self.service_key,
                        introduction_point_list=intro_points,
                        replica=replica,
                        deviation=deviation
                    )
                except ValueError as exc:
                    logger.warning("Error generating descriptor: %s", exc)
                    continue

                # Signed descriptor was generated successfully, upload it
                self._upload_descriptor(signed_descriptor, replica)
                logger.info("Published a descriptor for service %s.onion "
                            "under replica %d.", self.onion_address, replica)

        # It would be better to set last_uploaded when an upload succeeds and
        # not when an upload is just attempted. Unfortunately the HS_DESC #
        # UPLOADED event does not provide information about the service and
        # so it can't be used to determine when descriptor upload succeeds
        self.uploaded = datetime.datetime.utcnow()

    def _upload_descriptor(self, signed_descriptor, replica, hsdirs=None):
        """
        Convenience method to upload a descriptor
        Handle some error checking and logging inside the Service class
        """
        if hsdirs and not isinstance(hsdirs, list):
            hsdirs = [hsdirs]

        while True:
            try:
                descriptor.upload_descriptor(self.controller,
                                             signed_descriptor, hsdirs=hsdirs)
                break
            except stem.SocketClosed:
                logger.error("Error uploading descriptor for service "
                             "%s.onion, Socket is closed.",
                             self.onion_address)
                util.reauthenticate(self.controller, logger)
            except stem.ControllerError:
                logger.exception("Error uploading descriptor for service "
                                 "%s.onion.", self.onion_address)
                break

    def descriptor_publish(self, force_publish=False):
        """
        Publish descriptor if have new IP's or if descriptor has expired
        """

        # A descriptor should be published if any of the following conditions
        # are True
        if any([self._intro_points_modified(),  # If any IPs have changed
                self._descriptor_not_uploaded_recently(),
                force_publish]):

            logger.debug("Publishing a descriptor for service %s.onion.",
                         self.onion_address)
            self._publish_descriptor()

            # If the descriptor ID will change soon, need to upload under
            # the new ID too.
            if self._descriptor_id_changing_soon():
                logger.info("Publishing a descriptor for service %s.onion "
                            "under next descriptor ID.", self.onion_address)
                self._publish_descriptor(deviation=1)

        else:
            logger.debug("Not publishing a new descriptor for service "
                         "%s.onion.", self.onion_address)
