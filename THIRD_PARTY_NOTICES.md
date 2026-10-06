# Third-party notices

This repository contains original project source under the MIT License.

It downloads these components at install time:

| Component | Upstream | License |
| --- | --- | --- |
| Xovi `0.3.3` | `asivery/xovi` | GPL-3.0 |
| Qt Resource Rebuilder from extensions release `v19-23052026` | `asivery/rm-xovi-extensions` | GPL-3.0 |

Their release URLs and accepted SHA-256 values are pinned in `tools/infinite_horizontal.py`.

The official reMarkable SDK is downloaded separately from the manufacturer. It is not redistributed by this repository.

The patch generator reads proprietary QML resources from the owner's tablet. Generated resources are stored under `.local`, ignored by Git, and must not be redistributed.

reMarkable is a trademark of reMarkable AS. This project is independent and not endorsed by reMarkable AS.
