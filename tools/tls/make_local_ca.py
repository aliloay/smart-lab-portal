"""
HTTPS for the lab network (no internet, so no public certificate authority):

  1. a Smart Lab CA (made once, kept on this laptop - the key never leaves it);
  2. a server certificate for the laptop, signed by that CA, valid for the
     names and addresses the portal is opened with.

Then each lab PC / phone trusts the CA once (import deploy/tls/smartlab-ca.crt
as a trusted root - docs/SECURITY.md) and the portal opens on https:// with
no warning. TLS is never disabled to "make it work": an untrusted CA shows a
warning instead.

    py tools/tls/make_local_ca.py                      (localhost + 192.168.1.200 + 192.168.1.210)
    py tools/tls/make_local_ca.py --ip 192.168.1.200 --ip 192.168.1.210 --name smartlab.local

The server certificate lasts 397 days (browser limit); run again to renew
(the CA is reused). Needs: pip install cryptography.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "deploy", "tls")


def _write(path, data, private=False):
    with open(path, "wb") as f:
        f.write(data)
    if private:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _key_pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", action="append", default=[], help="LAN address the portal is opened on")
    ap.add_argument("--name", action="append", default=[], help="host name, e.g. smartlab.local")
    a = ap.parse_args()
    ips = a.ip or ["192.168.1.200", "192.168.1.210"]
    names = ["localhost"] + a.name
    os.makedirs(OUT, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    ca_key_p, ca_crt_p = os.path.join(OUT, "smartlab-ca.key"), os.path.join(OUT, "smartlab-ca.crt")

    if os.path.isfile(ca_key_p) and os.path.isfile(ca_crt_p):
        ca_key = serialization.load_pem_private_key(open(ca_key_p, "rb").read(), None)
        ca = x509.load_pem_x509_certificate(open(ca_crt_p, "rb").read())
        print("CA reused:", ca_crt_p)
    else:
        ca_key = ec.generate_private_key(ec.SECP256R1())
        subj = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "GIU Smart Lab"),
                          x509.NameAttribute(NameOID.COMMON_NAME, "Smart Lab local CA")])
        ca = (x509.CertificateBuilder().subject_name(subj).issuer_name(subj)
              .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=3650))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True,
                                           content_commitment=False, key_encipherment=False,
                                           data_encipherment=False, key_agreement=False,
                                           encipher_only=False, decipher_only=False), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
              .sign(ca_key, hashes.SHA256()))
        _write(ca_key_p, _key_pem(ca_key), private=True)
        _write(ca_crt_p, ca.public_bytes(serialization.Encoding.PEM))
        print("CA made:", ca_crt_p)

    key = ec.generate_private_key(ec.SECP256R1())
    san = [x509.DNSName(n) for n in names] + [x509.IPAddress(ipaddress.ip_address(i))
                                              for i in ["127.0.0.1"] + ips]
    crt = (x509.CertificateBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Smart Lab portal")]))
           .issuer_name(ca.subject).public_key(key.public_key()).serial_number(x509.random_serial_number())
           .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=397))
           .add_extension(x509.SubjectAlternativeName(san), critical=False)
           .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
           .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
           .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
           .sign(ca_key, hashes.SHA256()))
    _write(os.path.join(OUT, "server.key"), _key_pem(key), private=True)
    _write(os.path.join(OUT, "server.crt"), crt.public_bytes(serialization.Encoding.PEM)
           + ca.public_bytes(serialization.Encoding.PEM))
    print("server certificate for:", ", ".join(names + ["127.0.0.1"] + ips),
          "- valid until", crt.not_valid_after_utc.date())
    print("Trust", os.path.abspath(ca_crt_p), "on each device (docs/SECURITY.md), then restart the portal.")


if __name__ == "__main__":
    main()
