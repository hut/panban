![screenshot](demos/markdown/screenshot_markdown.png)

# Panban

NOTE: This project is a work in progress and is not suitable for general use.

A modular kanban tool with swappable front-ends and database interfaces.  It
allows you to view various kinds of structured data as a kanban board, with a
consistent UI.  Currently supported data formats are:

- [Markdown lists](demos/markdown/README.md) (read+write)
- [todo.txt](demos/todotxt/README.md) (read+write)
- [GitHub issues](demos/github/README.md) (read only)
- [CalDav VTODO Tasks](demos/caldav/README.md), synced via e.g. [vdirsyncer](https://github.com/pimutils/vdirsyncer) (read+write)

# Key bindings

| key        | action                                                       |
|------------|--------------------------------------------------------------|
| h/j/k/l    | move left/down/up/right (vim-like keybindings)               |
| `ENTER`    | edit entry                                                   |
| p          | edit task priority                                           |
| 1-9        | move entry to column N                                       |
| +/-        | add/remove tags                                              |
| z          | toggle visibility of metadata                                |
| /          | filter entries by regex                                      |
| ?          | reset filter                                                 |
| o          | open first URL in task description in Firefox                |
| A          | add new entry                                                |
| X          | delete entry                                                 |
| R          | reload entries                                               |
| q or `TAB` | change the tab/project                                       |
| Q          | quit                                                         |

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
