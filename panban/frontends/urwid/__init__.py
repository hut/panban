import subprocess
import time
import urwid

from panban.api import UserFacingException

VIM_KEYS = {
    'h': 'cursor left',
    'l': 'cursor right',
    'j': 'cursor down',
    'k': 'cursor up',
    'd': 'cursor page down',
    'u': 'cursor page up',
    'g': 'cursor max left',
    'G': 'cursor max right',
}
PALETTE = [
    (None, '', ''),
    ('heading', 'black', 'light gray'),
    ('focus button', 'black', 'white'),
    ('button', 'default', ''),
    ('button_alt', 'brown', ''),
    ('button_important', 'light red', ''),
    ('button_unimportant', 'dark gray', ''),
    ('heading_Inactive', 'black', 'dark gray'),
    ('heading_Active', 'black', 'dark red'),
    ('heading_Finished', 'black', 'dark green'),
]


class UI(object):
    def __init__(self, db):
        self.db = db
        self.loop = None

        self.menu = MenuBox(self)
        self.kanban_layout = KanbanLayout(self)
        self.base = Base(self, db, self.kanban_layout, self.menu)

        self._original_urwid_SHOW_CURSOR = urwid.escape.SHOW_CURSOR

    def activate(self):
        if self.loop is None:
            # Workaround for hiding cursor, see
            # https://github.com/urwid/urwid/issues/170
            urwid.escape.SHOW_CURSOR = ''
            self.reload()
            self.loop = urwid.MainLoop(self.base, PALETTE)
        else:
            raise Exception("Do not call UI.activate() more than once!")

    def deactivate(self):
        self.loop.screen.write(self._original_urwid_SHOW_CURSOR)
        self.loop.stop()

    def reactivate(self):
        self.base.reload()
        self.loop.start()

    def system(self, command):
        self.deactivate()
        try:
            subprocess.check_call(command)
        except KeyboardInterrupt:
            pass
        self.reactivate()

    def get_entries(self):
        return self.db.get_columns()

    def main(self):
        self.activate()
        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.deactivate()

    def reload(self):
        self.db.reload()
        self.rebuild()

    def rebuild(self):
        self.last_rebuild = time.time()
        self.tabs = []
        for node_id in self.db.root_node_ids:
            node = self.db.nodes_by_id[node_id]
            self.tabs.append(node)

        self.kanban_layout.reload()
        self.menu.reload()


class EntryButton(urwid.Button):
    button_left = urwid.Text("-")
    button_right = urwid.Text("")

    def __init__(self, ui, entry):
        self.ui = ui
        self.entry = entry
        super(EntryButton, self).__init__(entry.label)
        urwid.connect_signal(self, 'click', lambda button: self.ui.system(['vim']))  # TODO

    def keypress(self, size, key):
        if key == 'X':
            self.entry.delete()
        return super(EntryButton, self).keypress(size, key)


class Base(urwid.WidgetPlaceholder):
    def __init__(self, ui, db, content, menu):
        super(Base, self).__init__(content)
        self.content_widget = content
        self.menu_widget = menu
        self.ui = ui
        self.db = db
        self.overlay_widget = urwid.Overlay(
            urwid.LineBox(self.menu_widget),
            content, 'center', 50, 'middle', 30)

    def flip(self):
        if self.original_widget == self.content_widget:
            self.original_widget = self.overlay_widget
        else:
            self.original_widget = self.content_widget

    def reload(self):
        self.db.reload()
        self.content_widget.reload()

    def keypress(self, size, key):
        if self.db.last_modification > self.ui.last_rebuild:
            self.ui.rebuild()
        if key in ('tab', 'q'):
            self.flip()
        elif key == 'Q':
            raise SystemExit(0)
        elif key == 'R':
            self.reload()
        return super(Base, self).keypress(size, key)  # pylint: disable=not-callable


class MenuBox(urwid.ListBox):
    def __init__(self, ui):
        self.ui = ui
        self.list_walker = urwid.SimpleFocusListWalker([])
        super(MenuBox, self).__init__(self.list_walker)
        self.reload()

    def reload(self):
        focus = self.list_walker.focus
        self.list_walker[:] = []
        for entry in ['foo', 'bar', 'zar', 'yar', 'war']:
            button = urwid.Button(entry)
            urwid.connect_signal(button, 'click',
                    lambda button: self.ui.base.flip())
            self.list_walker.append(button)
        if not focus:  # Avoid starting with the bottom item focused
            self.list_walker.set_focus(0)


class KanbanLayout(urwid.Columns):
    def __init__(self, ui):
        self.columns = []
        self.ui = ui
        self.active_tab_nr = 0
        super(KanbanLayout, self).__init__(self.columns, dividechars=1)
        for key, value in VIM_KEYS.items():
            self._command_map[key] = value

    def reload(self):
        try:
            focus = self.focus_position
        except IndexError:
            focus = None

        columnboxes = []
        for column in self.get_column_nodes():
            columnbox = ColumnBox(self.ui, column.label)
            columnbox.reload()
            columnboxes.append((columnbox, self.options()))
        self.contents = columnboxes

        if self.contents:
            if focus is None:
                self.focus_position = 0
            else:
                self.focus_position = focus  # TODO: does this help?

    def get_column_nodes(self):
        if self.active_tab_nr < len(self.ui.tabs):
            active_tab = self.ui.tabs[self.active_tab_nr]
            return active_tab.getChildrenNodes()
        else:
            return []


class ColumnBox(urwid.ListBox):
    def __init__(self, ui, label):
        self.ui = ui
        self.label = label
        self.list_walker = urwid.SimpleFocusListWalker([])
        super(ColumnBox, self).__init__(self.list_walker)
        for key, value in VIM_KEYS.items():
            self._command_map[key] = value

    def reload(self):
        focus = self.list_walker.focus

        for column in self.ui.kanban_layout.get_column_nodes():
            if column.label == self.label:
                break
        else:
            raise UserFacingException('Column with label %s does not exist' % self.label)

        self.list_walker[:] = []

        self.list_walker.append(urwid.AttrMap(urwid.Text(self.label), 'heading'))
        self.list_walker.append(urwid.Divider())
        for entry in column.getChildrenNodes():
            widget = EntryButton(self.ui, entry)
            widget = urwid.AttrMap(widget, 'button', 'focus button')
            self.list_walker.append(widget)

        if not focus:  # Avoid starting with the bottom item focused
            self.list_walker.set_focus(0)
