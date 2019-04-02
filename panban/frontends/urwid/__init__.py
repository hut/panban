import urwid
import subprocess

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

        #self.kanban_layout = KanbanLayout(db)
        self.menu = Menu(self)
        self.kanban_layout = Menu(self)
        self.base = Base(self, db, self.kanban_layout, self.menu)

    def activate(self):
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


class EntryButton(urwid.Button):
    button_left = urwid.Text("-")
    button_right = urwid.Text("")

    def __init__(self, ui, entry):
        self.ui = ui
        self.entry = entry
        super(MenuButton, self).__init__(label)
        urwid.connect_signal(self, 'click', lambda button: self.ui.system(['vim']))  # TODO

    def keypress(self, size, key):
        if key == 'X':
            self.entry.delete()


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
        for column in self.content_widget.columns:
            column.rebuild_listwalker()

    def keypress(self, size, key):
        if key in ('tab', 'q'):
            self.flip()
        elif key == 'Q':
            raise SystemExit(0)
        elif key == 'R':
            self.reload()
        return super(Base, self).keypress(size, key)  # pylint: disable=not-callable


class Menu(urwid.ListBox):
    def __init__(self, ui):
        self.ui = ui
        self.list_walker = urwid.SimpleFocusListWalker([])
        super(Menu, self).__init__(self.list_walker)
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
