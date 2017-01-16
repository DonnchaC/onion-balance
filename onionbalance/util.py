# -*- coding: utf-8 -*-
import hashlib
import struct
import datetime
import getpass
import base64
import binascii
import os
import stem
import time

# import Crypto.Util
import Crypto.PublicKey

from onionbalance import config


def add_pkcs1_padding(message):
    """Add PKCS#1 padding to **message**."""
    padding = b''
    typeinfo = b'\x00\x01'
    separator = b'\x00'
    padding = b'\xFF' * (125 - len(message))
    padded_message = typeinfo + padding + separator + message
    assert len(padded_message) == 128
    return padded_message


def get_asn1_sequence(rsa_key):
    seq = Crypto.Util.asn1.DerSequence()
    seq.append(rsa_key.n)
    seq.append(rsa_key.e)
    asn1_seq = seq.encode()
    return asn1_seq


def calc_key_digest(rsa_key):
    """Calculate the SHA1 digest of an RSA key"""
    return hashlib.sha1(get_asn1_sequence(rsa_key)).digest()


def calc_permanent_id(rsa_key):
    return calc_key_digest(rsa_key)[:10]


def calc_onion_address(rsa_key):
    return base64.b32encode(calc_permanent_id(rsa_key)).decode().lower()


def calc_descriptor_id(permanent_id, secret_id_part):
    return hashlib.sha1(permanent_id + secret_id_part).digest()


def get_time_period(time, permanent_id):
    """
    time-period = (current-time + permanent-id-byte * 86400 / 256) / 86400
    """
    permanent_id_byte = int(struct.unpack('B', permanent_id[0:1])[0])
    return int((int(time) + permanent_id_byte * 86400 / 256) / 86400)


def get_seconds_valid(time, permanent_id):
    """
    Calculate seconds until the descriptor ID changes
    """
    permanent_id_byte = int(struct.unpack('B', permanent_id[0:1])[0])
    return 86400 - int((int(time) + permanent_id_byte * 86400 / 256) % 86400)


def calc_secret_id_part(time_period, descriptor_cookie, replica):
    """
    secret-id-part = H(time-period | descriptor-cookie | replica)
    """
    secret_id_part = hashlib.sha1()
    secret_id_part.update(struct.pack('>I', time_period)[:4])
    if descriptor_cookie:
        secret_id_part.update(descriptor_cookie)
    secret_id_part.update(binascii.unhexlify('{0:02X}'.format(replica)))
    return secret_id_part.digest()


def calc_descriptor_id_b32(onion_address, time, replica, deviation=0,
                           descriptor_cookie=None):
    """
    High level function to calculate the descriptor ID for a hidden
    service.

    The onion address and returned descriptor ID are both base32 encoded.
    """
    permanent_id = base64.b32decode(onion_address, 1)
    time_period = get_time_period(time, permanent_id) + int(deviation)
    secret_id_part = calc_secret_id_part(time_period, descriptor_cookie,
                                         replica)
    descriptor_id = calc_descriptor_id(permanent_id, secret_id_part)

    return base64.b32encode(descriptor_id).decode('utf-8').lower()


def rounded_timestamp(timestamp=None):
    """
    Create timestamp rounded down to the nearest hour
    """
    if not timestamp:
        timestamp = datetime.datetime.utcnow()
    timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
    return timestamp.strftime('%Y-%m-%d %H:%M:%S')


def base32_encode_str(byte_str):
    """
    Encode bytes as lowercase base32 string
    """
    return base64.b32encode(byte_str).lower().decode('utf-8')


def key_decrypt_prompt(key_file, retries=3):
    """
    Try open an PEM encrypted private key, prompting the user for a
    passphrase if required.
    """

    key_passphrase = None
    with open(key_file, 'rt') as handle:
        pem_key = handle.read()

        for retries in range(0, retries):
            if "Proc-Type: 4,ENCRYPTED" in pem_key:  # Key looks encrypted
                key_passphrase = getpass.getpass(
                    "Enter the password for the private key (%s): " % key_file)
            try:
                rsa_key = Crypto.PublicKey.RSA.importKey(
                    pem_key, passphrase=key_passphrase)
            except ValueError:
                # Key not decrypted correctly, prompt for passphrase again
                continue
            else:
                # .. todo:: Check the loaded key size in a more reasonable way.
                if rsa_key.has_private() and rsa_key.size() in (1023, 1024):
                    return rsa_key
                else:
                    raise ValueError("The specified key was not a 1024 bit "
                                     "private key.")

    # No private key was imported
    raise ValueError("Could not import RSA key.")


def try_make_dir(path):
    """
    Try to create a directory (including any parent directories)
    """
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise


def is_directory_empty(path):
    """
    Check if a directory contains any files or directories.
    """
    if os.listdir(path):
        return False
    else:
        return True


def reauthenticate(controller, logger):
    """
    Tries to authenticate to the controller
    """
    time.sleep(10)
    try:
        controller.authenticate(password=config.TOR_CONTROL_PASSWORD)
    except stem.connection.AuthenticationFailure:
        logger.error("Failed to re-authenticate controller.")
