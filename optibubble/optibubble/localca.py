"""
Local Certificate Authority — zero-configuration HTTPS for the mobile bridge.

Mobile browsers only grant the live in-page camera (``getUserMedia``) inside a
secure context.  On ``http://192.168.x.x`` that is impossible, so OPTIBubble
runs its own tiny PKI, fully automatic:

* on first boot a **root CA** (RSA-2048, 10 years) is generated and stored in
  ``<data>/certs/``;
* a **leaf certificate** is issued per server start, covering every LAN IP of
  this machine (+ ``127.0.0.1`` / ``localhost`` / ``optibubble.local``);
* the Flask app is served twice — plain HTTP for the desktop and the cert
  download, and **HTTPS** for the phone scanner with the full live viewfinder.

Students install the root CA once (QR code A: plain-old `.crt` for
Android/desktop, an iOS configuration profile for iPhone/iPad), then scan QR
code B which opens the scanner over HTTPS with no warnings.

Requires the ``cryptography`` package.
"""

from __future__ import annotations

import datetime
import ipaddress
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CA_DAYS = 10 * 365
LEAF_DAYS = 825
CA_CN = "OPTIBubble Local CA"


def _serial() -> int:
    return int.from_bytes(uuid.uuid4().bytes[:16], "big")


def ensure_ca(cert_dir: Path) -> Tuple[Path, Path]:
    """Load or create the root CA. Returns (cert_path, key_path)."""
    cert_dir.mkdir(parents=True, exist_ok=True)
    ca_cert = cert_dir / "optibubble-ca.crt"
    ca_key = cert_dir / "optibubble-ca.key"
    if ca_cert.exists() and ca_key.exists():
        return ca_cert, ca_key
    # If only ONE half exists, refuse to silently regenerate: doing so creates
    # a brand-new root CA that every phone that already trusted the old one
    # will reject (and iOS would need a fresh profile reinstall). A corrupt or
    # missing key is a manual intervention, not something to paper over.
    if ca_cert.exists() != ca_key.exists():
        raise RuntimeError(
            f"Local CA is incomplete ({ca_cert if ca_cert.exists() else ca_key} "
            "missing its counterpart). Delete the leftover file and restart — "
            "this ensures phones don't end up trusting a CA that has since changed.")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OPTIBubble"),
        x509.NameAttribute(NameOID.COMMON_NAME, CA_CN),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(_serial())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=CA_DAYS))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0),
                           critical=True)
            .add_extension(
                x509.KeyUsage(digital_signature=True, key_encipherment=False,
                              key_cert_sign=True, crl_sign=True,
                              content_commitment=False, data_encipherment=False,
                              key_agreement=False, encipher_only=False,
                              decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    ca_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    ca_key.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    return ca_cert, ca_key


def load_ca(ca_cert: Path, ca_key: Path):
    cert = x509.load_pem_x509_certificate(ca_cert.read_bytes())
    key = serialization.load_pem_private_key(ca_key.read_bytes(), password=None)
    return cert, key


def issue_leaf(ca_cert, ca_key, ips: List[str], out_cert: Path,
               out_key: Path) -> Tuple[Path, Path]:
    """Issue a server cert valid for the given LAN IPs (+ localhost names)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sans: List[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName("optibubble.local"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    for ip in ips:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr not in [s.value for s in sans if isinstance(s, x509.IPAddress)]:
            sans.append(x509.IPAddress(addr))
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,
                                         "OPTIBubble Server")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(_serial())
            .not_valid_before(now - datetime.timedelta(hours=1))
            .not_valid_after(now + datetime.timedelta(days=LEAF_DAYS))
            .add_extension(x509.SubjectAlternativeName(sans), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID
                                                  .SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(
                key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(
                ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256()))
    out_cert.parent.mkdir(parents=True, exist_ok=True)
    out_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    out_key.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    return out_cert, out_key


def ios_mobileconfig(ca_cert_path: Path) -> bytes:
    """Wrap the CA in an iOS configuration profile for one-tap install."""
    der = x509.load_pem_x509_certificate(ca_cert_path.read_bytes()).public_bytes(
        serialization.Encoding.DER)
    import base64
    b64 = base64.b64encode(der).decode()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadContent</key><data>{b64}</data>
      <key>PayloadIdentifier</key><string>com.optibubble.ca</string>
      <key>PayloadDisplayName</key><string>{CA_CN}</string>
      <key>PayloadDescription</key><string>Trusts the teacher's OPTIBubble server on this Wi-Fi.</string>
      <key>PayloadType</key><string>com.apple.security.root</string>
      <key>PayloadUUID</key><string>{uuid.uuid4()}</string>
      <key>PayloadVersion</key><integer>1</integer>
    </dict>
  </array>
  <key>PayloadDisplayName</key><string>OPTIBubble Certificate</string>
  <key>PayloadIdentifier</key><string>com.optibubble.profile</string>
  <key>PayloadRemovalDisallowed</key><false/>
  <key>PayloadType</key><string>Configuration</string>
  <key>PayloadUUID</key><string>{uuid.uuid4()}</string>
  <key>PayloadVersion</key><integer>1</integer>
</dict>
</plist>
""".encode()
