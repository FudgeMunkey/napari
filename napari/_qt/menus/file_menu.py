from typing import TYPE_CHECKING

from qtpy.QtCore import QSize
from qtpy.QtWidgets import QAction

from ...settings import get_settings
from ...utils.history import get_save_history, update_save_history
from ...utils.misc import running_as_bundled_app
from ...utils.translations import trans
from ..dialogs.preferences_dialog import PreferencesDialog
from ..dialogs.screenshot_dialog import ScreenshotDialog
from ._util import NapariMenu, populate_menu

if TYPE_CHECKING:
    from ..qt_main_window import Window


class FileMenu(NapariMenu):
    def __init__(self, window: 'Window'):
        self._win = window
        super().__init__(trans._('&File'), window._qt_window)
        self.open_sample_menu = NapariMenu('Open Sample', self)
        ACTIONS = [
            {
                'text': trans._('Open File(s)...'),
                'slot': window.qt_viewer._open_files_dialog,
                'shortcut': 'Ctrl+O',
            },
            {
                'text': trans._('Open Files as Stack...'),
                'slot': window.qt_viewer._open_files_dialog_as_stack_dialog,
                'shortcut': 'Ctrl+Alt+O',
            },
            {
                'text': trans._('Open Folder...'),
                'slot': window.qt_viewer._open_folder_dialog,
                'shortcut': 'Ctrl+Shift+O',
            },
            {'menu': self.open_sample_menu},
            {},
            {
                'text': trans._('Preferences'),
                'slot': self._open_preferences,
                'shortcut': 'Ctrl+Shift+P',
                'statusTip': trans._('Open preferences dialog'),
                'menuRole': QAction.PreferencesRole,
            },
            {},
            {
                'text': trans._('Save Selected Layer(s)...'),
                'slot': lambda: window.qt_viewer._save_layers_dialog(
                    selected=True
                ),
                'shortcut': 'Ctrl+S',
                'enabled': self._layer_count,
            },
            {
                'text': trans._('Save All Layers...'),
                'slot': lambda: window.qt_viewer._save_layers_dialog(
                    selected=False
                ),
                'shortcut': 'Ctrl+Shift+S',
                'enabled': self._layer_count,
            },
            {
                'text': trans._('Save Screenshot...'),
                'slot': window.qt_viewer._screenshot_dialog,
                'shortcut': 'Alt+S',
                'statusTip': 'Save screenshot of current display, default .png',
            },
            {
                'text': trans._('Save Screenshot with Viewer...'),
                'slot': self._screenshot_dialog,
                'shortcut': 'Alt+Shift+S',
                'statusTip': 'Save screenshot of current display with the viewer, default .png',
            },
            {
                'text': trans._('Copy Screenshot to Clipboard'),
                'slot': window.qt_viewer.clipboard,
                'shortcut': 'Alt+Shift+S',
                'statusTip': 'Copy screenshot of current display to the clipboard',
            },
            {
                'text': trans._('Copy Screenshot with Viewer to Clipboard'),
                'slot': window.clipboard,
                'shortcut': 'Alt+Shift+S',
                'statusTip': trans._(
                    'Copy screenshot of current display with the viewer to the clipboard'
                ),
            },
            {},
            {
                'text': trans._('Close Window'),
                'slot': window._qt_window.close_window,
                'shortcut': 'Ctrl+W',
            },
            {
                'when': running_as_bundled_app(),
                'text': trans._('Restart'),
                'slot': window._qt_window.restart,
            },
            # OS X will rename this to Quit and put it in the app menu.
            # This quits the entire QApplication and closes all windows.
            {
                'text': trans._('Exit'),
                'slot': lambda: window._qt_window.close(quit_app=True),
                'shortcut': 'Ctrl+Q',
                'menuRole': QAction.QuitRole,
            },
        ]
        populate_menu(self, ACTIONS)

        self._pref_dialog = None

        from ...plugins import plugin_manager

        plugin_manager.discover_sample_data()
        plugin_manager.events.disabled.connect(self._rebuild_samples_menu)
        plugin_manager.events.registered.connect(self._rebuild_samples_menu)
        plugin_manager.events.unregistered.connect(self._rebuild_samples_menu)
        self._rebuild_samples_menu()
        self.update()

    def _layer_count(self, event=None):
        return len(self._win.qt_viewer.viewer.layers)

    def _screenshot_dialog(self):
        """Save screenshot of current display with viewer, default .png"""
        hist = get_save_history()
        dial = ScreenshotDialog(
            self._win.screenshot, self._win.qt_viewer, hist[0], hist
        )
        if dial.exec_():
            update_save_history(dial.selectedFiles()[0])

    def _open_preferences(self):
        """Edit preferences from the menubar."""
        if self._pref_dialog is None:
            win = PreferencesDialog(parent=self._win._qt_window)
            self._pref_dialog = win

            app_pref = get_settings().application
            if app_pref.preferences_size:
                win.resize(*app_pref.preferences_size)

            @win.resized.connect
            def _save_size(sz: QSize):
                app_pref.preferences_size = (sz.width(), sz.height())

            win.finished.connect(self._clean_pref_dialog)
            win.show()
        else:
            self._pref_dialog.raise_()

    def _clean_pref_dialog(self):
        self._pref_dialog = None

    def _rebuild_samples_menu(self):
        from ...plugins import menu_item_template, plugin_manager

        self.open_sample_menu.clear()

        for plugin_name, samples in plugin_manager._sample_data.items():
            multiprovider = len(samples) > 1
            if multiprovider:
                menu = self.open_sample_menu.addMenu(plugin_name)
            else:
                menu = self.open_sample_menu

            for samp_name, samp_dict in samples.items():
                display_name = samp_dict['display_name']
                if multiprovider:
                    action = QAction(display_name, parent=self)
                else:
                    full_name = menu_item_template.format(
                        plugin_name, display_name
                    )
                    action = QAction(full_name, parent=self)

                def _add_sample(*args, plg=plugin_name, smp=samp_name):
                    self._win.qt_viewer.viewer.open_sample(plg, smp)

                menu.addAction(action)
                action.triggered.connect(_add_sample)
