![screenshot](demos/markdown/screenshot_markdown.png)

# Panban

**⚠️ This is not production-ready software. This project is in active development ⚠️**

A modular kanban tool with swappable front-ends and database interfaces.  It
allows you to view various kinds of structured data as a kanban board, with a
consistent UI.  Currently supported data formats are:

- [Markdown lists](demos/markdown/README.md) (read+write)
- [todo.txt](demos/todotxt/README.md) (read+write)
- [GitHub issues](demos/github/README.md) (read only)
- [CalDav VTODO Tasks](demos/caldav/README.md), synced via e.g. [vdirsyncer](https://github.com/pimutils/vdirsyncer) (read+write)

# Key bindings

| key        | action                                                           |
|------------|------------------------------------------------------------------|
| h/j/k/l    | move left/down/up/right (vim-like keybindings)                   |
| `ENTER`    | edit task label                                                  |
| E          | edit task description                                            |
| p          | edit task priority                                               |
| 1-9        | move task to column N                                            |
| +/-        | add/remove tags                                                  |
| z          | toggle visibility of task description                            |
| Z          | toggle visibility of metadata                                    |
| /          | filter entries by regex                                          |
| o          | open first URL in task description in Firefox                    |
| A          | add new task                                                     |
| X          | delete task                                                      |
| R          | reload tasks                                                     |
| q or `TAB` | change the tab/project                                           |
| B          | Experimental: Edit task description as markdown panban sub-board |
| Q          | quit                                                             |

As of 2019-04-22, it is necessary to reload after certain operations to ensure
that the program doesn't crash.  To be on the safe side, just reload the data
with `R` after every operation.

# How to run

First download panban and install the dependencies:

```
git clone https://codeberg.org/hut/panban.git
pip install urwid  # required
pip install icalendar  # optional, for CalDav VTODO backend
pip install todotxtio  # optional, for todo.txt backend
cd panban
```

Then you can try out the desired backend with the provided demo database.

KEEP A BACKUP OF YOUR DATABASE. PANBAN IS STILL A WORK IN PROGRESS AND MAY CAUSE DATA LOSS

- `./panban.py -b todotxt demos/todotxt/todo.txt`
- `./panban.py -b markdown demos/markdown/markdown.md`
- `./panban.py -b caldav demos/caldav`

You can also use this to view github issues (read-only):

- `./panban.py -b github ranger/ranger`

![screenshot of github issues](demos/github/screenshot_github.png)

# License

Copyright (C) 2023  Roman Zimbelmann

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License version 3 as
published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
