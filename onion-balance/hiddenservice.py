# -*- coding: utf-8 -*-
import datetime
import random
import time
import base64

import Crypto.PublicKey.RSA
import stem.descriptor.hidden_service_descriptor

import descriptor
import util
import log
import config

logger = log.get_logger()


def fetch_all_descriptors(controller):
    """
    Try fetch fresh descriptors for all HS instances
    """
    logger.info("Running periodic descriptor fetch")

    # Clear Tor descriptor cache before fetches by sending NEWNYM
    controller.signal(stem.control.Signal.NEWNYM)
    time.sleep(5)

    for service in config.cfg.hidden_services:
        for instance in service.instances:
                instance.fetch_descriptor()


def publish_all_descriptors():
    """
    Called periodically to upload new super-descriptors if needed
    """
    logger.info("Running periodic descriptor publish")
    for service in config.cfg.hidden_services:
        service.publish()


class HiddenService(object):
    """
    HiddenService represents a front-facing hidden service which should
    be load-balanced.
    """

    def __init__(self, controller, service_key=None, instances=None):
        """
        Initialise a HiddenService object.
        """
        self.controller = controller

        # Service key must be a valid PyCrypto RSA key object
        if not isinstance(service_key, Crypto.PublicKey.RSA._RSAobj):
            raise ValueError("Service key is not a valid RSA object")
        else:
            self.service_key = service_key

        # List of load balancing Instances for this hidden service
        if not instances:
            instances = []
        self.instances = instances

        self.onion_address = util.calc_onion_address(self.service_key)
        self.last_uploaded = None

    def _intro_points_modified(self):
        """
        Check if the introduction point set has changed since last
        publish.
        """
        for instance in self.instances:
            if instance.changed_since_published:
                return True

        # No introduction points have changed
        return False

    def _descriptor_expiring(self):
        """
        Check if the last uploaded super descriptor is old and should be
        uploaded again.
        """
        if not self.last_uploaded:
            # No descriptor uploaded yet, we should publish.
            return True

        descriptor_age = (datetime.datetime.utcnow() - self.last_uploaded)
        if (descriptor_age.total_seconds() >
                config.cfg.config.get("descriptor_upload_period")):
            return True

        return False

    def _descriptor_id_changing_soon(self):
        """
        If the descriptor ID will change soon, upload under both descriptor IDs
        """
        seconds_valid = util.get_seconds_valid(
            time.time(), base64.b32decode(self.onion_address, 1))

        # Check if descriptor ID will be changing within the overlap period.
        if seconds_valid < config.cfg.config.get('descriptor_overlap_period'):
            return True

        return False

    def _get_combined_introduction_points(self):
        """
        Choose set of introduction points from all fresh descriptors

        TODO: There are probably better algorithms for choosing which
        introduction points to include. If we have more than
        `max_intro_points` introduction points, we will need to exclude
        some.  It probably sensible to prefer IPs which are new and
        haven't been included in any previous descriptors. Clients with
        an old descriptor will continue trying previously published IPs
        if they still work.
        """

        combined_intro_points = []
        for instance in self.instances:

            if not instance.last_fetched:
                logger.debug("No descriptor fetched for instance '%s' yet. "
                             "Skipping!" % instance.onion_address)
                continue

            # Check if the intro points are too old
            intro_age = datetime.datetime.utcnow() - instance.last_fetched
            if intro_age.total_seconds() > 60 * 60:
                logger.info("Our introduction points for instance '%s' "
                            "are too old. Skipping!" % instance.onion_address)
                continue

            # Our IP's are recent enough, include them
            instance.changed_since_published = False
            combined_intro_points.extend(instance.introduction_points)

        # Choose up to `max_intro_points` IPs from the combined set
        max_introduction_points = min(
            len(combined_intro_points),
            config.cfg.config.get("max_intro_points")
        )
	#print [ip.service_key for ip in combined_intro_points]

        choosen_intro_points = random.sample(combined_intro_points,
                                             max_introduction_points)
        # Shuffle IP's to try reveal less information about which
        # instances are online and have introduction points included.
        random.shuffle(choosen_intro_points)

        logger.debug("Selected %d IPs (of %d) for service '%s'" %
                     (len(choosen_intro_points), len(combined_intro_points),
                      self.onion_address))

        return choosen_intro_points

    def _get_signed_descriptor(self, replica=0, timestamp=None):
        """
        Generate a signed HS descriptor for this hidden service
        """

        # Select a set of introduction points from this HS's load
        # balancing instances.
        introduction_points = self._get_combined_introduction_points()

        signed_descriptor = descriptor.generate_hs_descriptor(
            self.service_key,
            introduction_point_list=introduction_points,
            replica=replica,
            timestamp=timestamp
        )
        return signed_descriptor

    def _upload_descriptor(self, timestamp=None):
        """
        Create, sign and upload a super-descriptors for this HS
        """
        for replica in range(0, config.cfg.config.get("replicas")):
            signed_descriptor = self._get_signed_descriptor(
                replica=replica, timestamp=timestamp)

            # Upload if a signed descriptor was generated successfully
            if signed_descriptor:
                descriptor.upload_descriptor(self.controller,
                                             signed_descriptor)

        self.last_uploaded = datetime.datetime.utcnow()

    def publish(self, force=False):
        """
        Publish descriptor if have new IP's or if descriptor has expired
        """

        if (    self._intro_points_modified() or
                self._descriptor_expiring() or
                force):
            logger.info("Publishing new descriptor for '%s'" %
                        self.onion_address)

            self._upload_descriptor()

            # If the descriptor ID will change soon, need to upload under
            # the new ID too.
            if self._descriptor_id_changing_soon():
                logger.info("Publishing new descriptor for '%s' under "
                            "next descriptor ID" % self.onion_address)
                next_time = datetime.datetime.utcnow() + datetime.timedelta(1)
                self._upload_descriptor(timestamp=next_time)


class Instance(object):
    """
    Instance represents a back-end load balancing hidden service.
    """

    def __init__(self, controller, service_privkey, onion_address, authentication_cookie):
        """
        Initialise an Instance object.
        """
        self.controller = controller
        self.service_privkey = service_privkey
        self.onion_address = onion_address
        self.authentication_cookie = authentication_cookie

        self.introduction_points = []
        self.last_fetched = None
        self.changed_since_published = False

    def fetch_descriptor(self):
        """
        Try fetch a fresh descriptor for this back-end HS instance.
        """
        logger.debug("Trying to fetch a descriptor of instance '%s'" %
                     self.onion_address)
        return descriptor.fetch_descriptor(self.controller, self.onion_address)

    def update_descriptor(self, descriptor_content):
        """
        Update introduction points when a new HS descriptor is received

        Parse the descriptor content and update the set of introduction
        points for this HS instance.
        """

        logger.info("Received a descriptor for %s" % self.onion_address)
        #print descriptor_content


        self.last_fetched = datetime.datetime.utcnow()

        # Parse and store this descriptors introduction points.
        parsed_descriptor = stem.descriptor.hidden_service_descriptor.\
            HiddenServiceDescriptor(descriptor_content)
        #print parsed_descriptor
        # Parse the introduction point list, decrypting if necessary
        introduction_points = parsed_descriptor.introduction_points(
            authentication_cookie=self.authentication_cookie)
        print introduction_points
        # If the new intro point set is different, flag this HS instance
        # as modified.
        if introduction_points != self.introduction_points:
            logger.info("New IPs found for '%s'" % self.onion_address)
            self.changed_since_publish = True
            self.introduction_points = introduction_points

        else:
            logger.info("IPs for '%s' matched the cached set" %
                        self.onion_address)
