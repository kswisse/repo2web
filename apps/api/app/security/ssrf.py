"""
SSRF protection — validates URLs and resolves IPs against blocked ranges.

All private IPs, loopback, link-local, and cloud metadata endpoints are blocked.
"""

import ipaddress
import socket
from urllib.parse import urlparse


BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

BLOCKED_HOSTS = frozenset([
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
])

ALLOWED_HOSTS = frozenset([
    "github.com",
    "raw.githubusercontent.com",
    "gist.github.com",
])

MAX_REDIRECTS = 3


def is_ip_blocked(ip_str: str) -> bool:
    """Check if an IP address is in a blocked range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        for blocked_range in BLOCKED_IP_RANGES:
            if ip in blocked_range:
                return True
        return False
    except ValueError:
        return True


def resolve_hostname(hostname: str) -> list[str]:
    """Resolve hostname to IP addresses."""
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ips = []
        for family, _, _, _, sockaddr in results:
            ips.append(sockaddr[0])
        return list(set(ips))
    except socket.gaierror:
        return []


def validate_url_ssrf(url: str) -> tuple[bool, str | None]:
    """
    Validate URL and resolved IP against SSRF policy.
    Returns (is_safe, reason_if_blocked).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    if parsed.scheme not in ("https",):
        return False, f"Scheme {parsed.scheme} not allowed (only https)"

    hostname = parsed.hostname
    if not hostname:
        return False, "No hostname in URL"

    # Check blocked hosts
    if hostname in BLOCKED_HOSTS:
        return False, f"Host {hostname} is blocked"

    # Check if hostname is an IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if is_ip_blocked(str(ip)):
            return False, f"IP {hostname} is in blocked range"
    except ValueError:
        pass

    # Check allowed hosts (for GitHub URLs)
    if hostname not in ALLOWED_HOSTS:
        # Check if it's a subdomain of allowed hosts
        is_allowed_subdomain = any(
            hostname.endswith(f".{allowed}") or hostname == allowed
            for allowed in ALLOWED_HOSTS
        )
        if not is_allowed_subdomain:
            return False, f"Host {hostname} not in allowed list"

    # Resolve hostname and check IPs
    resolved_ips = resolve_hostname(hostname)
    if not resolved_ips:
        return False, f"Could not resolve hostname {hostname}"

    for ip in resolved_ips:
        if is_ip_blocked(ip):
            return False, f"Hostname {hostname} resolves to blocked IP {ip}"

    return True, None


async def validate_url_ssrf_async(url: str) -> tuple[bool, str | None]:
    """Async version of validate_url_ssrf for use in async contexts."""
    return validate_url_ssrf(url)
