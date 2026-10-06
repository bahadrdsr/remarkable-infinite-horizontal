from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_native_patch import transform


class NativePatchTests(unittest.TestCase):
    def test_all_notebooks_are_controlled_by_one_setting(self):
        source = (
            "    property Document document\n"
            "            limitScrollingToPaper: true\n"
            "property real size: root.leftViewportEdge\n"
            "property real size: root.rightViewportEdge\n"
            "property real size: root.topViewportEdge\n"
            "property real size: root.bottomViewportEdge\n"
            "ScenePenInputHandler { onStrokeCompleted: controller.addDrawingLine(stroke) }\n")
        result = transform("DeviceSceneView.qml", source)
        self.assertIn("document.fileType === Document.Notebook", result)
        self.assertIn("CanvasSettings.effectiveEnabled(String(document.id))", result)
        self.assertIn("CanvasSettings.revision", result)
        self.assertIn("String(document.id)", result)
        self.assertNotIn("00000000-1111-2222-3333-444444444444", result)
        self.assertIn("limitScrollingToPaper: !root.nativeInfinitePage", result)
        self.assertIn("ScenePenInputHandler { onStrokeCompleted: controller.addDrawingLine(stroke) }", result)
        self.assertNotIn("100000", result)

    def test_gestures_are_conditional_and_undo_is_untouched(self):
        source = (
            "        id: nextPageGesture\n        enabled: !touchArea.gesturesBlocked\n"
            "        id: prevPageGesture\n        enabled: !touchArea.gesturesBlocked\n"
            "TouchAreaClickFilter { fingers: 2; onClick: controller.undo() }\n")
        result = transform("SceneViewGestures.qml", source)
        self.assertEqual(result.count("&& !touchArea.view.nativeInfinitePage"), 2)
        self.assertIn("fingers: 2; onClick: controller.undo()", result)

    def test_navigation_callback_guards_restore_when_setting_off(self):
        source = (
            "        snapEnabled: !adjustViewPopup.active\n"
            "            visible: newPageVisible\n"
            "    function moveForward() {\n}\n"
            "    function moveBackward() {\n}\n")
        result = transform("DocumentView.qml", source)
        self.assertEqual(result.count("if (sceneView.nativeInfinitePage)"), 2)
        self.assertIn("visible: newPageVisible && !sceneView.nativeInfinitePage", result)

    def test_settings_uses_native_panel_and_toggle(self):
        result = transform("Display.qml", "                Repeater {\n}\n")
        self.assertIn("ArkControls.Toggle", result)
        self.assertIn("onClicked: CanvasSettings.enabled = !CanvasSettings.enabled", result)
        self.assertIn("CanvasSettings.error", result)

    def test_notebook_override_uses_native_save_flow(self):
        edit = transform("EditDocument.qml",
            "    property alias documentName: documentNameInput.inputText\n"
            "        Column {\n            id: detailsColumn\n")
        self.assertIn("visible: root.entry?.fileType === Document.Notebook", edit)
        self.assertIn("CanvasSettings.AlwaysInfinite", edit)
        self.assertIn("CanvasSettings.AlwaysPaged", edit)
        self.assertIn("ArkControls.Toggle", edit)
        self.assertNotIn("ContextualMenu.Button", edit)
        window = transform("EditDocumentWindow.qml",
            "        onAccept: {\n            root.windowNavigator.close();\n"
            "            LibraryController.setCoverPageNumber(root._entry.id, settings.coverPageNumber);\n")
        self.assertIn("CanvasSettings.setOverrideMode", window)
        self.assertGreater(window.index("CanvasSettings.setOverrideMode"),
                           window.index("LibraryController.setCoverPageNumber"))
        self.assertGreater(window.index("root.windowNavigator.close();"),
                           window.index("CanvasSettings.setOverrideMode"))

    def test_unknown_or_ambiguous_source_is_rejected(self):
        with self.assertRaises(ValueError):
            transform("DeviceSceneView.qml", "")
        with self.assertRaises(ValueError):
            transform("Display.qml", "                Repeater {\n" * 2)
        with self.assertRaises(ValueError):
            transform("Other.qml", "")


if __name__ == "__main__":
    unittest.main()
