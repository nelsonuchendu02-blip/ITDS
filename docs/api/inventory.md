# Asset and network inventory API

Phase 1K provides organization-scoped inventory endpoints:

- `/api/v1/assets`
- `/api/v1/sites`
- `/api/v1/networks`
- `/api/v1/subnets`
- `/api/v1/vlans`
- `/api/v1/ssids`

All endpoints require authentication. Read operations use the `assets:read` or
`networks:read` permission. Creation uses the corresponding `:create`
permission, while updates and deletion require `:manage`.

Assets use one central device model with a typed `asset_type`. Supported values
are `laptop`, `desktop`, `mobile_phone`, `tablet`, `server`, `access_point`,
`switch`, `firewall`, `router`, `printer`, `network_device`, `iot`, and `other`.

Organization ownership is assigned by the server. Site, network, subnet, VLAN,
SSID, and asset relationships are organization-scoped and cross-organization
references are rejected.
