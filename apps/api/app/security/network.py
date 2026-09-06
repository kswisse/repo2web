"""
Machine-readable network policy for build and runtime containers.

All policies are deny-by-default. Only explicitly allowed traffic is permitted.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Protocol(Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"


class Direction(Enum):
    INGRESS = "ingress"
    EGRESS = "egress"


@dataclass(frozen=True)
class NetworkRule:
    """Single network rule — immutable."""
    direction: Direction
    protocol: Protocol
    port: Optional[int] = None
    source_cidr: Optional[str] = None
    dest_cidr: Optional[str] = None
    action: str = "allow"
    description: str = ""


@dataclass(frozen=True)
class NetworkPolicy:
    """
    Complete network policy for a container type.
    deny-by-default: all traffic blocked unless explicitly allowed.
    """
    name: str
    rules: list[NetworkRule] = field(default_factory=list)

    # --- Egress Defaults ---
    ALLOWED_EGRESS_PORTS: tuple = (80, 443)

    # --- Blocked CIDRs (RFC1918 + link-local + loopback) ---
    BLOCKED_CIDRS: tuple = (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "127.0.0.0/8",
        "fc00::/7",
        "::1/128",
    )

    # --- Blocked Hosts ---
    BLOCKED_HOSTS: tuple = (
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "metadata.google.internal",
        "169.254.169.254",
    )

    # --- DNS Policy ---
    ALLOWED_DNS: tuple = ("8.8.8.8", "1.1.1.1", "8.8.4.4")
    DNS_PORT: int = 53

    # --- Connection Limits ---
    connection_timeout: int = 30
    max_connections: int = 100
    max_outbound_bandwidth: str = "100m"

    # --- Blocked Ports (outbound) ---
    BLOCKED_PORTS: tuple = (
        22, 23, 25, 587, 465,
        3389, 4444, 5555, 6660, 6667,
    )


# --- Pre-defined policies ---

BUILD_NETWORK_POLICY = NetworkPolicy(
    name="build-isolation",
    rules=[
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=80,
            description="HTTP for package downloads",
        ),
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=443,
            description="HTTPS for package downloads",
        ),
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.UDP,
            port=53,
            description="DNS resolution",
        ),
        NetworkRule(
            direction=Direction.INGRESS,
            protocol=Protocol.TCP,
            action="deny",
            description="Default deny ingress",
        ),
    ],
)

RUNTIME_NETWORK_POLICY = NetworkPolicy(
    name="runtime-isolation",
    rules=[
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=80,
            description="HTTP for external APIs",
        ),
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.TCP,
            port=443,
            description="HTTPS for external APIs",
        ),
        NetworkRule(
            direction=Direction.EGRESS,
            protocol=Protocol.UDP,
            port=53,
            description="DNS resolution",
        ),
        NetworkRule(
            direction=Direction.INGRESS,
            protocol=Protocol.TCP,
            action="deny",
            description="Default deny ingress",
        ),
    ],
)


def generate_iptables_rules(
    policy: NetworkPolicy,
    source_cidr: str,
) -> list[list[str]]:
    """Generate iptables rules from a network policy."""
    rules = []

    # Default: drop all forwarded traffic from this source
    rules.append([
        "iptables", "-A", "FORWARD",
        "-s", source_cidr,
        "-j", "DROP",
    ])

    # Allow specific egress
    for rule in policy.rules:
        if rule.direction == Direction.EGRESS and rule.action == "allow":
            args = [
                "iptables", "-I", "FORWARD",
                "-s", source_cidr,
                "-p", rule.protocol.value,
            ]
            if rule.port:
                args.extend(["--dport", str(rule.port)])
            if rule.dest_cidr:
                args.extend(["-d", rule.dest_cidr])
            args.extend(["-j", "ACCEPT"])
            rules.append(args)

    # Block specific CIDRs (defense-in-depth)
    for cidr in policy.BLOCKED_CIDRS:
        rules.append([
            "iptables", "-A", "FORWARD",
            "-s", source_cidr,
            "-d", cidr,
            "-j", "DROP",
        ])

    # Block specific ports
    for port in policy.BLOCKED_PORTS:
        rules.append([
            "iptables", "-A", "FORWARD",
            "-s", source_cidr,
            "-p", "tcp",
            "--dport", str(port),
            "-j", "DROP",
        ])

    return rules
