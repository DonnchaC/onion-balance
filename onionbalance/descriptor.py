# -*- coding: utf-8 -*-
from future.moves.itertools import zip_longest
import hashlib
import base64
import textwrap
import datetime
import random
import itertools

import Crypto.Util.number
import stem

from onionbalance import util
from onionbalance import log
from onionbalance import config

logger = log.get_logger()


class IntroductionPointSet(object):
    """
    Select a set of introduction points to included in a HS descriptor.

    Provided with a list of available introduction points for each
    backend instance for an onionbalance service. This object will store
    the set of available introduction points and allow IPs to be selected
    from the available set.

    This class tracks which introduction points have already been provided
    and tries to provide the most diverse set of IPs.
    """

    def __init__(self, available_introduction_points):
        # Shuffle the introduction point order before selecting IPs.
        # Randomizing now allows later calls to .choose() to be
        # deterministic.
        for instance_intro_points in available_introduction_points:
            random.shuffle(instance_intro_points)
        random.shuffle(available_introduction_points)

        self.available_intro_points = available_introduction_points
        self.intro_point_generator = self.get_intro_point()

    def __len__(self):
        """Provide the total number of available introduction points"""
        return sum(len(ips) for ips in self.available_intro_points)

    def get_intro_point(self):
        """
        Generator function which yields an introduction point

        Iterates through all available introduction points and try
        to pick IPs breath first across all backend instances. The
        intro point set is wrapped in `itertools.cycle` and will provided
        an infinite series of introduction points.
        """

        # Combine intro points from across the backend instances and flatten
        intro_points = zip_longest(*self.available_intro_points)
        flat_intro_points = itertools.chain.from_iterable(intro_points)
        for intro_point in itertools.cycle(flat_intro_points):
            if intro_point:
                yield intro_point

    def choose(self, count=10, shuffle=True):
        """
        Retrieve N introduction points from the set of IPs

        Where more than `count` IPs are available, introduction points are
        selected to try and achieve the greatest distribution of introduction
        points across all of the available backend instances.

        Return a list of IntroductionPoints.
        """

        # Limit `count` to the available number of IPs to avoid repeats.
        count = min(len(self), count)
        choosen_ips = list(itertools.islice(self.intro_point_generator, count))

        if shuffle:
            random.shuffle(choosen_ips)
        return choosen_ips


def generate_service_descriptor(permanent_key, introduction_point_list=None,
                                replica=0, timestamp=None, deviation=0):
    """
    High-level interface for generating a signed HS descriptor
    """

    if not timestamp:
        timestamp = datetime.datetime.utcnow()
    unix_timestamp = int(timestamp.strftime("%s"))

    permanent_key_block = make_public_key_block(permanent_key)
    permanent_id = util.calc_permanent_id(permanent_key)

    # Calculate the current secret-id-part for this hidden service
    # Deviation allows the generation of a descriptor for a different time
    # period.
    time_period = (util.get_time_period(unix_timestamp, permanent_id) +
                   int(deviation))

    secret_id_part = util.calc_secret_id_part(time_period, None, replica)
    descriptor_id = util.calc_descriptor_id(permanent_id, secret_id_part)

    if not introduction_point_list:
        onion_address = util.calc_onion_address(permanent_key)
        raise ValueError("No introduction points for service %s.onion." %
                         onion_address)

    # Generate the introduction point section of the descriptor
    intro_section = make_introduction_points_part(
        introduction_point_list
    )

    unsigned_descriptor = generate_hs_descriptor_raw(
        desc_id_base32=util.base32_encode_str(descriptor_id),
        permanent_key_block=permanent_key_block,
        secret_id_part_base32=util.base32_encode_str(secret_id_part),
        publication_time=util.rounded_timestamp(timestamp),
        introduction_points_part=intro_section
    )

    signed_descriptor = sign_descriptor(unsigned_descriptor, permanent_key)
    return signed_descriptor


def generate_hs_descriptor_raw(desc_id_base32, permanent_key_block,
                               secret_id_part_base32, publication_time,
                               introduction_points_part):
    """
    Generate hidden service descriptor string
    """
    doc = [
        "rendezvous-service-descriptor {}".format(desc_id_base32),
        "version 2",
        "permanent-key",
        permanent_key_block,
        "secret-id-part {}".format(secret_id_part_base32),
        "publication-time {}".format(publication_time),
        "protocol-versions 2,3",
        "introduction-points",
        introduction_points_part,
        "signature\n",
    ]

    unsigned_descriptor = '\n'.join(doc)
    return unsigned_descriptor


def make_introduction_points_part(introduction_point_list=None):
    """
    Make introduction point block from list of IntroductionPoint objects
    """

    # If no intro points were specified, we should create an empty list
    if not introduction_point_list:
        introduction_point_list = []

    intro = []
    for intro_point in introduction_point_list:
        intro.append("introduction-point {}".format(intro_point.identifier))
        intro.append("ip-address {}".format(intro_point.address))
        intro.append("onion-port {}".format(intro_point.port))
        intro.append("onion-key")
        intro.append(intro_point.onion_key)
        intro.append("service-key")
        intro.append(intro_point.service_key)

    intro_section = '\n'.join(intro).encode('utf-8')
    intro_section_base64 = base64.b64encode(intro_section).decode('utf-8')
    intro_section_base64 = textwrap.fill(intro_section_base64, 64)

    # Add the header and footer:
    intro_points_with_headers = '\n'.join([
        '-----BEGIN MESSAGE-----',
        intro_section_base64,
        '-----END MESSAGE-----'])
    return intro_points_with_headers


def make_public_key_block(key):
    """
    Get ASN.1 representation of public key, base64 and add headers
    """
    asn1_pub = util.get_asn1_sequence(key)
    pub_base64 = base64.b64encode(asn1_pub).decode('utf-8')
    pub_base64 = textwrap.fill(pub_base64, 64)

    # Add the header and footer:
    pub_with_headers = '\n'.join([
        '-----BEGIN RSA PUBLIC KEY-----',
        pub_base64,
        '-----END RSA PUBLIC KEY-----'])
    return pub_with_headers


def sign_digest(digest, private_key):
    """
    Sign, base64 encode, wrap and add Tor signature headers

    The message digest is PKCS1 padded without the optional
    algorithmIdentifier section.
    """

    digest = util.add_pkcs1_padding(digest)
    (signature_long, ) = private_key.sign(digest, None)
    signature_bytes = Crypto.Util.number.long_to_bytes(signature_long, 128)
    signature_base64 = base64.b64encode(signature_bytes).decode('utf-8')
    signature_base64 = textwrap.fill(signature_base64, 64)

    # Add the header and footer:
    signature_with_headers = '\n'.join([
        '-----BEGIN SIGNATURE-----',
        signature_base64,
        '-----END SIGNATURE-----'])
    return signature_with_headers


def sign_descriptor(descriptor, service_key):
    """
    Sign or resign a provided hidden service descriptor
    """
    token_descriptor_signature = '\nsignature\n'

    # Remove signature block if it exists
    if token_descriptor_signature in descriptor:
        descriptor = descriptor[:descriptor.find(token_descriptor_signature) +
                                len(token_descriptor_signature)]
    else:
        descriptor = descriptor.strip() + token_descriptor_signature

    descriptor_digest = hashlib.sha1(descriptor.encode('utf-8')).digest()
    signature_with_headers = sign_digest(descriptor_digest, service_key)
    return descriptor + signature_with_headers


def descriptor_received(descriptor_content):
    """
    Process onion service descriptors retrieved from the HSDir system or
    received directly over the metadata channel.
    """

    try:
        parsed_descriptor = stem.descriptor.hidden_service_descriptor.\
            HiddenServiceDescriptor(descriptor_content, validate=True)
    except ValueError:
        logger.exception("Received an invalid service descriptor.")
        return None

    # Ensure the received descriptor matches the requested descriptor
    permanent_key = Crypto.PublicKey.RSA.importKey(
        parsed_descriptor.permanent_key)
    descriptor_onion_address = util.calc_onion_address(permanent_key)

    # Find the HS instance for this descriptor
    for service in config.services:
        for instance in service.instances:
            if instance.onion_address == descriptor_onion_address:
                # Update the descriptor and exit
                instance.update_descriptor(parsed_descriptor)
                return None

    # No matching service instance was found for the descriptor
    logger.debug("Received a descriptor for an unknown service:\n%s",
                 descriptor_content.decode('utf-8'))
    logger.warning("Received a descriptor with address %s.onion that "
                   "did not match any configured service instances.",
                   descriptor_onion_address)

    return None


def upload_descriptor(controller, signed_descriptor, hsdirs=None):
    """
    Upload descriptor via the Tor control port

    If no HSDirs are specified, Tor will upload to what it thinks are the
    responsible directories
    """
    logger.debug("Beginning service descriptor upload.")

    # Provide server fingerprints to control command if HSDirs are specified.
    if hsdirs:
        server_args = ' '.join([("SERVER={}".format(hsdir))
                                for hsdir in hsdirs])
    else:
        server_args = ""

    # Stem will insert the leading + and trailing '\r\n.\r\n'
    response = controller.msg("HSPOST %s\n%s" %
                              (server_args, signed_descriptor))

    (response_code, divider, response_content) = response.content()[0]
    if not response.is_ok():
        if response_code == "552":
            raise stem.InvalidRequest(response_code, response_content)
        else:
            raise stem.ProtocolError("HSPOST returned unexpected response "
                                     "code: %s\n%s" % (response_code,
                                                       response_content))
