"""
SSRF protection — validates URLs and resolves IPs against blocked ranges.

All private IPs, loopback, link-local, and cloud metadata endpoints are blocked.

Security Design Note — Trusted Deployment Health Checks:
---------------------------------------------------------
The health checker is a trusted Repo2Web infrastructure component. When health-checking
a deployment container, the flow is:

    Trusted health checker
        → container_id (trusted internal identifier from deployment pipeline)
        → Docker API inspection (trusted metadata source)
        → container labels (deployment_id proves provenance)
        → exact container IP
        → HTTP health check

This is NOT general-purpose SSRF bypass. The authorization is narrowly scoped:
- The container must have a valid `deployment_id` label (proves Repo2Web created it)
- The IP is obtained from Docker API for that specific container
- Only HTTP requests to that exact container IP are allowed
- Redirects to other destinations are still blocked
- Arbitrary private IPs unrelated to the target deployment remain blocked
"""

import ipaddress
import logging
import re
import socket
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Narrowly scoped temporary SSRF exceptions for health checking
# ---------------------------------------------------------------------------

# In-memory store: {(ip, deployment_id): expiration_timestamp}
# Each entry is a tuple: (ip: str, deployment_id: str, expires_at: float)
_health_check_allowlist: dict[tuple[str, str], float] = {}

# Default TTL for health check exceptions (seconds)
HEALTH_CHECK_EXCEPTION_TTL = 60


def allow_container_ip_for_health_check(
    ip: str,
    deployment_id: str,
    container_id: str = "",
    ttl: int = HEALTH_CHECK_EXCEPTION_TTL,
) -> None:
    """Temporarily allow a specific container IP for health checking.

    Creates a narrowly scoped SSRF exception that:
    - Is specific to the exact (ip, deployment_id) pair
    - Expires automatically after TTL seconds
    - Is audit-logged for security traceability
    - Does NOT weaken general SSRF protection

    Security rationale:
    - The IP comes from Docker API inspection (trusted metadata)
    - The deployment_id comes from container labels (proves provenance)
    - The exception is time-limited and scoped to one deployment
    - Other private IPs remain fully blocked

    Args:
        ip: Container IP address to temporarily allow
        deployment_id: Deployment ID from container labels
        container_id: Container ID for audit logging (optional)
        ttl: Time-to-live in seconds (default: 60)
    """
    expires_at = time.time() + ttl
    key = (ip, deployment_id)
    _health_check_allowlist[key] = expires_at

    logger.info(
        "ssrf.health_check_exception.created",
        extra={
            "ip": ip,
            "deployment_id": deployment_id,
            "container_id": container_id[:12] if container_id else "",
            "ttl": ttl,
            "expires_at": expires_at,
        },
    )


def is_health_check_target_allowed(
    ip: str,
    deployment_id: str,
) -> bool:
    """Check if IP is allowed as a health check target for this deployment.

    Checks the temporary allowlist for a valid (non-expired) entry matching
    both the IP and deployment_id. This ensures:
    - Only the exact deployment container is allowed
    - Expired exceptions are rejected
    - Cross-deployment targeting is prevented

    Args:
        ip: IP address to check
        deployment_id: Deployment ID to match

    Returns:
        True if the IP is allowed for health checking this deployment
    """
    key = (ip, deployment_id)
    expires_at = _health_check_allowlist.get(key)

    if expires_at is None:
        return False

    if time.time() > expires_at:
        # Entry expired — remove it
        del _health_check_allowlist[key]
        return False

    return True


def cleanup_expired_exceptions() -> int:
    """Remove expired entries from the health check allowlist.

    Returns:
        Number of entries removed
    """
    now = time.time()
    expired = [k for k, v in _health_check_allowlist.items() if now > v]
    for k in expired:
        del _health_check_allowlist[k]
    return len(expired)


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


def validate_url_ssrf(url: str, allow_http: bool = False) -> tuple[bool, str | None]:
    """
    Validate URL and resolved IP against SSRF policy.
    Returns (is_safe, reason_if_blocked).

    Args:
        url: URL to validate
        allow_http: If True, allow http:// scheme in addition to https://.
                    Used for health check redirect validation where containers
                    may redirect to HTTP endpoints on localhost.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    # Check scheme
    allowed_schemes = ("https",)
    if allow_http:
        allowed_schemes = ("https", "http")
    if parsed.scheme not in allowed_schemes:
        return False, f"Scheme {parsed.scheme} not allowed (only {', '.join(allowed_schemes)})"

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


def is_trusted_deployment_endpoint(
    ip_str: str,
    container_labels: dict[str, str] | None = None,
) -> bool:
    """Check if an IP is a trusted deployment endpoint for health checking.

    A trusted deployment endpoint is a container that:
    1. Was created by Repo2Web (has a valid deployment_id label)
    2. Has an IP address assigned by Docker networking

    This function does NOT blanket-whitelist private CIDRs. It only allows
    health checks to containers that Repo2Web itself created, identified by
    their deployment_id label.

    Security rationale:
    - The container_id is a trusted internal identifier (not user-controlled)
    - The IP is obtained from Docker API for that specific container
    - The deployment_id label proves the container was created by Repo2Web
    - This narrowly scopes authorization to the exact deployment container
    - Arbitrary private IPs unrelated to the deployment remain blocked

    Args:
        ip_str: IP address to validate
        container_labels: Docker container labels (must contain deployment_id)

    Returns:
        True if this is a trusted deployment endpoint, False otherwise
    """
    if not container_labels:
        return False

    # Must have a valid deployment_id label (proves Repo2Web created it)
    deployment_id = container_labels.get("deployment_id")
    if not deployment_id:
        return False

    # Validate deployment_id format (alphanumeric + hyphens, reasonable length)
    import re
    if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', deployment_id):
        return False

    # Must also have a type label (build or runtime)
    container_type = container_labels.get("type")
    if container_type not in ("build", "runtime"):
        return False

    # The IP must be a valid IP address
    try:
        ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    # Still block obviously dangerous targets even for trusted containers
    # (defense-in-depth: shouldn't happen but guard against misconfiguration)
    blocked_check = ipaddress.ip_address(ip_str)
    for blocked_range in [
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("169.254.0.0/16"),
    ]:
        if blocked_check in blocked_range:
            return False

    return True
