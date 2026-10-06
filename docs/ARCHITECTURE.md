# Architecture

## Native editor patch

The project modifies six QML resources at runtime:

| Resource | Change |
| --- | --- |
| `DeviceSceneView.qml` | Disable horizontal paper limits for enabled handwritten notebooks and hide out-of-page overlays |
| `SceneViewGestures.qml` | Disable next/previous-page swipes while infinite mode is active |
| `DocumentView.qml` | Prevent new-page/page-navigation callbacks and viewport snapping in infinite mode |
| `Display.qml` | Add the global stock-style switch |
| `EditDocument.qml` | Add native per-notebook override controls |
| `EditDocumentWindow.qml` | Save the per-notebook override through the stock Save flow |

The generator verifies exact source hashes before applying narrow edits. Full stock resources are never committed.

## Settings

`CanvasSettings` is registered as a QML singleton inside the stock process. It stores:

```json
{
  "version": 1,
  "enabled": true,
  "overrides": {
    "notebook-uuid": "paged"
  }
}
```

Writes are atomic. Invalid or unsupported settings fail closed.

## Runtime integration

The active `xochitl.service` is a runtime copy of the vendor service. It preserves the original service dependencies so `rm-sync.service` continues to follow Xochitl normally.

The runtime copy adds:

- Xovi and Qt Resource Rebuilder preload paths;
- the settings and resource-inspection libraries;
- project recovery as the failure handler;
- no automatic restart loop.

Vendor service files are not edited.

## Guarded transitions

On Paper Pure software `3.28.0.172`, stopping stock Xochitl can exit with SIGSEGV. The manager:

1. waits for bounded quiet thread activity;
2. shadows the vendor service without its emergency failure handlers;
3. stops the stock process;
4. verifies no process remains;
5. restores normal failure handling before launching the modified editor;
6. arms an independent recovery timer;
7. verifies resource hashes, loaded modules, sync, and the selected release.

Failures restore the original service and create a disabled marker.

## Boot activation

One persistent systemd unit runs after encrypted home storage and stock Xochitl are available. It is:

- exact-firmware gated;
- one-shot and bounded;
- not configured to restart;
- disabled automatically after a failed startup;
- removable without changing notebook files.

The installer briefly remounts the root writable and recursively unmounts the volatile `/etc` overlay to place the unit in persistent `/etc`. It restores the overlay and read-only root before success.
