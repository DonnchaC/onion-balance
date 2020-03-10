# -*- coding: utf-8 -*-
import datetime
import string

import pytest
import Crypto.PublicKey.RSA
import stem.descriptor
import hashlib

from binascii import unhexlify

from onionbalance import descriptor

PEM_PRIVATE_KEY = u'\n'.join([
    '-----BEGIN RSA PRIVATE KEY-----',
    'MIICWwIBAAKBgQDXzP6HGtjPSy7uF9OlY7ZmefTVKcFLsq0mSEzQrW5wSiNuYc+d',
    'oSV2OWxPg+1fVe19ES43AUkq/bS/gjAMLOunP6u9FbPDojyh1Vs/6TVqftS3sPkl',
    'Q0ItrrZwAwhtHC0WaEyrwYJNOSCBq3wpupdQhpRyWJFqMwm9+iBCG1QcJQIDAQAB',
    'AoGAegc2Sqm4vgdyozof+R8Ybnw6ISu6XRbNaJ9rqHjZwW9695khsK4GJAM2pwQf',
    '/0/0ukszyfDVMhVC1yREDS59lgzNecItd6nQZWbwr9TFxIoa9ouTqk8PcAoNixTb',
    'wafjPcMmWGakizXeAHiOfazPBH4x2keDQCulxfYxXZxTpyECQQDqZu61kd1S3U7T',
    'BT2NQBd3tHX0Hvonx+IkOKXwpHFY0Mo4d32Bi+MxRuEnd3tO44AaMvlkl13QMTF2',
    'kHFSC70dAkEA669LZavGjW67+rO+f+xyDVby9pD5GJQBb78xRCf93Zcu2KW4NSp3',
    'XC4p4eWfLgff1VuXL7g0VdFm4wUUHqYUqQJAZLmqpjdyBeO3tZIw6vu5meTgMvEE',
    'ygdos+vr0sa3NlUyMKWYNwznqgstQYpkYHf+WkPBS2qIE6iv+qUDLSCCOQJAESSk',
    'CFYxUBJQ7BBs9+Mb/Kppa9Ppuobxf85ZaAq8pYScrLeJKZzYJ8VX2I2aQX/jISLT',
    'YW41qFRd9n9lEkGkWQJAcxPmNI+2r5zJG+K148LLmWCIDTVZ4nxOcxffHka/3tCJ',
    'lDGUw4p2wU6pVRDpNfKrF5Nc9ZKO8NAtC17ZvDyVkQ==',
    '-----END RSA PRIVATE KEY-----',
])

INTRODUCTION_POINT_PART = u'\n'.join([
    '-----BEGIN MESSAGE-----',
    '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',
    '-----END MESSAGE-----',
])

UNSIGNED_DESCRIPTOR = u'\n'.join([
    'rendezvous-service-descriptor 6wgohrr64y2od75psnrfdkbc74ddqx2v',
    'version 2',
    'permanent-key',
    '-----BEGIN RSA PUBLIC KEY-----',
    'MIGJAoGBANfM/oca2M9LLu4X06VjtmZ59NUpwUuyrSZITNCtbnBKI25hz52hJXY5',
    'bE+D7V9V7X0RLjcBSSr9tL+CMAws66c/q70Vs8OiPKHVWz/pNWp+1Lew+SVDQi2u',
    'tnADCG0cLRZoTKvBgk05IIGrfCm6l1CGlHJYkWozCb36IEIbVBwlAgMBAAE=',
    '-----END RSA PUBLIC KEY-----',
    'secret-id-part udmoj3e2ykfp73kpvauoq4t4p7kkwsjq',
    'publication-time 2015-06-25 11:00:00',
    'protocol-versions 2,3',
    'introduction-points',
    '-----BEGIN MESSAGE-----',
    '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',
    '-----END MESSAGE-----',
    'signature',
    '-----BEGIN SIGNATURE-----',
    'VX4GC6s6zmY84mKsh+YdAqyZqDevJwGYr9yJntBNms4XRQHlgiW/JCspJzCqvrQG',
    'N4Fh8XNTodQFnxz/kz8K3SBFlLnJHzKxSBTSZTLd8hRp84F/XxDcPaIPda8UJZuF',
    'pOT8V0hfhgo8WxLpOyUzxrYugPB2GRkWYLhHaKhxkJY=',
    '-----END SIGNATURE-----',
])

SIGNED_DESCRIPTOR = u'\n'.join([
    'rendezvous-service-descriptor 6wgohrr64y2od75psnrfdkbc74ddqx2v',
    'version 2',
    'permanent-key',
    '-----BEGIN RSA PUBLIC KEY-----',
    'MIGJAoGBANfM/oca2M9LLu4X06VjtmZ59NUpwUuyrSZITNCtbnBKI25hz52hJXY5',
    'bE+D7V9V7X0RLjcBSSr9tL+CMAws66c/q70Vs8OiPKHVWz/pNWp+1Lew+SVDQi2u',
    'tnADCG0cLRZoTKvBgk05IIGrfCm6l1CGlHJYkWozCb36IEIbVBwlAgMBAAE=',
    '-----END RSA PUBLIC KEY-----',
    'secret-id-part udmoj3e2ykfp73kpvauoq4t4p7kkwsjq',
    'publication-time 2015-06-25 11:00:00',
    'protocol-versions 2,3',
    'introduction-points',
    '-----BEGIN MESSAGE-----',
    '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',
    '-----END MESSAGE-----',
    'signature',
    '-----BEGIN SIGNATURE-----',
    'VX4GC6s6zmY84mKsh+YdAqyZqDevJwGYr9yJntBNms4XRQHlgiW/JCspJzCqvrQG',
    'N4Fh8XNTodQFnxz/kz8K3SBFlLnJHzKxSBTSZTLd8hRp84F/XxDcPaIPda8UJZuF',
    'pOT8V0hfhgo8WxLpOyUzxrYugPB2GRkWYLhHaKhxkJY=',
    '-----END SIGNATURE-----',
])

PRIVATE_KEY = Crypto.PublicKey.RSA.importKey(PEM_PRIVATE_KEY)
UNIX_TIMESTAMP = 1435233021


@pytest.mark.parametrize('intro_point_distribution, selected_ip_count', [
    ([3], 3),
    ([3, 3], 6),
    ([0], 0),
    ([10, 10], 10),
    ([3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3], 10),
    ([10, 10, 10, 10, 10, 10], 10),
    pytest.param([0, 3, 3], 10, marks=pytest.mark.xfail()),
    pytest.param([6, 3, 3], 12, marks=pytest.mark.xfail()),
])
def test_introduction_point_selection(intro_point_distribution,
                                      selected_ip_count):
    """
    Basic test case to check that the correct number of IPs are selected.
    """
    # Create Mock list of instances (index by letter) and their respective
    # introduction points.
    available_intro_points = [[index] * count for index, count
                              in zip(string.ascii_lowercase,
                                     intro_point_distribution)]

    intro_set = descriptor.IntroductionPointSet(available_intro_points)

    # Check that we can fetch the same number for each descriptor
    for i in range(0, 2):
        # Max 10 introduction points per descriptor
        choosen_intro_points = intro_set.choose(10)
        assert len(choosen_intro_points) == selected_ip_count


def test_generate_service_descriptor(monkeypatch, mocker):
    """
    Test creation of a fully signed hidden service descriptor
    """
    # Mock the datetime function to return a constant timestamp
    class frozen_datetime(datetime.datetime):
        @classmethod
        def utcnow(cls):
            return datetime.datetime.utcfromtimestamp(UNIX_TIMESTAMP)
    monkeypatch.setattr(datetime, 'datetime', frozen_datetime)

    # Patch make_introduction_points_part to return the test introduction
    # point section
    mocker.patch('onionbalance.descriptor.make_introduction_points_part',
                 lambda *_: INTRODUCTION_POINT_PART)

    # Test basic descriptor generation.
    signed_descriptor = descriptor.generate_service_descriptor(
        PRIVATE_KEY,
        introduction_point_list=['mocked-ip-list'],
    ).encode('utf-8')
    stem.descriptor.hidden_service_descriptor.\
        HiddenServiceDescriptor(signed_descriptor, validate=True)
    assert (hashlib.sha1(signed_descriptor).hexdigest() ==
            'df4f4a7a15492205f073c32cbcfc4eb9511e4ad8')

    # Test descriptor generation with specified timestamp
    signed_descriptor = descriptor.generate_service_descriptor(
        PRIVATE_KEY,
        introduction_point_list=['mocked-ip-list'],
        timestamp=datetime.datetime.utcfromtimestamp(UNIX_TIMESTAMP),
    ).encode('utf-8')
    stem.descriptor.hidden_service_descriptor.\
        HiddenServiceDescriptor(signed_descriptor, validate=True)
    assert (hashlib.sha1(signed_descriptor).hexdigest() ==
            'df4f4a7a15492205f073c32cbcfc4eb9511e4ad8')

    # Test descriptor for deviation and replica 1
    signed_descriptor = descriptor.generate_service_descriptor(
        PRIVATE_KEY,
        introduction_point_list=['mocked-ip-list'],
        replica=1,
        deviation=24*60*60,
    ).encode('utf-8')
    stem.descriptor.hidden_service_descriptor.\
        HiddenServiceDescriptor(signed_descriptor, validate=True)
    assert (hashlib.sha1(signed_descriptor).hexdigest() ==
            'd828140cdccb1165dbc5a4b39622fcb45e6438fb')


def test_generate_service_descriptor_no_intros():
    with pytest.raises(ValueError):
        descriptor.generate_service_descriptor(
            PRIVATE_KEY,
            introduction_point_list=[],
        )


def test_make_public_key_block():
    """
    Test generation of ASN.1 representation of public key
    """
    public_key_block = descriptor.make_public_key_block(PRIVATE_KEY)
    assert (hashlib.sha1(public_key_block.encode('utf-8')).hexdigest() ==
            '2cf75da5e1a198ca7cb3db7b0baa6708feaf26e8')


def test_sign_digest():
    """
    Test signing a SHA1 digest
    """
    test_digest = unhexlify('2a447f044d2f8d8127e8133b2d545450bc58760e')
    signature = descriptor.sign_digest(test_digest, PRIVATE_KEY)
    assert (hashlib.sha1(signature.encode('utf-8')).hexdigest() ==
            '27bee071a7e0f0af26a1c176f0c0af00854c05c1')


def test_sign_descriptor():
    """
    Test signing a descriptor
    """

    # Test signing an unsigned descriptor
    signed_descriptor = descriptor.sign_descriptor(
        UNSIGNED_DESCRIPTOR, PRIVATE_KEY).encode('utf-8')
    stem.descriptor.hidden_service_descriptor.\
        HiddenServiceDescriptor(signed_descriptor, validate=True)
    assert (hashlib.sha1(signed_descriptor).hexdigest() ==
            'df4f4a7a15492205f073c32cbcfc4eb9511e4ad8')

    # Test resigning a previously signed descriptor
    signed_descriptor = descriptor.sign_descriptor(
        SIGNED_DESCRIPTOR, PRIVATE_KEY).encode('utf-8')
    stem.descriptor.hidden_service_descriptor.\
        HiddenServiceDescriptor(signed_descriptor, validate=True)
    assert (hashlib.sha1(signed_descriptor).hexdigest() ==
            'df4f4a7a15492205f073c32cbcfc4eb9511e4ad8')


def test_descriptor_received_invalid_descriptor(mocker):
    """
    Test invalid descriptor content received from the HSDir
    """
    mocker.patch("onionbalance.descriptor.logger.exception",
                 side_effect=ValueError('InvalidDescriptorException'))

    # Check that the invalid descriptor error is logged.
    with pytest.raises(ValueError):
        descriptor.descriptor_received(u'not-a-valid-descriptor-input')
    assert descriptor.logger.exception.call_count == 1
