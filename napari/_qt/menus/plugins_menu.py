from typing import TYPE_CHECKING, DefaultDict, Iterator, List, Sequence, Tuple

from qtpy.QtWidgets import QAction

from ...utils.translations import trans
from ..dialogs.qt_plugin_dialog import QtPluginDialog
from ..dialogs.qt_plugin_report import QtPluginErrReporter
from ._util import NapariMenu

if TYPE_CHECKING:
    from ..qt_main_window import Window


class PluginsMenu(NapariMenu):
    def __init__(self, window: 'Window'):
        self._win = window
        super().__init__(trans._('&Plugins'), window._qt_window)

        from ...plugins import plugin_manager

        plugin_manager.discover_widgets()
        plugin_manager.events.disabled.connect(
            self._remove_unregistered_widget
        )
        plugin_manager.events.registered.connect(self._add_registered_widget)
        plugin_manager.events.unregistered.connect(
            self._remove_unregistered_widget
        )
        self._build()

    def _build(self, event=None):
        self.clear()
        action = self.addAction(trans._("Install/Uninstall Plugins..."))
        action.triggered.connect(self._show_plugin_install_dialog)
        action = self.addAction(trans._("Plugin Errors..."))
        action.setStatusTip(
            trans._(
                'Review stack traces for plugin exceptions and notify developers'
            )
        )
        action.triggered.connect(self._show_plugin_err_reporter)
        self.addSeparator()

        # Add a menu item (QAction) for each available plugin widget
        self._add_registered_widget(call_all=True)

    def _remove_unregistered_widget(self, event):

        for idx, action in enumerate(self.actions()):
            if event.value in action.text():
                self.removeAction(action)
                self._win._remove_dock_widget(event=event)

    def _add_registered_widget(self, event=None, call_all=False):
        from itertools import chain

        from ...plugins import plugin_manager

        # eg ('dock', ('my_plugin', {'My widget': MyWidget}))
        _iterable: Iterator[Tuple[str, Tuple[str, Sequence[str]]]]
        try:
            import npe2
        except ImportError:
            _iterable = iter([])
        else:
            pm = npe2.PluginManager.instance()
            wdgs: DefaultDict[str, List[str]] = DefaultDict(list)
            for wdg_contrib in pm.iter_widgets():
                wdgs[wdg_contrib.plugin_name].append(wdg_contrib.name)
            _iterable = (('dock', x) for x in wdgs.items())

        for hook_type, (plugin_name, widgets) in chain(
            _iterable, plugin_manager.iter_widgets()
        ):
            if call_all or event.value == plugin_name:
                self._add_plugin_actions(hook_type, plugin_name, widgets)

    def _add_plugin_actions(
        self, hook_type: str, plugin_name: str, widgets: Sequence[str]
    ):
        from ...plugins import menu_item_template

        multiprovider = len(widgets) > 1
        if multiprovider:
            menu = NapariMenu(plugin_name, self)
            self.addMenu(menu)
        else:
            menu = self

        for wdg_name in widgets:
            key = (plugin_name, wdg_name)
            if multiprovider:
                action = QAction(wdg_name, parent=self)
            else:
                full_name = menu_item_template.format(*key)
                action = QAction(full_name, parent=self)

            def _add_toggle_widget(*, key=key, hook_type=hook_type):
                full_name = menu_item_template.format(*key)
                if full_name in self._win._dock_widgets.keys():
                    dock_widget = self._win._dock_widgets[full_name]
                    if dock_widget.isVisible():
                        dock_widget.hide()
                    else:
                        dock_widget.show()
                    return

                if hook_type == 'dock':
                    dock_widget, _w = self._win.add_plugin_dock_widget(*key)
                else:
                    dock_widget = self._win._add_plugin_function_widget(*key)

                # Fixes https://github.com/napari/napari/issues/3624
                dock_widget.setFloating(True)
                dock_widget.setFloating(False)

            action.setCheckable(True)
            # check that this wasn't added to the menu already
            actions = [a.text() for a in menu.actions()]
            if action.text() not in actions:
                menu.addAction(action)
            action.triggered.connect(_add_toggle_widget)

    def _show_plugin_install_dialog(self):
        """Show dialog that allows users to sort the call order of plugins."""
        QtPluginDialog(self._win._qt_window).exec_()

    def _show_plugin_err_reporter(self):
        """Show dialog that allows users to review and report plugin errors."""
        QtPluginErrReporter(parent=self._win._qt_window).exec_()
