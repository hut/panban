import urwid
import subprocess

from panban.controller import UserFacingException

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

        self.menu = MenuBox(self)
        self.kanban_layout = KanbanLayout(self)
        self.base = Base(self, db, self.kanban_layout, self.menu)

    def activate(self):
        self.reload()
        self.loop = urwid.MainLoop(self.base, PALETTE)
        self.loop.run()

    def system(self, command):
        self.loop.stop()
        try:
            subprocess.check_call(command)
        except KeyboardInterrupt:
            pass
        self.base.reload()
        self.loop.start()

    def get_entries(self):
        return self.db.get_columns()

    def main(self):
        self.activate()
        try:
            pass
        finally:
            self.deactivate()

    def reload(self):
        self.db.reload()
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
        super(KanbanLayout, self).__init__(self.columns, dividechars=1)
        for key, value in VIM_KEYS.items():
            self._command_map[key] = value

    def reload(self):
        try:
            focus = self.focus_position
        except IndexError:
            focus = None

        columnboxes = []
        for column in self.ui.db.columns:
            columnbox = ColumnBox(self.ui, column.title)
            columnbox.reload()
            columnboxes.append((columnbox, self.options()))
        self.contents = columnboxes

        if self.contents:
            if focus is None:
                self.focus_position = 0
            else:
                self.focus_position = focus  # TODO: does this help?


class ColumnBox(urwid.ListBox):
    def __init__(self, ui, title):
        self.ui = ui
        self.title = title
        self.list_walker = urwid.SimpleFocusListWalker([])
        super(ColumnBox, self).__init__(self.list_walker)
        for key, value in VIM_KEYS.items():
            self._command_map[key] = value

    def reload(self):
        focus = self.list_walker.focus

        for column in self.ui.db.columns:
            if column.title == self.title:
                break
        else:
            raise UserFacingException('Column with title %s does not exist' % self.title)

        self.list_walker[:] = []
        for entry in column.entries:
            widget = EntryButton(self.ui, entry)
            widget = urwid.AttrMap(widget, 'button', 'focus button')
            self.list_walker.append(widget)

        if not focus:  # Avoid starting with the bottom item focused
            self.list_walker.set_focus(0)