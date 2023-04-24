import os
import re
import subprocess
import tempfile
import time

import urwid

from panban.json_api.eternal import DEFAULT_PRIO
from panban.api import UserFacingException
from panban.util import extract_urls

VIM_KEYS = {
    'h': 'cursor left',
    'l': 'cursor right',
    'j': 'cursor down',
    'k': 'cursor up',
    'd': 'cursor page down',
    'J': 'cursor page down',
    'u': 'cursor page up',
    'K': 'cursor page up',
    'g': 'cursor max left',
    'G': 'cursor max right',
}

# Each line: "Context Foreground Background", items separated by whitespace.
# Available colors: http://urwid.org/manual/displayattributes.html
# Replace spaces in attributes by "_", e.g. "light red" -> "light_red".
DEFAULT_THEME = """
default         / /
prio0           dark_blue /
prio0_focused   dark_blue,standout /
prio1           / /
prio1_focused   standout /
prio2           / /
prio2_focused   standout /
prio3           light_red /
prio3_focused   light_red,standout /
button          / /
button_focused  standout /
header          light_gray,standout /
header_inactive dark_gray,standout /
header_active   dark_red,standout /
header_finished dark_green,standout /
header_urgent   light_magenta,standout /
header_next     dark_blue,standout /
"""

COLOR_MAP_BY_PRIO = {
    0: 'prio0',
    1: 'prio1',
    2: 'prio2',
    3: 'prio3',
}
PRIO_LABELS = {
    3: '3: High',
    2: '2: Medium',
    1: '1: Low',
    0: '0: None',
}

CHOICE_ABORT = '[Cancel]'
CHOICE_NEW_TAG = '[New Tag]'


class UI(object):
    def __init__(self, db, initial_tab=None, debug=False, theme=None):
        self.db = db
        self.loop = None
        self.debug = debug
        self.initial_tab = initial_tab
        self.filter_regex = None

        self.theme = DEFAULT_THEME
        if theme is not None:
            self.theme += open(theme, 'r').read()

        self.menu = MenuBox(self)
        self.choice_menu = ChoiceMenuBox(self)
        self.kanban_layout = KanbanLayout(self)
        self.base = Base(self, db, self.kanban_layout, self.menu, self.choice_menu)
        self.tabs = None

        self._original_urwid_SHOW_CURSOR = urwid.escape.SHOW_CURSOR

    def _parse_theme(self, theme):
        palette = []
        for line in theme.split('\n'):
            line = line.strip()
            if line.startswith('#') or line.startswith('/'):
                continue
            components = line.split()
            if len(components) != 3:
                continue
            tag, fg, bg = components
            if tag == 'default':
                tag = None
            fg = fg.replace('_', ' ')
            bg = bg.replace('_', ' ')
            if fg == '/':
                fg = ''
            if bg == '/':
                bg = ''
            palette.append((tag, fg, bg))
        return palette

    def activate(self):
        if self.loop is None:
            self.hide_cursor()
            self.reload()
            self.menu.reload()
            palette = self._parse_theme(self.theme)
            self.loop = urwid.MainLoop(self.base, palette)
        else:
            raise Exception("Do not call UI.activate() more than once!")

    def deactivate(self):
        self.loop.screen.write(self._original_urwid_SHOW_CURSOR)
        try:
            self.loop.stop()
        except AttributeError:
            pass

    def reactivate(self):
        self.base.reload()
        self.loop.start()

    def hide_cursor(self):
        # Workaround, see https://github.com/urwid/urwid/issues/170
        urwid.escape.SHOW_CURSOR = ''

    def show_cursor(self):
        urwid.escape.SHOW_CURSOR = self._original_urwid_SHOW_CURSOR

    def system(self, command):
        self.deactivate()
        try:
            subprocess.check_call(command)
        except KeyboardInterrupt:
            pass
        self.reactivate()

    def edit_string(self, string=''):
        tmp = tempfile.NamedTemporaryFile(mode='w', delete=False)
        filename = tmp.name
        if string:
            tmp.write(string)
        tmp.close()
        if string:
            self.system(['vim', filename])
        else:
            self.system(['vim', '-c', 'startinsert', filename])
        with open(filename, 'r') as f:
            new_string = f.read().rstrip('\n')
        os.unlink(filename)
        return new_string

    def edit_string_async(self, string, title, callback):
        self.base._open_edit_popup(string, title, callback)

    def user_choice(self, options, callback, quick_keys=None, focus=0,
            exit_key=None, callback_params=None):
        """
        Opens up a pop-up that lets the user choose one of the given options.
        """

        self._choice_callback = callback
        self._choice_callback_params = callback_params
        self._choice_options = options
        self._choice_quick_keys = quick_keys
        self._choice_focus = focus
        self._choice_exit_key = exit_key
        self.base._open_choice_popup()

    def user_choice_addtag(self, node, exit_key=None):
        possible_new_tags = list(sorted(set(self.db.all_tags) - set(node.tags)))
        options = [CHOICE_ABORT] + possible_new_tags + [CHOICE_NEW_TAG]
        self.user_choice(
            options=options,
            callback=self._user_choice_addtag_callback,
            exit_key=exit_key,
            callback_params=[node],
        )

    def _user_choice_addtag_callback(self, choice, node):
        if choice == CHOICE_NEW_TAG:
            tag = self.edit_string('')
            if tag:
                node.add_tags(tag)
                # TODO: This reload is excessive and should be handled by updating the cache instead
                self.reload()
        elif choice not in (CHOICE_ABORT, CHOICE_NEW_TAG):
            node.add_tags(choice)
            # TODO: This reload is excessive and should be handled by updating the cache instead
            self.reload()

    def user_choice_removetag(self, node, exit_key=None):
        options = [CHOICE_ABORT] + node.tags
        self.user_choice(
            options=options,
            callback=self._user_choice_removetag_callback,
            exit_key=exit_key,
            callback_params=[node],
        )

    def _user_choice_removetag_callback(self, choice, node):
        if choice != CHOICE_ABORT:
            node.remove_tags(choice)
            # TODO: This reload is excessive and should be handled by updating the cache instead
            self.reload()

    def user_choice_prio(self, node, exit_key=None):
        self.user_choice(
            options=PRIO_LABELS,
            exit_key=exit_key,
            focus=list(PRIO_LABELS).index(node.prio),
            callback=self._user_choice_prio_callback,
            callback_params=[node],
        )

    def _user_choice_prio_callback(self, prio, node):
        old_prio = node.prio
        node.change_prio(prio)
        if old_prio != node.prio:
            self.rebuild()

    def _add_node(self, column_id, prio):
        new_label = self.edit_string()
        if new_label.strip():
            self.db.add_node(new_label, column_id, prio=prio)
            # TODO: This rebuild is excessive and should be handled by updating the cache instead
            self.rebuild()

    def open_in_browser(self, url):
        subprocess.Popen(['firefox', url])

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

        root_nodes = self.db.get_root_nodes()
        root_nodes.sort(key=lambda node: node.label)
        root_nodes.sort(key=lambda node: -(node.prio or 0))
        self.tabs = root_nodes
        self.kanban_layout.reload()
        self.menu.reload()


class DummyButton(urwid.Button):
    button_left = urwid.Text("")
    button_right = urwid.Text("")


class EntryButton(urwid.Button):
    button_left = urwid.Text("-")
    button_right = urwid.Text("")

    def __init__(self, ui, columnbox, entry):
        self.ui = ui
        self.columnbox = columnbox
        self.entry = entry
        if not self.ui.kanban_layout.hide_metadata:
            label = "{0.label} [prio={0.prio} id={1} tags={2} create={0.creation_date} complete={0.completion_date}]".format(entry, entry.id[:8], ','.join(entry.tags or ('None', )))
        else:
            label = entry.label
        super(EntryButton, self).__init__(label)
        urwid.connect_signal(self, 'click', EntryButton.edit_label)

    def edit_label(self):
        self._old_label = self.entry.label
        self.ui.base._open_edit_popup(self.entry.label, "Task Title", self._edit_callback)

    def _edit_callback(self, new_label):
        if new_label.strip() and self._old_label != new_label:
            self.entry.change_label(new_label)

            # TODO: This reload/rebuild is excessive and should be handled by updating the cache instead
            self.ui.db.reload()
            self.ui.rebuild()

    def keypress(self, size, key):
        key = super(EntryButton, self).keypress(size, key)
        if key == 'X':
            self.entry.delete()
        elif key == 'o':
            urls = extract_urls(self.entry.label)
            if urls:
                self.ui.open_in_browser(urls[0])
        elif key == '+':
            # NOTE: if you change the key for this binding, update exit_key:
            self.ui.user_choice_addtag(self.entry, exit_key='+')
        elif key == '-':
            # NOTE: if you change the key for this binding, update exit_key:
            self.ui.user_choice_removetag(self.entry, exit_key='-')
        elif key == 'p':
            # NOTE: if you change the key for this binding, update exit_key:
            self.ui.user_choice_prio(self.entry, exit_key='p')
        elif key == 'A':
            self.ui._add_node(self.columnbox.column.id, self.entry.prio)
        elif key in tuple('123456789'):
            key_int = ord(key) - ord('1')
            tab = self.ui.tabs[self.ui.kanban_layout.active_tab_nr]
            column_id = tab.children[key_int]
            self.entry.move_to_column(column_id)
            # TODO: This reload is excessive and should be handled by updating the cache instead
            self.ui.reload()
        else:
            return key


class Base(urwid.WidgetPlaceholder):
    def __init__(self, ui, db, content, menu, choice_menu):
        super(Base, self).__init__(content)
        self.content_widget = content
        self.menu_widget = menu
        self.ui = ui
        self.db = db
        self.choice_widget = choice_menu
        self.overlay_widget = urwid.Overlay(
            urwid.LineBox(self.menu_widget),
            content, 'center', 23, 'middle', 23)
        self.overlay_widget_choice = urwid.Overlay(
            urwid.LineBox(self.choice_widget),
            content, 'center', 23, 'middle', 10)

    def flip(self):
        if self.original_widget == self.content_widget:
            self.original_widget = self.overlay_widget
            self.menu_widget.focus_category(self.ui.kanban_layout.active_tab_nr)
        else:
            self._close_popup()

    def _open_choice_popup(self):
        self.choice_widget.load_options()
        self.original_widget = self.overlay_widget_choice

    def _open_edit_popup(self, edit_text, title=None, callback=None, callback_params=None):
        self.ui.show_cursor()
        self._edit_widget = EditBox(self.ui, edit_text, callback, callback_params)
        self._overlay_widget_edit = urwid.Overlay(
            urwid.Filler(urwid.LineBox(self._edit_widget, title=title)),
            self.content_widget, 'center', 42, 'middle', 6)
        self.original_widget = self._overlay_widget_edit

    def _close_popup(self):
        self.ui.hide_cursor()
        self.original_widget = self.content_widget

    def reload(self):
        self.db.reload()
        self.content_widget.reload()

    def keypress(self, size, key):
        if self.db.last_modification > self.ui.last_rebuild:
            self.ui.rebuild()

        key = super().keypress(size, key)
        if key in ('tab', 'q'):
            self.flip()
        elif key == 'Q':
            raise SystemExit(0)
        elif key == 'R':
            self.reload()
        elif key == '/':
            self.ui.edit_string_async('', 'Regex Filter', self._apply_filter)
        elif key == 'y':
            self.ui.deactivate()
            self.ui.db.sync()
            self.ui.reactivate()
            self.ui.reload()
        else:
            return key

    def _apply_filter(self, pattern):
        self.ui.filter_regex = pattern
        self.ui.rebuild()


class MenuBox(urwid.ListBox):
    def __init__(self, ui):
        self.ui = ui
        self.list_walker = urwid.SimpleFocusListWalker([])
        super(MenuBox, self).__init__(self.list_walker)

    def focus_category(self, category_index):
        # category_index is literally the position of the category in the list
        return self.list_walker.set_focus(category_index)

    def reload(self):
        focus = self.list_walker.focus
        self.list_walker[:] = []
        for entry in self.ui.tabs:
            button = MenuButton(self.ui, entry.label, entry.id)
            urwid.connect_signal(button, 'click',
                    lambda button: button.click())
            button = urwid.AttrMap(button, 'button', 'button_focused')
            self.list_walker.append(button)
        if not focus:  # Avoid starting with the bottom item focused
            self.list_walker.set_focus(0)


class MenuButton(urwid.Button):
    button_left = urwid.Text("")
    button_right = urwid.Text("")
    def __init__(self, ui, label, node_id):
        super(MenuButton, self).__init__(label)
        self.ui = ui
        self.node_id = node_id

    def click(self):
        self.ui.kanban_layout.change_tab_by_node_id(self.node_id)
        self.ui.base.flip()


class ChoiceMenuBox(urwid.ListBox):
    def __init__(self, ui):
        self.ui = ui
        self.list_walker = urwid.SimpleFocusListWalker([])
        super(ChoiceMenuBox, self).__init__(self.list_walker)

    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key in ('tab', 'q', self.ui._choice_exit_key):
            self.ui.base._close_popup()
        else:
            return key

    def load_options(self):
        self.list_walker[:] = []
        # TODO: clean up button objects. disconnect signals if necessary

        if isinstance(self.ui._choice_options, dict):
            options = [(value, label) for value, label in self.ui._choice_options.items()]
        else:
            options = [(label, label) for label in self.ui._choice_options]

        for value, label in options:
            button = ChoiceMenuButton(self, self.ui, value, label)
            urwid.connect_signal(button, 'click', ChoiceMenuButton.click)
            button = urwid.AttrMap(button, 'button', 'button_focused')
            self.list_walker.append(button)

        if self.ui._choice_focus:
            self.list_walker.set_focus(self.ui._choice_focus)


class ChoiceMenuButton(urwid.Button):
    button_left = urwid.Text("")
    button_right = urwid.Text("")
    def __init__(self, menu, ui, value, label):
        super(ChoiceMenuButton, self).__init__(label)
        self.ui = ui
        self.menu = menu
        self.value = value

    def click(self):
        self.ui._choice_callback(self.value, *self.ui._choice_callback_params)
        self.ui.base._close_popup()


class EditBox(urwid.Edit):
    def __init__(self, ui, edit_text, callback=None, callback_params=None):
        super().__init__(edit_text=edit_text, multiline=False)
        self.ui = ui
        self.callback = callback
        if callback_params is None:
            self.callback_params = []
        else:
            self.callback_params = callback_params

    def keypress(self, size, key):
        if key == 'esc':
            self.ui.base._close_popup()
        elif key == 'enter':
            if self.callback:
                self.callback(self.edit_text, *self.callback_params)
            self.ui.base._close_popup()
        else:
            return super().keypress(size, key)


class KanbanLayout(urwid.Columns):
    def __init__(self, ui):
        self.ui = ui
        self.active_tab_nr = 0
        self.first_load = True
        self.hide_metadata = not self.ui.debug
        super(KanbanLayout, self).__init__([], dividechars=1)
        for key, value in VIM_KEYS.items():
            self._command_map[key] = value

    def reload(self):
        try:
            focus = self.focus_position
        except IndexError:
            focus = None

        if self.first_load:
            self.first_load = False
            if self.ui.initial_tab:
                for i, tab in enumerate(self.ui.tabs):
                    if tab.label == self.ui.initial_tab:
                        self.active_tab_nr = i
                        break

        columnboxes = []
        for column in self.get_column_nodes():
            # TODO: don't re-create ColumnBoxes on each reload
            columnbox = ColumnBox(self.ui, column)
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
                self.active_tab_node_id = node_id
                break
        self.ui.rebuild()

    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key == 'z':
            self.hide_metadata ^= True
            self.ui.rebuild()
        else:
            return key

class ColumnBox(urwid.ListBox):
    def __init__(self, ui, column):
        self.ui = ui
        self.label = column.label
        self.column = column
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

        if not self.ui.kanban_layout.hide_metadata:
            label = "%s <%s>" % (self.label, column.id[:8])
        else:
            label = self.label
        styling = 'header'
        if self.label.lower() in ('active', 'in progress'):
            styling = 'header_active'
        elif self.label.lower() in ('urgent', 'high prio', 'high priority'):
            styling = 'header_urgent'
        elif self.label.lower() in ('inactive', 'todo', 'backlog', 'backburner', 'archive', 'blocked'):
            styling = 'header_inactive'
        elif self.label.lower() in ('finished', 'done'):
            styling = 'header_finished'
        elif self.label.lower() in ('next', 'upcoming'):
            styling = 'header_next'
        self.list_walker.append(urwid.AttrMap(urwid.Text(label), styling))
        self.list_walker.append(urwid.Divider())

        done = self.label.lower() in ('finished', 'done')
        active = self.label.lower() in ('active', )
        nodes = list(column.getChildrenNodes())

        if self.ui.filter_regex:
            filter_regex = re.compile(self.ui.filter_regex, flags=re.I)
            nodes = [node for node in nodes if filter_regex.search(node.label)]

        nodes.sort(key=lambda node: node.label)
        if done:
            nodes.sort(key=lambda node: node.completion_date or '0000-00-00')
            nodes.reverse()
        elif active:
            pass
        else:
            nodes.sort(key=lambda node: -(node.prio or 0))

        def extract_day(node):
            return (node.completion_date or '')[:10]

        previous_group = None
        if done:
            grouper = extract_day
        elif active:
            grouper = None
        else:
            grouper = lambda node: node.prio

        for entry in nodes:
            if grouper is not None:
                group = grouper(entry)
            else:
                group = 1

            if group != previous_group and previous_group is not None:
                #self.list_walker.append(urwid.Divider())
                self.list_walker.append(urwid.Divider())
            previous_group = group

            widget = EntryButton(self.ui, self, entry)
            color = COLOR_MAP_BY_PRIO[entry.prio]
            widget = urwid.AttrMap(widget, color, color + '_focused')
            self.list_walker.append(widget)

        if not nodes:
            widget = DummyButton("")
            color = COLOR_MAP_BY_PRIO[DEFAULT_PRIO]
            widget = urwid.AttrMap(widget, color, color + '_focused')
            self.list_walker.append(widget)

        if not focus:  # Avoid starting with the bottom item focused
            self.list_walker.set_focus(0)

    def keypress(self, size, key):
        key = super(ColumnBox, self).keypress(size, key)
        if key == 'A':
            # This is only reached when there is no focused node in the column
            self.ui._add_node(self.column.id, 0)
        else:
            return key
