# Panban

A modular kanban tool with swappable front-ends and database interfaces.

This project is still in alpha phase, expect everything to change.

# Key bindings

|------------|---------------------------------|
| j          | move down                       |
| k          | move up                         |
| h          | move to the column on the left  |
| l          | move to the column on the right |
| <Enter>    | edit entry                      |
| A          | add new entry                   |
| X          | delete entry                    |
| R          | reload entries                  |
| q or <TAB> | change the tab/project          |
| Q          | quit                            |
|------------|---------------------------------|

As of 2019-04-22, it is necessary to reload after certain operations to ensure
that the program doesn't crash.  To be on the safe side, just reload the data
with `R` after every operation.
