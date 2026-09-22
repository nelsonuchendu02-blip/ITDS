# Asset and network inventory security

The Phase 1K inventory foundation is organization-scoped and does not execute
commands, scripts, PowerShell, subprocesses, or network polling.

## Authorization

- `assets:read`, `assets:create`, and `assets:manage` protect asset routes.
- `networks:read`, `networks:create`, and `networks:manage` protect site,
  network, subnet, VLAN, and SSID routes.
- Organization identity, audit identity, and ownership fields are server
  controlled.
- Cross-organization resources return not-found behavior rather than leaking
  their existence.

## Data integrity

Every inventory entity belongs to exactly one organization. Composite foreign
keys enforce that device-to-site, device-to-network, device-to-subnet,
device-to-VLAN, device-to-SSID, device-to-user, and network hierarchy
relationships cannot cross organization boundaries.

Request schemas reject unexpected fields and validate asset types, IP
addresses, MAC addresses, CIDRs, VLAN ranges, and parent ownership.

Inventory creates, updates, and deletes are recorded in the audit log with
minimal resource metadata and no credentials or command payloads.
