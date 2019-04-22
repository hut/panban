import subprocess
import time
import urwid
import tempfile
import os

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
    ('heading_Urgent', 'black', 'light magenta'),
]


class UI(object):
    def __init__(self, db, debug=False):
        self.db = db
        self.loop = None
        self.debug = debug

        self.menu = MenuBox(self)
        self.kanban_layout = KanbanLayout(self)
        self.base = Base(self, db, self.kanban_layout, self.menu)
        self.tabs = None

        self._original_urwid_SHOW_CURSOR = urwid.escape.SHOW_CURSOR

    def activate(self):
        if self.loop is None:
            # Workaround for hiding cursor, see
            # https://github.com/urwid/urwid/issues/170
            urwid.escape.SHOW_CURSOR = ''
            self.reload()
            self.menu.reload()
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

    def edit_string(self, string):
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False)
        filename = tmp.name
        tmp.write(string)
        tmp.close()
        self.system(['vim', filename])
        with open(filename, 'r') as f:
            new_string = f.read().rstrip('\n')
        os.unlink(filename)
        return new_string

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
        self.tabs = self.db.get_root_nodes()
        self.kanban_layout.reload()
        self.menu.reload()


class EntryButton(urwid.Button):
    button_left = urwid.Text("-")
    button_right = urwid.Text("")

    def __init__(self, ui, entry):
        self.ui = ui
        self.entry = entry
        if self.ui.debug:
            label = "%s <%s>" % (entry.label, entry.id[:8])
        else:
            label = entry.label
        super(EntryButton, self).__init__(label)
        urwid.connect_signal(self, 'click', lambda button: button.edit_label())

    def edit_label(self):
        new_label = self.ui.edit_string(self.entry.label)
        self.entry.change_label(new_label)

    def keypress(self, size, key):
        if key == 'X':
            self.entry.delete()
        elif key in '123456789':
            key_int = ord(key) - ord('1')
            tab = self.ui.tabs[self.ui.kanban_layout.active_tab_nr]
            column_id = tab.children[key_int]
            self.entry.move_to_column(column_id)
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

    def reload(self):
        focus = self.list_walker.focus
        self.list_walker[:] = []
        for entry in self.ui.tabs:
            button = MenuButton(self.ui, entry.label, entry.id)
            urwid.connect_signal(button, 'click',
                    lambda button: button.click())
            button = urwid.AttrMap(button, 'button', 'focus button')
            self.list_walker.append(button)
        if not focus:  # Avoid starting with the bottom item focused
            self.list_walker.set_focus(0)


class MenuButton(urwid.Button):
    def __init__(self, ui, label, node_id):
        super(MenuButton, self).__init__(label)
        self.ui = ui
        self.node_id = node_id

    def click(self):
        self.ui.kanban_layout.change_tab_by_node_id(self.node_id)
        self.ui.base.flip()


class KanbanLayout(urwid.Columns):
    def __init__(self, ui):
        self.ui = ui
        self.active_tab_nr = 0
        super(KanbanLayout, self).__init__([], dividechars=1)
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

    def change_tab_by_node_id(self, node_id):
        for i, tab in enumerate(self.ui.tabs):
            if tab.id == node_id:
                self.active_tab_nr = i
                break
        self.ui.rebuild()

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

        if self.ui.debug:
            label = "%s <%s>" % (self.label, column.id[:8])
        else:
            label = self.label
        styling = 'heading'
        if self.label.lower() == 'active':
            styling = 'heading_Active'
        elif self.label.lower() in ('urgent', 'high prio'):
            styling = 'heading_Urgent'
        elif self.label.lower() in ('inactive', 'todo'):
            styling = 'heading_Inactive'
        elif self.label.lower() in ('finished', 'done'):
            styling = 'heading_Finished'
        self.list_walker.append(urwid.AttrMap(urwid.Text(label), styling))
        self.list_walker.append(urwid.Divider())
        for entry in column.getChildrenNodes():
            widget = EntryButton(self.ui, entry)
            widget = urwid.AttrMap(widget, 'button', 'focus button')
            self.list_walker.append(widget)

        if not focus:  # Avoid starting with the bottom item focused
            self.list_walker.set_focus(0)
