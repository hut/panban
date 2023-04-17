![screenshot](screenshot.png)

# Panban

A modular kanban tool with swappable front-ends and database interfaces.  It
allows you to view various kinds of structured data as a kanban board, with a
consistent UI.  Currently supported data formats are:

- Markdown lists (read+write)
- todo.txt (read+write)
- GitHub issues (read only)

This project is an early (albeit functional) prototype, not actively in
development anymore.

# Key bindings

| key        | action                          |
|------------|---------------------------------|
| j          | move down                       |
| k          | move up                         |
| h          | move to the column on the left  |
| l          | move to the column on the right |
| `ENTER`    | edit entry                      |
| z          | toggle visibility of metadata   |
| A          | add new entry                   |
| X          | delete entry                    |
| R          | reload entries                  |
| q or `TAB` | change the tab/project          |
| Q          | quit                            |

As of 2019-04-22, it is necessary to reload after certain operations to ensure
that the program doesn't crash.  To be on the safe side, just reload the data
with `R` after every operation.

# How to run

- `./panban.py -b todotxt test/todo.txt`
- `./panban.py -b markdown test/markdown.md`

You can also use this to view github issues (read-only):

- `./panban.py -b github ranger/ranger`

![screenshot of github issues](screenshot_github.png)
