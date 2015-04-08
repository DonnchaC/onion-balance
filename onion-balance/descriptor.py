# -*- coding: utf-8 -*-
import hashlib
import base64
import textwrap
import datetime

import Crypto.Util.number
import stem

import util
import log
import sys

logger = log.get_logger()


def generate_hs_descriptor(permanent_key, introduction_point_list=None,
                           replica=0, timestamp=None):
    """
    High-level interface for generating a signed HS descriptor

    TODO: Allow generation of descriptors for future timeperiod,
          to help clients with a skewed clock
    """

    if not timestamp:
        timestamp = datetime.datetime.utcnow()
    unix_timestamp = int(timestamp.strftime("%s"))

    permanent_key_block = make_public_key_block(permanent_key)
    permanent_id = util.calc_permanent_id(permanent_key)

    # Calculate the current secret-id-part for this hidden service
    time_period = util.get_time_period(unix_timestamp, permanent_id)
    secret_id_part = util.calc_secret_id_part(time_period, None, replica)
    descriptor_id = util.calc_descriptor_id(permanent_id, secret_id_part)

    # If we have no introduction
    if not introduction_point_list:
        logger.warning("No introduction points for service '%s'. "
                       "Skipping upload." % util.calc_onion_address(
                            permanent_key))
        return None

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
    doc = []
    doc.append("rendezvous-service-descriptor {}".format(desc_id_base32))
    doc.append("version 2")
    doc.append("permanent-key")
    doc.append(permanent_key_block)
    doc.append("secret-id-part {}".format(secret_id_part_base32))
    doc.append("publication-time {}".format(publication_time))
    doc.append("protocol-versions 2,3")
    doc.append("introduction-points")
    doc.append(introduction_points_part)
    doc.append("signature\n")

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
    TOKEN_HSDESCRIPTOR_SIGNATURE = '\nsignature\n'

    # Remove signature block if it exists
    if TOKEN_HSDESCRIPTOR_SIGNATURE in descriptor:
        descriptor = descriptor[:descriptor.find(TOKEN_HSDESCRIPTOR_SIGNATURE)
                                + len(TOKEN_HSDESCRIPTOR_SIGNATURE)]
    else:
        descriptor = descriptor.strip() + TOKEN_HSDESCRIPTOR_SIGNATURE

    descriptor_digest = hashlib.sha1(descriptor.encode('utf-8')).digest()
    signature_with_headers = sign_digest(descriptor_digest, service_key)
    return descriptor + signature_with_headers


def fetch_descriptor(controller, onion_address, hsdir=None):
    """
    Try fetch a HS descriptor from any of the responsible HSDirs

    TODO: Allow a custom HSDir to be specified
    """
    logger.info("Sending HS descriptor fetch for %s.onion" % onion_address)
    response = controller.msg("HSFETCH %s" % (onion_address))
    (response_code, divider, response_content) = response.content()[0]
    if not response.is_ok():
        if response_code == "510":
            logger.error("This version of Tor does not support HSFETCH command")
            sys.exit(1)
        if response_code == "552":
            raise stem.InvalidRequest(response_code, response_content)
        else:
            raise stem.ProtocolError("HSFETCH returned unexpected "
                                     "response code: %s" % response_code)
        pass


def upload_descriptor(controller, signed_descriptor, hsdirs=None):
    """
    Upload descriptor via the Tor control port

    If no HSDir's are specified, Tor will upload to what it thinks are the
    responsible directories
    """
    logger.debug("Sending HS descriptor upload")

    # Provide server fingerprints to control command if HSDirs are specified.
    if hsdirs:
        server_args = ' '.join([("SERVER=%s" % hsdir) for hsdir in hsdirs])
    else:
        server_args = ""

    response = controller.msg("HSPOST%s\r\n%s\r\n.\r\n" %
                              (server_args, signed_descriptor))

    (response_code, divider, response_content) = response.content()[0]
    if not response.is_ok():
        if response_code == "552":
            raise stem.InvalidRequest(response_code, response_content)
        else:
            raise stem.ProtocolError("HSPOST returned unexpected response "
                                     "code: %s" % response_code)
