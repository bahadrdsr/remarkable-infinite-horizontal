"""Generate local-only native resources. Never publish the generated directory."""

import argparse
import hashlib
import json
from pathlib import Path

PREFIX = "/qml/device/view/documentview/"
RESOURCES = {
    "DocumentView.qml": (PREFIX + "DocumentView.qml",
        "867b30a725a4ae97e3459f07a60cd72bcafb21db9a0b374f02d75c5cd8d83269"),
    "DeviceSceneView.qml": (PREFIX + "DeviceSceneView.qml",
        "78df7fe68f0be6e0795cde67bdb5ce5c5f355c9100f0c14d6e8157c688271a0c"),
    "SceneViewGestures.qml": (PREFIX + "SceneViewGestures.qml",
        "ab11773343d512d7f1e4259411c91ed2aff5c222c787cccd2e8d076b4e33563f"),
    "Display.qml": ("/qml/device/view/settings/Display.qml",
        "c71bebb7a5a927d4814ee68d4e0762f0d50bbaa4482d56a526fa32f7dea73edc"),
    "EditDocument.qml": ("/qt/qml/xofm/modules/library/ui/qml/EditDocument.qml",
        "fdca243330c3179de364ea5a7236019a5c2d702a08768ae3d59fc8384742dae6"),
    "EditDocumentWindow.qml": ("/qt/qml/xofm/modules/library/ui/qml/EditDocumentWindow.qml",
        "e248affc4b5512d3f370cb3571bc7db0bb5e8ca0edfadce2247d9ccd58f6eb69"),
}


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError("The firmware resource does not contain exactly one expected edit location.")
    return source.replace(before, after, 1)


def transform(name, source):
    if name == "DeviceSceneView.qml":
        source = "import InfiniteHorizontal 1.0\n" + source
        source = replace_once(source, "    property Document document\n",
            "    property Document document\n"
            "    readonly property int infiniteHorizontalRevision: CanvasSettings.revision\n"
            "    readonly property bool nativeInfinitePage: {\n"
            "        const revision = infiniteHorizontalRevision;\n"
            "        return !!document && document.fileType === Document.Notebook && notePage"
            " && CanvasSettings.effectiveEnabled(String(document.id));\n"
            "    }\n")
        source = replace_once(source, "            limitScrollingToPaper: true",
                              "            limitScrollingToPaper: !root.nativeInfinitePage")
        for edge in ("left", "right", "top", "bottom"):
            source = replace_once(source,
                f"property real size: root.{edge}ViewportEdge",
                f"property real size: root.nativeInfinitePage ? 0 : root.{edge}ViewportEdge")
    elif name == "SceneViewGestures.qml":
        for identifier in ("nextPageGesture", "prevPageGesture"):
            marker = f"        id: {identifier}"
            if source.count(marker) != 1:
                raise ValueError("Ambiguous page gesture.")
            start = source.index(marker)
            location = source.index("        enabled: !touchArea.gesturesBlocked", start)
            end = location + len("        enabled: !touchArea.gesturesBlocked")
            source = source[:location] + (
                "        enabled: !touchArea.gesturesBlocked && !touchArea.view.nativeInfinitePage"
            ) + source[end:]
    elif name == "DocumentView.qml":
        source = replace_once(source,
            "        snapEnabled: !adjustViewPopup.active",
            "        snapEnabled: !adjustViewPopup.active && !sceneView.nativeInfinitePage")
        source = replace_once(source,
            "            visible: newPageVisible",
            "            visible: newPageVisible && !sceneView.nativeInfinitePage")
        for function in ("moveForward", "moveBackward"):
            source = replace_once(source, f"    function {function}() {{\n",
                f"    function {function}() {{\n"
                "        if (sceneView.nativeInfinitePage) { root.newPageVisible = false; return; }\n")
    elif name == "Display.qml":
        source = "import InfiniteHorizontal 1.0\n" + source
        toggle = """
                RowLayout {
                    objectName: "infiniteHorizontalSetting"
                    Layout.fillWidth: true
                    spacing: ArkControls.Values.platform.spacing.large
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: ArkControls.Values.spacing.small
                        TextHeaderRegular {
                            Layout.fillWidth: true
                            text: qsTr("Infinite horizontal canvas")
                        }
                        TextParagraph {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: CanvasSettings.error.length > 0 ? CanvasSettings.error
                                : qsTr("Set the default for handwritten notebooks. Individual notebooks can override this in Notebook settings.")
                        }
                    }
                    ArkControls.Toggle {
                        objectName: "infiniteHorizontalToggle"
                        checked: CanvasSettings.enabled
                        focusPolicy: Qt.NoFocus
                        onClicked: CanvasSettings.enabled = !CanvasSettings.enabled
                    }
                }

"""
        source = replace_once(source, "                Repeater {\n",
                              toggle + "                Repeater {\n")
    elif name == "EditDocument.qml":
        source = "import InfiniteHorizontal 1.0\n" + source
        source = replace_once(source,
            "    property alias documentName: documentNameInput.inputText\n",
            "    property alias documentName: documentNameInput.inputText\n"
            "    property int infiniteHorizontalMode: root.entry"
            " ? CanvasSettings.overrideMode(String(root.entry.id)) : CanvasSettings.UseGlobal\n")
        control = """
        ColumnLayout {
            id: infiniteHorizontalSetting
            objectName: "infiniteHorizontalNotebookSetting"
            Layout.fillWidth: true
            visible: root.entry?.fileType === Document.Notebook
            spacing: ArkControls.Values.margin.vertical.small
            readonly property bool overrideActive: root.infiniteHorizontalMode !== CanvasSettings.UseGlobal

            ArkControls.Panel {
                objectName: "infiniteHorizontalOverrideToggle"
                Layout.fillWidth: true
                label: qsTr("Override global canvas setting")
                description: qsTr("Use a different canvas mode for this notebook.")
                action: ArkControls.Toggle {
                    checked: infiniteHorizontalSetting.overrideActive
                    focusPolicy: Qt.NoFocus
                    onClicked: {
                        root.infiniteHorizontalMode = root.infiniteHorizontalMode === CanvasSettings.UseGlobal
                            ? (CanvasSettings.enabled ? CanvasSettings.AlwaysInfinite : CanvasSettings.AlwaysPaged)
                            : CanvasSettings.UseGlobal;
                    }
                }
            }

            ArkControls.Panel {
                objectName: "infiniteHorizontalNotebookToggle"
                Layout.fillWidth: true
                enabled: infiniteHorizontalSetting.overrideActive
                opacity: enabled ? 1 : 0.5
                label: qsTr("Infinite for this notebook")
                description: qsTr("Turn off to keep normal horizontal page swipes in this notebook.")
                action: ArkControls.Toggle {
                    checked: root.infiniteHorizontalMode === CanvasSettings.AlwaysInfinite
                    enabled: infiniteHorizontalSetting.overrideActive
                    focusPolicy: Qt.NoFocus
                    onClicked: {
                        root.infiniteHorizontalMode = root.infiniteHorizontalMode === CanvasSettings.AlwaysInfinite
                            ? CanvasSettings.AlwaysPaged : CanvasSettings.AlwaysInfinite;
                    }
                }
            }
        }

"""
        source = replace_once(source, "        Column {\n            id: detailsColumn\n",
                              control + "        Column {\n            id: detailsColumn\n")
    elif name == "EditDocumentWindow.qml":
        source = "import InfiniteHorizontal 1.0\n" + source
        source = replace_once(source,
            "        onAccept: {\n            root.windowNavigator.close();\n",
            "        onAccept: {\n")
        source = replace_once(source,
            "            LibraryController.setCoverPageNumber(root._entry.id, settings.coverPageNumber);\n",
            "            LibraryController.setCoverPageNumber(root._entry.id, settings.coverPageNumber);\n"
            "            CanvasSettings.setOverrideMode(String(root._entry.id), settings.infiniteHorizontalMode);\n"
            "            root.windowNavigator.close();\n")
    else:
        raise ValueError("Unexpected native resource.")
    return source


def build(inspection, output):
    index = json.loads((inspection / "index.json").read_text())
    contents = {}
    for name, (path, expected) in RESOURCES.items():
        entries = [entry for entry in index if entry["path"] == path]
        if len(entries) != 1:
            raise ValueError(f"Missing or ambiguous inspected resource: {name}")
        filename = entries[0]["file"]
        if Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise ValueError("Unsafe resource filename.")
        data = (inspection / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Unreviewed firmware resource: {name}")
        contents[name] = transform(name, data.decode("utf-8")).encode("utf-8")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in contents.items():
        (output / name).write_bytes(data)
    mapping = "".join(f"R {RESOURCES[name][0]} {name}\n" for name in contents)
    (output / "infinite-horizontal.qrr").write_bytes(mapping.encode())
    (output / "manifest.json").write_text(json.dumps({
        "version": 1,
        "software": "3.28.0.172",
        "scope": "all-notebooks-with-settings-toggle",
        "resources": {RESOURCES[name][0]: hashlib.sha256(data).hexdigest()
                      for name, data in contents.items()},
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
    }, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inspection", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(build(args.inspection, args.output))
