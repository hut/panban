import os
import re
import subprocess
import tempfile
import time

import urwid

from panban.backends import get_backend_from_uri
from panban.json_api.eternal import DEFAULT_PRIO
from panban.api import UserFacingException
from panban.util import extract_urls
from panban.controller import DatabaseAbstraction

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
important       light_magenta /
important_focused light_magenta,standout /

header              light_gray,standout /
header_todo         dark_blue,standout /
header_backlog      dark_gray,standout /
header_active       dark_red,standout /
header_in_progress  dark_red,standout /
header_done         dark_green,standout /
header_urgent       light_magenta,standout /
header_next         dark_blue,standout /
"""

ACTIVE_COLUMNS = ['active']
DONE_COLUMNS = ['finished', 'done']

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
CHOICE_ALL_TAGS = '[All Tags]'


class UI(object):
    def __init__(self, source_uris, initial_tab=None, debug=False, theme=None, use_titlebar=True):
        self.dbs = {}
        for source_uri in source_uris:
            self.load_db(source_uri)

        self.source_uris = source_uris
        self.db_uri = source_uris[0]
        self.db = self.dbs[self.db_uri]
        self.loop = None
        self.debug = debug
        self.initial_tab = initial_tab
        self.filter_regex = None
        self.filter_tag = None
        self.hide_left_column = False
        self.use_titlebar = use_titlebar

        self.theme = DEFAULT_THEME
        if theme is not None:
            self.theme += open(theme, 'r').read()
        self.palette = self._parse_theme(self.theme)

        self.kanban_layout = KanbanLayout(self)
        self.base = Base(self, self.db, self.kanban_layout)
        self.tabs = None  # DEPRECATED. there's always only one "tab".

        self._tag_priorities = dict()

        self._choice_callback = None
        self._choice_callback_params = ()
        self._choice_exit_key = None
        self._choice_focus = None
        self._choice_options = None
        self._choice_quick_keys = None
        self._choice_styles = ()

        self._original_urwid_SHOW_CURSOR = urwid.escape.SHOW_CURSOR

    def _parse_theme(self, theme):
        palette = []
        for line in theme.split('\n'):
            line = line.strip()
            if line.startswith('#') or line.startswith('/'):
                continue
            components = line.split()

            # Components are: (see https://urwid.org/tutorial)
            # - Name of the display attribute, typically a string
            # - Foreground color and settings for 16-color (normal) mode
            # - Background color for normal mode
            # - Settings for monochrome mode (optional)
            # - Foreground color and settings for 88 and 256-color modes (optional)
            # - Background color for 88 and 256-color modes (optional)
            if len(components) not in (3, 4, 6):
                continue
            if components[0] == 'default':
                components[0] = None
            for i in range(1, len(components)):
                components[i] = components[i].replace('_', ' ')
                if components[i] == '/':
                    components[i] = ''
            palette.append(tuple(components))
        return palette

    def load_db(self, source_uri):
        if source_uri not in self.dbs:
            source_backend = get_backend_from_uri(source_uri)
            backend_handler = source_backend.Handler()
            self.dbs[source_uri] = DatabaseAbstraction(backend_handler, source_uri)
        else:
            raise Exception("Duplicate Source: %s" % source_uri)

    def change_db(self, source_uri):
        # If the source file hasn't been loaded before, load it now:
        if source_uri not in self.dbs:
            self.load_db(source_uri)

        self.db = self.dbs[source_uri]
        self.db_uri = source_uri
        self.db.reload()
        self.rebuild()

    def rotate_db(self, offset):
        if len(self.dbs) > 1:
            dbs_list = list(self.dbs)
            db_id = dbs_list.index(self.db_uri)
            new_id = (db_id + offset) % len(dbs_list)
            self.change_db(dbs_list[new_id])

    def activate(self):
        if self.loop is None:
            self.hide_cursor()
            self.reload()
            self.loop = urwid.MainLoop(self.base, self.palette)
            try:
                self.loop.screen.set_terminal_properties(colors=256)
            except:
                pass
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

    def edit_in_panban(self, string, callback, backend):
        """WARNING: Experimental, may cause data loss"""

        # Sanity checks.
        if not string:
            return
        if len(string) < 10:
            return
        if backend == 'markdown':
            if string.count('#') < 2:
                return
        else:
            raise Exception("edit_in_panban supports only markdown backend for now")

        # Write temporary file
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        filename = tmp.name
        tmp.write(string)
        tmp.close()

        # Call a sub-panban
        self.system(['panban', filename])

        # Read temporary file for changes & delete it
        with open(filename, 'r') as f:
            new_string = f.read().rstrip('\n')
        os.unlink(filename)

        # Finish up
        if string != new_string:
            callback(new_string)
        self.reload()

    def edit_string_externally(self, string=''):
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

    def edit_string_async(self, string, title, callback, callback_params=None):
        self.base._open_edit_popup(string, title, callback, callback_params)

    def user_choice(
            self,
            options,
            callback,
            styles=(),
            quick_keys=None,
            focus=0,
            exit_key=None,
            callback_params=None
        ):
        """
        Opens up a pop-up that lets the user choose one of the given options.
        """

        self._choice_callback = callback
        self._choice_callback_params = callback_params or ()
        self._choice_options = options
        self._choice_styles = styles
        self._choice_quick_keys = quick_keys
        self._choice_focus = focus
        self._choice_exit_key = exit_key
        self.base._open_choice_popup()

    def user_choice_source(self, exit_key=None):
        options = dict((path, os.path.basename(path)) for path in self.dbs)
        current_db_index = list(self.dbs).index(self.db_uri)
        self.user_choice(
            options=options,
            callback=self.change_db,
            exit_key=exit_key,
            focus=current_db_index,
        )

    def user_choice_filtertag(self, exit_key=None):
        all_tags = list(self.db.all_tags)
        all_tags.sort()
        all_tags.sort(key=lambda tag: -self._tag_priorities.get(tag, DEFAULT_PRIO))
        options = [CHOICE_ALL_TAGS] + all_tags
        styles = [None]
        for tag in all_tags:
            prio = self._tag_priorities.get(tag, DEFAULT_PRIO)
            style = COLOR_MAP_BY_PRIO[prio]
            styles.append((style, style + '_focused'))

        self.user_choice(
            options=options,
            styles=styles,
            callback=self._user_choice_filtertag_callback,
            exit_key=exit_key,
        )

    def _user_choice_filtertag_callback(self, choice):
        old_filter_tag = self.filter_tag
        if choice == CHOICE_ALL_TAGS:
            self.filter_tag = None
        else:
            self.filter_tag = choice
        if self.filter_tag != old_filter_tag:
            self.rebuild()

    def user_choice_addtag(self, node, exit_key=None):
        possible_new_tags = list(set(self.db.all_tags) - set(node.tags))
        possible_new_tags.sort()
        possible_new_tags.sort(key=lambda tag: -self._tag_priorities.get(tag, DEFAULT_PRIO))
        options = [CHOICE_ABORT] + possible_new_tags + [CHOICE_NEW_TAG]
        self.user_choice(
            options=options,
            callback=self._user_choice_addtag_callback,
            exit_key=exit_key,
            callback_params=[node],
        )

    def _user_choice_addtag_callback(self, choice, node):
        if choice == CHOICE_NEW_TAG:
            self.edit_string_async('', 'Add Tag', self._user_choice_addtag_edit_callback, [node])
        elif choice not in (CHOICE_ABORT, CHOICE_NEW_TAG):
            node.add_tags(choice)
            # TODO: This reload is excessive and should be handled by updating the cache instead
            self.reload()

    def _user_choice_addtag_edit_callback(self, tag_name, node):
        if tag_name:
            node.add_tags(tag_name)
            # TODO: This reload is excessive and should be handled by updating the cache instead
            self.reload()

    def user_choice_removetag(self, node, exit_key=None):
        options = [CHOICE_ABORT] + sorted(node.tags)
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
        self.edit_string_async('', 'New Task', self._add_node_callback, [column_id, prio])

    def _add_node_callback(self, new_label, column_id, prio):
        if new_label.strip():
            tags = [self.filter_tag] if self.filter_tag else []
            self.db.add_node(new_label, column_id, prio=prio, tags=tags)
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
        self._apply_priorities_from_task_description(root_nodes)
        root_nodes.sort(key=lambda node: node.label)
        root_nodes.sort(key=lambda node: -(node.prio or 0))
        self.tabs = root_nodes
        self.kanban_layout.reload()

    def _apply_priorities_from_task_description(self, root_nodes):
        # (Written on 2023-05-02. Details may have changed since then)
        # This is a hacky/temporary method to solve this problem:
        #
        # Tags in the tag list are sorted by priority, but there is no way to
        # assign priorities or any kind of metadata to tags in most backends.
        #
        # As a workaround, this method will look for a task called
        # "Tag Priorities" in the database which should have a description
        # string that is a valid panban database in markdown format.
        # If this markdown DB has columns of the name "High", "Medium", "Low",
        # and/or "None", the tasks within these columns will cause the tags in
        # the original DB to get priorities assigned to 3, 2, 1, or 0
        # respectively.
        #
        # Example:
        #
        # If the description of the task "Tag Priorities" is the following:
        #
        #     # High
        #
        #     - career
        #     - family
        #
        #     # Foobar
        #
        #     - exercise
        #
        # Then the tags "career" and "family" will get a priority of 3, while
        # the tag "exercise" will remain with the default priority.
        #
        # This description is edited in the easiest way with the "B" key which
        # opens the description of the task in a separate panban board.

        from panban.backends import markdown
        from panban.controller import DatabaseAbstraction
        import io

        prio_node = None
        task = None
        for uid, task in self.db.nodes_by_id.items():
            if task.label == 'Tag Priorities':
                prio_node = task
                break

        if task is None or not task.description:
            self._tag_priorities = dict()
            return

        def get_tag_priorities(markdown_string):
            handler = markdown.Handler(json_api='1')
            nodes = handler.load_markdown_string(task.description)
            root_ids = [uid for uid, node in nodes.items()
                if not node.parent]
            columns = [node for node in nodes.values()
                if node.parent in root_ids]
            priority_map = {
                'High': 3,
                'Medium': 2,
                'Low': 1,
                'None': 0,
            }
            tag_priorities = dict()
            for column in columns:
                try:
                    prio = priority_map[column.label]
                except KeyError:
                    continue
                for child_id in column.children:
                    child = nodes[child_id]
                    tag_priorities[child.label] = prio
            return tag_priorities

        self._tag_priorities = get_tag_priorities(task.description)
        for node in root_nodes:
            if node.label in self._tag_priorities:
                node.prio = self._tag_priorities[node.label]


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
        super().__init__(self._generate_button_text())

    def _generate_button_text(self):
        e = self.entry
        if self.entry.is_important():
            self.button_left = urwid.Text("▲")
        if not self.ui.kanban_layout.hide_metadata:
            tags = ','.join(self.entry.tags or ('None', ))
            return f"{e.label} [prio={e.prio} id={e.id[:8]} tags={tags} " + \
                f"create={e.creation_date} complete={e.completion_date}]\n{e.description}"
        else:
            label = e.label
            label = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', label)  # Simplify links TODO: proper md parsing
            if not self.ui.kanban_layout.hide_description and self.entry.description:
                return f"{label}\n{e.description}"
            else:
                return label

    def edit_label(self):
        self._old_label = self.entry.label
        self.ui.base._open_edit_popup(self.entry.label, "Task Title", self._edit_callback)
        # TODO: update EntryButton content

    def _edit_callback(self, new_label):
        if new_label.strip() and self._old_label != new_label:
            self.entry.change_label(new_label)

            # TODO: This reload/rebuild is excessive and should be handled by updating the cache instead
            self.ui.db.reload()
            self.ui.rebuild()

    def keypress(self, size, key):
        if key == 'enter':
            self.edit_label()
            return

        key = super().keypress(size, key)

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
        elif key == 'E':
            new_descr = self.ui.edit_string_externally(self.entry.description or '')
            if new_descr == '':
                new_descr = None
            self.entry.change_description(new_descr)
            # TODO: This reload/rebuild is excessive and should be handled by updating the cache instead
            self.ui.db.reload()
            self.ui.rebuild()
        elif key == 'A':
            self.ui._add_node(self.columnbox.column.id, self.entry.prio)
        elif key == 'B':
            self.ui.edit_in_panban(self.entry.description,
                                   callback=self.entry.change_description,
                                   backend='markdown')
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
    def __init__(self, ui, db, content):
        super().__init__(content)
        self.ui = ui
        self.db = db
        self.content_widget = content
        self.choice_widget = ChoiceMenuBox(self.ui)
        self.overlay_widget_choice = urwid.Overlay(
            urwid.LineBox(self.choice_widget),
            content, 'center', 23, 'middle', 10)

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
        if key == 'q':
            self.ui.user_choice_filtertag()
        elif key == 's':
            self.ui.user_choice_source(exit_key='s')
        elif key == 'tab':
            self.ui.rotate_db(1)
        elif key == 'shift tab':
            self.ui.rotate_db(-1)
        elif key == 'Q':
            raise urwid.ExitMainLoop()
        elif key == 'R':
            self.reload()
        elif key == '/':
            self.ui.edit_string_async('', 'Regex Filter', self._apply_filter)
        elif key == 'esc':
            if self.ui.filter_regex:
                # First, ESC resets the search/regex filter
                self.ui.filter_regex = None
                self.ui.rebuild()
            elif self.ui.filter_tag:
                # The second ESC press resets the tag filter
                self.ui.filter_tag = None
                self.ui.rebuild()
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


class ChoiceMenuBox(urwid.ListBox):
    def __init__(self, ui):
        self.ui = ui
        self.list_walker = urwid.SimpleFocusListWalker([])
        super().__init__(self.list_walker)

    def keypress(self, size, key):
        key = super().keypress(size, key)

        if key in ('tab', 'q', 'esc') or (self.ui._choice_exit_key is not None
                                          and key == self.ui._choice_exit_key):
            self.ui.base._close_popup()
        # Do NOT return the key here to block downstream key bindings

    def load_options(self):
        self.list_walker[:] = []
        # TODO: clean up button objects. disconnect signals if necessary

        if isinstance(self.ui._choice_options, dict):
            options = [(value, label) for value, label in self.ui._choice_options.items()]
        else:
            options = [(label, label) for label in self.ui._choice_options]

        for i, option in enumerate(options):
            value, label = option
            button = ChoiceMenuButton(self, self.ui, value, label)

            styles = self.ui._choice_styles
            if styles and i < len(styles) and styles[i] is not None:
                style, style_focused = styles[i]
            else:
                style, style_focused = 'button', 'button_focused'

            urwid.connect_signal(button, 'click', ChoiceMenuButton.click)
            button = urwid.AttrMap(button, style, style_focused)
            self.list_walker.append(button)

        if self.ui._choice_focus:
            self.list_walker.set_focus(self.ui._choice_focus)


class ChoiceMenuButton(urwid.Button):
    button_left = urwid.Text("")
    button_right = urwid.Text("")
    def __init__(self, menu, ui, value, label):
        super().__init__(label)
        self.ui = ui
        self.menu = menu
        self.value = value

    def click(self):
        self.ui.base._close_popup()
        self.ui._choice_callback(self.value, *self.ui._choice_callback_params)


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
        self.hide_metadata = not self.ui.debug
        self.hide_description = True
        super().__init__([], dividechars=1)
        for key, value in VIM_KEYS.items():
            self._command_map[key] = value

    def reload(self):
        try:
            focus = self.focus_position
        except IndexError:
            focus = None

        columnboxes = []
        for i, column in enumerate(self.get_column_nodes()):
            if i == 0 and self.ui.hide_left_column:
                continue

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

    def keypress(self, size, key):
        key = super().keypress(size, key)
        if key == 'z':
            self.hide_description ^= True
            self.ui.rebuild()
        elif key == 'Z':
            self.hide_metadata ^= True
            self.ui.rebuild()
        elif key == '`':
            self.ui.hide_left_column ^= True
            self.ui.rebuild()
        else:
            return key

class ColumnBox(urwid.ListBox):
    def __init__(self, ui, column):
        self.ui = ui
        self.label = column.label
        self.column = column
        self.list_walker = urwid.SimpleFocusListWalker([])
        super().__init__(self.list_walker)
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

        if self.ui.use_titlebar:
            palette_keys = [component[0] for component in self.ui.palette]
            palette_key = 'header_' + self.label.lower().replace(' ', '_')
            if palette_key in palette_keys:
                styling = palette_key
            else:
                styling = 'header'

            self.list_walker.append(urwid.AttrMap(urwid.Text(label), styling))
            self.list_walker.append(urwid.Divider())

        done = self.label.lower() in DONE_COLUMNS
        active = self.label.lower() in ACTIVE_COLUMNS
        nodes = list(column.getChildrenNodes())

        if self.ui.filter_tag:
            nodes = [node for node in nodes if self.ui.filter_tag in node.tags]
        if self.ui.filter_regex:
            filter_regex = re.compile(self.ui.filter_regex, flags=re.I)
            nodes = [node for node in nodes if filter_regex.search(node.label)]

        nodes.sort(key=lambda node: node.label)
        if done:
            nodes.sort(key=lambda node: node.completion_date or '0000-00-00')
            nodes.reverse()
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
            if entry.is_important():
                color = 'important'
            else:
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
        key = super().keypress(size, key)
        if key == 'A':
            # This is only reached when there is no focused node in the column
            self.ui._add_node(self.column.id, DEFAULT_PRIO)
        else:
            return key
