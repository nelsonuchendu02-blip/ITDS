from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from typing import Protocol

MAX_DISCOVERY_TARGETS = 256


@dataclass(frozen=True)
class NormalizedTarget:
    target_type: str
    definition: str
    count: int


@dataclass(frozen=True)
class ProviderResult:
    target_ip: str
    hostname: str | None = None
    device_type: str | None = None
    operating_system: str | None = None
    metadata: dict | None = None


def normalize_target(target: str) -> NormalizedTarget:
    value = target.strip()
    if not value:
        raise ValueError("Discovery target must not be blank")
    try:
        address = ip_address(value)
    except ValueError:
        try:
            network = ip_network(value, strict=False)
        except ValueError as exc:
            raise ValueError("Discovery target must be an IPv4 address or CIDR") from exc
        if not isinstance(network, IPv4Network) or network.num_addresses > MAX_DISCOVERY_TARGETS:
            raise ValueError("Discovery target range is too large")
        return NormalizedTarget("cidr", str(network), network.num_addresses)
    if not isinstance(address, IPv4Address):
        raise ValueError("Only IPv4 discovery targets are supported")
    return NormalizedTarget("address", str(address), 1)


class DiscoveryProvider(Protocol):
    name: str

    def discover(self, target: NormalizedTarget) -> list[ProviderResult]:
        """Return structured results without accepting shell commands or credentials."""


class SimulatedDiscoveryProvider:
    name = "simulated"

    def discover(self, target: NormalizedTarget) -> list[ProviderResult]:
        if target.target_type == "cidr":
            return []
        return [
            ProviderResult(
                target_ip=target.definition,
                metadata={"simulation": True},
            )
        ]
