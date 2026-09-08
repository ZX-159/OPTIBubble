"""
Trusted-HTTPS provisioning — a built-in ACME (Let's Encrypt) client.

Why: mobile browsers gate the live camera (``getUserMedia``) behind a secure
context, and self-signed CAs need per-phone installation.  The zero-phone-setup
answer is a **publicly trusted certificate** for a name that resolves to the
teacher's *private* LAN IP:

    teacher creates a free <name>.duckdns.org subdomain  (one minute, once)
    → OPTIBubble issues a Let's Encrypt cert via the DNS-01 challenge
    → the domain points at 192.168.x.x, so phones reach the server locally
    → students scan ONE QR code and the camera just works — any browser

Only DNS queries and the (occasional) issuance traffic touch the internet;
scans, photos and results never leave the LAN.  Works without any open ports
because DNS-01 never requires the server to be reachable from outside.

Implemented from scratch on ``cryptography`` (no certbot/lego dependency):
RFC 8555 account, order, DNS-01 authorization, CSR finalize, certificate
download; DuckDNS TXT records via their plain HTTP API; propagation checked
over DNS-over-HTTPS (Cloudflare) with no extra dependencies.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

DIR_STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"
DIR_PROD = "https://acme-v02.api.letsencrypt.org/directory"

UA = "optibubble-acme/1.0"


class ACMEError(RuntimeError):
    pass


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _json_b64u(obj) -> str:
    return _b64u(json.dumps(obj, separators=(",", ":")).encode())


def _http(url: str, data: Optional[bytes] = None,
          headers: Optional[dict] = None, timeout: int = 30):
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method="POST" if data is not None else "GET")
    req.add_header("User-Agent", UA)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:400]
        raise ACMEError(f"{e.code} {url}: {body}") from e


def duckdns_txt_url(domain: str, token: str, txt: str) -> str:
    """DuckDNS update URL that sets the _acme-challenge TXT record."""
    sub = domain.removesuffix(".duckdns.org")
    return (f"https://www.duckdns.org/update?domains={sub}&token={token}"
            f"&txt={txt}")


def dns_txt_lookup(domain: str) -> list:
    """Resolve TXT records for _acme-challenge.<domain> over DoH (no deps).

    Tries Cloudflare then Google; TXT payloads arrive DNS-quoted
    (\"value\") so the quotes are stripped before comparison.
    """
    for base in ("https://cloudflare-dns.com/dns-query",
                 "https://dns.google/resolve"):
        try:
            r = _http(f"{base}?name=_acme-challenge.{domain}&type=TXT",
                      headers={"accept": "application/dns-json"})
            data = json.loads(r.read())
            vals = [a.get("data", "").strip('"').strip()
                    for a in data.get("Answer", []) if a.get("type") == 16]
            if vals:
                return vals
        except Exception:
            continue
    return []


def dns_a_lookup(domain: str) -> list:
    """Resolve the A record of <domain> over DoH (preflight check)."""
    for base in ("https://cloudflare-dns.com/dns-query",
                 "https://dns.google/resolve"):
        try:
            r = _http(f"{base}?name={domain}&type=A",
                      headers={"accept": "application/dns-json"})
            data = json.loads(r.read())
            return [a.get("data", "") for a in data.get("Answer", [])
                    if a.get("type") == 1]
        except Exception:
            continue
    return []


class ACMEClient:
    """Minimal RFC 8555 client with RS256 JWS (DuckDNS DNS-01 flow)."""

    def __init__(self, directory_url: str, email: str, account_key,
                 log=lambda msg: None):
        self.dir_url = directory_url
        self.email = email
        self.key = account_key
        self.log = log
        self._dir = None
        self._nonce = None
        self._kid = None

    # ------------------------------------------------------------- plumbing
    def _directory(self) -> dict:
        if self._dir is None:
            r = _http(self.dir_url, headers={"accept": "application/json"})
            self._nonce = r.headers.get("Replay-Nonce")
            self._dir = json.loads(r.read())
        return self._dir

    def _jwk(self) -> dict:
        pub = self.key.public_key().public_numbers()
        n = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
        e = pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")
        return {"kty": "RSA", "n": _b64u(n), "e": _b64u(e)}

    def _thumbprint(self) -> str:
        jwk = json.dumps(self._jwk(), separators=(",", ":"),
                         sort_keys=True).encode()
        return _b64u(hashlib.sha256(jwk).digest())

    def _post(self, url: str, payload) -> Tuple[dict, object]:
        if self._nonce is None:
            r = _http(self._directory()["newNonce"])
            self._nonce = r.headers.get("Replay-Nonce")
        protected = {"alg": "RS256", "nonce": self._nonce, "url": url}
        if self._kid:
            protected["kid"] = self._kid
        else:
            protected["jwk"] = self._jwk()
        # payload=None → POST-as-GET (empty payload per RFC 8555 §6.3);
        # dict → a real POST; bytes → raw (certificate download)
        if payload is None:
            body = _b64u(b"")
        elif isinstance(payload, (bytes, bytearray)):
            body = _b64u(bytes(payload))
        else:
            body = _json_b64u(payload)
        signing_input = f"{_json_b64u(protected)}.{body}".encode()
        from cryptography.hazmat.primitives.asymmetric import padding
        sig = self.key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        data = json.dumps({"protected": _json_b64u(protected), "payload": body,
                           "signature": _b64u(sig)}).encode()
        r = _http(url, data=data, headers={
            "content-type": "application/jose+json",
            "accept": "application/json"})
        self._nonce = r.headers.get("Replay-Nonce") or self._nonce
        loc = r.headers.get("Location")
        raw = r.read()
        parsed = json.loads(raw) if raw else {}
        return parsed, loc

    def _post_as_get(self, url: str) -> Tuple[dict, object]:
        return self._post(url, None)

    # ----------------------------------------------------------------- flow
    def new_account(self) -> str:
        _, kid = self._post(self._directory()["newAccount"], {
            "termsOfServiceAgreed": True,
            "contact": [f"mailto:{self.email}"]})
        if not kid:
            raise ACMEError("ACME account creation returned no Location")
        self._kid = kid
        return kid

    def dns01_challenge(self, domain: str):
        """Create an order; return (order_url, challenge_url, txt_value)."""
        order, loc = self._post(self._directory()["newOrder"], {
            "identifiers": [{"type": "dns", "value": domain}]})
        for authz_url in order.get("authorizations", []):
            authz, _ = self._post_as_get(authz_url)
            for ch in authz.get("challenges", []):
                if ch.get("type") == "dns-01":
                    key_auth = f"{ch['token']}.{self._thumbprint()}"
                    txt = _b64u(hashlib.sha256(key_auth.encode()).digest())
                    return loc, ch["url"], txt
        raise ACMEError("no dns-01 challenge in the ACME order")

    def wait_propagation(self, domain: str, txt: str, timeout: int = 240,
                         progress_every: int = 15) -> bool:
        t0 = time.time()
        next_note = progress_every
        while time.time() - t0 < timeout:
            if txt in dns_txt_lookup(domain):
                return True
            if self.log and time.time() - t0 >= next_note:
                self.log(f"waiting for DNS propagation … {int(next_note)}s")
                next_note += progress_every
            time.sleep(5)
        return False

    def answer_and_finalize(self, order_url: str, challenge_url: str, domain: str,
                            csr: x509.CertificateSigningRequest,
                            timeout: int = 150) -> str:
        """Trigger validation, finalize THE SAME order, return the cert PEM."""
        self._post(challenge_url, {})
        t0 = time.time()
        finalize_url = None
        while time.time() - t0 < timeout:
            order, _ = self._post_as_get(order_url)
            status = order.get("status")
            if status == "ready":
                finalize_url = order["finalize"]
                break
            if status == "invalid":
                raise ACMEError("ACME challenge failed (check the DuckDNS "
                                "token / domain ownership)")
            time.sleep(3)
        if not finalize_url:
            raise ACMEError("timed out waiting for the challenge")
        der = csr.public_bytes(serialization.Encoding.DER)
        self._post(finalize_url, {"csr": _b64u(der)})
        while time.time() - t0 < timeout:
            order, _ = self._post_as_get(order_url)
            if order.get("status") == "valid":
                cert_url = order.get("certificate")
                if not cert_url:
                    raise ACMEError("valid order without a certificate URL")
                # POST-as-GET (signed empty JWS payload) for the certificate
                r = self._post_raw(cert_url, None)
                return r.read().decode()
            if order.get("status") == "invalid":
                raise ACMEError("ACME finalization failed")
            time.sleep(3)
        raise ACMEError("timed out waiting for the certificate")

    def _post_raw(self, url: str, payload):
        """Signed JWS request returning the raw response object."""
        if self._nonce is None:
            r = _http(self._directory()["newNonce"])
            self._nonce = r.headers.get("Replay-Nonce")
        protected = {"alg": "RS256", "nonce": self._nonce, "url": url,
                     "kid": self._kid}
        body = _b64u(b"" if payload is None else bytes(payload))
        signing_input = f"{_json_b64u(protected)}.{body}".encode()
        from cryptography.hazmat.primitives.asymmetric import padding
        sig = self.key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
        data = json.dumps({"protected": _json_b64u(protected), "payload": body,
                           "signature": _b64u(sig)}).encode()
        return _http(url, data=data, headers={
            "content-type": "application/jose+json",
            "accept": "application/pem-certificate-chain"})


def make_csr(domain: str, key) -> x509.CertificateSigningRequest:
    return (x509.CertificateSigningRequestBuilder()
            .subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, domain)]))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(domain)]),
                           critical=False)
            .sign(key, hashes.SHA256()))


def issue_trusted_cert(domain: str, duckdns_token: str, email: str,
                       out_dir: Path, staging: bool = False,
                       progress_every: int = 15,
                       log=lambda msg: None) -> Tuple[Path, Path]:
    """Full DNS-01 issuance for <domain> via DuckDNS → (cert, key) PEM paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    acct_key_p = out_dir / "acme-account.key"
    if acct_key_p.exists():
        acct_key = serialization.load_pem_private_key(
            acct_key_p.read_bytes(), password=None)
    else:
        acct_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        acct_key_p.write_bytes(acct_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))

    client = ACMEClient(DIR_STAGING if staging else DIR_PROD, email, acct_key,
                        log=log)
    log("· contacting Let's Encrypt …")
    client.new_account()
    log("· ACME account ready")
    order_url, ch_url, txt = client.dns01_challenge(domain)
    log(f"· DNS-01 challenge received (TXT {txt[:12]}…)")
    r = _http(duckdns_txt_url(domain, duckdns_token, txt))
    if b"OK" not in (r.read() or b""):
        raise ACMEError("DuckDNS rejected the TXT update — check the token")
    log("· TXT record published, waiting for DNS propagation …")
    if not client.wait_propagation(domain, txt,
                                   progress_every=progress_every):
        raise ACMEError("TXT record did not propagate in time — try again")
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = client.answer_and_finalize(order_url, ch_url, domain,
                                     make_csr(domain, server_key))
    cert_p, key_p = out_dir / "trusted-fullchain.pem", out_dir / "trusted-key.pem"
    cert_p.write_text(pem)
    key_p.write_bytes(server_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()))
    log(f"✔ certificate issued for {domain}")
    return cert_p, key_p


def trusted_cert_valid(cert_path: Path, min_days_left: int = 30) -> bool:
    """True if the stored trusted cert exists and is still comfortably valid."""
    if not cert_path.exists():
        return False
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        ends = cert.not_valid_after_utc
        return (ends - __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc)).days > min_days_left
    except Exception:
        return False
