from typing import TYPE_CHECKING, Callable, List, Union

from qtpy.QtWidgets import QAction, QMenu

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    from ...utils.events import EventEmitter

    try:
        from qtpy.QtCore import SignalInstance
    except ImportError:
        from qtpy.QtCore import pyqtBoundSignal as SignalInstance

    class ActionDict(TypedDict):
        text: str
        # these are optional
        slot: Callable
        shortcut: str
        statusTip: str
        menuRole: QAction.MenuRole
        checkable: bool
        checked: bool
        check_on: Union[EventEmitter, SignalInstance]

    class MenuDict(TypedDict):
        menu: str
        # these are optional
        items: List[ActionDict]

    # note: TypedDict still doesn't have the concept of "optional keys"
    # so we add in generic `dict` for type checking.
    # see PEP655: https://www.python.org/dev/peps/pep-0655/
    MenuItem = Union[MenuDict, ActionDict, dict]


def populate_menu(menu: QMenu, actions: List['MenuItem']):
    """Populate a QMenu from a declarative list of QAction dicts.

    Parameters
    ----------
    menu : QMenu
        the menu to populate
    actions : list of dict
        A list of dicts with one or more of the following keys

        **Required: One of "text" or "menu" MUST be present in the dict**
        text: str
            the name of the QAction to add
        menu: str
            if present, creates a submenu instead.  "menu" keys may also
            provide an "items" key to populate the menu.

        **Optional:**
        slot: callable
            a callback to call when the action is triggered
        shortcut: str
            a keyboard shortcut to trigger the actoin
        statusTip: str
            used for setStatusTip
        menuRole: QAction.MenuRole
            used for setMenuRole
        checkable: bool
            used for setCheckable
        checked: bool
            used for setChecked (only if `checkable` is provided and True)
        check_on: EventEmitter
            If provided, and `checkable` is True, this EventEmitter will be
            connected to action.setChecked:

            `dct['check_on'].connect(lambda e: action.setChecked(e.value))`
    """
    for ax in actions:
        if not ax:
            menu.addSeparator()
            continue
        if not ax.get("when", True):
            continue
        if 'menu' in ax:
            sub = ax['menu']
            if isinstance(sub, QMenu):
                menu.addMenu(sub)
                sub.setParent(menu)
            else:
                sub = menu.addMenu(sub)
            populate_menu(sub, ax.get("items", []))
            continue
        action: QAction = menu.addAction(ax['text'])
        if 'slot' in ax:
            action.triggered.connect(ax['slot'])
        action.setShortcut(ax.get('shortcut', ''))
        action.setStatusTip(ax.get('statusTip', ''))
        if 'menuRole' in ax:
            action.setMenuRole(ax['menuRole'])
        if ax.get("checkable"):
            action.setCheckable(True)
            action.setChecked(ax.get("checked", False))
            if 'check_on' in ax:
                emitter = ax['check_on']

                @emitter.connect
                def _setchecked(e, action=action):
                    action.setChecked(e.value if hasattr(e, 'value') else e)

        action.setData(ax)


def populate_qmenu_from_manifest(menu: QMenu, menu_key: str):
    """Populate `menu` from a `menu_key` offering in the manifest."""
    # TODO: declare somewhere what menu_keys are valid.
    try:
        from npe2 import PluginManager
    except ImportError:
        return

    pm = PluginManager.instance()
    for item in pm.iter_menu(menu_key):
        if hasattr(item, 'submenu'):
            subm_contrib = pm.get_submenu(item.submenu)
            subm = menu.addMenu(subm_contrib.label)
            populate_qmenu_from_manifest(subm, subm_contrib.id)
        else:
            cmd = pm.get_command(item.command)
            action = menu.addAction(cmd.title)
            action.triggered.connect(lambda *args: cmd.exec(args=args))


class NapariMenu(QMenu):
    """
    Base napari menu class that provides action handling and clean up on
    close.
    """

    _INSTANCES: List['NapariMenu'] = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._INSTANCES.append(self)

    def _destroy(self):
        """Clean up action data to avoid widget leaks."""
        for ax in self.actions():
            ax.setData(None)

            try:
                ax._destroy()
            except AttributeError:
                pass

        if self in self._INSTANCES:
            self._INSTANCES.remove(self)

    def update(self, event=None):
        """Update action enabled/disabled state based on action data."""
        for ax in self.actions():
            data = ax.data()
            if data:
                enabled_func = data.get('enabled', lambda event: True)
                ax.setEnabled(bool(enabled_func(event)))
