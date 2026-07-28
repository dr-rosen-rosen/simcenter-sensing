# CV hardware

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

## ZedBox

Stereolabs ZedBox — embedded compute appliance with attached ZED stereo camera(s).
Runs Ubuntu + the ZED SDK; supports multi-camera fusion for body tracking.

- Vendor docs: <https://www.stereolabs.com/docs/>
- Multi-camera body tracking example: <https://github.com/stereolabs/zed-sdk/blob/master/body%20tracking/multi-camera/python/fused_cameras.py>
- Multi-camera recording example: <https://github.com/stereolabs/zed-sdk/tree/master/recording/recording/multi%20camera/python>

<!-- TODO(unassigned): Fill exact ZedBox model, ZED camera modules attached, ZED SDK version pinned to, JetPack / Ubuntu version. -->

| Field                | Value |
|----------------------|-------|
| ZedBox model         | TODO  |
| Attached cameras     | 2× ZED (model TODO): `zed-7796` (cam1, right), `zed-9816` (cam2, left) |
| ZED SDK version      | TODO  |
| OS / JetPack         | TODO  |
| Bundled body model   | TODO (e.g., HUMAN_BODY_MEDIUM, BODY_34) |

## Default credentials and network posture

The ZedBox ships with factory-default OS credentials (per Stereolabs docs).

> [!WARNING]
> **Change the factory password before deploying** to any network beyond the
> data-collection room. The default credentials are public knowledge. Restrict
> the ZedBox to an isolated lab network and do not expose it to the internet.

<!-- TODO(unassigned): Document the credential-rotation procedure and the network segment the ZedBox should sit on. -->

## Mounting and coverage

<!-- TODO(unassigned): Add a room diagram in assets/ showing camera placements and the coverage zones each camera contributes to multi-camera fusion. Note minimum overlap required between camera fields-of-view for fusion to work. -->

## Lighting requirements

<!-- TODO(unassigned): Document lighting constraints discovered during pilot sessions. ZED depth quality depends on scene texture and lighting; capture acceptable ranges. -->

## Maintenance

- Lens cleaning: <!-- TODO -->
- Calibration cadence: <!-- TODO — see pre-session.md for ZED360 procedure -->
- Firmware / SDK updates: <!-- TODO — pin versions, document upgrade procedure -->
