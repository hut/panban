# Reference

This document provides a few quick facts

## Task Attributes

Every task (sometimes called `item` or `node`) has the following attributes:

- `label` (a string defining the visible part of the task)
- `prio` (integer between 0 and 3, inspired by the priorities of CalDAV)
    - 3: High
    - 2: Medium (default)
    - 1: Low
    - 0: None
- `tags` (a list of arbitrary strings for custom categorization)
- `description` (either None or a string containing additional text)
- `id` (a string that uniquely identifies the task)
- `parent` (the unique ID of the column that the task is in)
- `children` (a list of IDs, relevant for columns only, which have the same internal representation as tasks)
- `creation_date` (TODO)
- `completion_date` (TODO)
- `pos` (TODO)
- `attrs` (Additional attributes, currently unused)
- `_raw_json` (the raw JSON that the backend sent to the frontend to declare this task)

## JSON API
### Commands

To interact with the backend, the frontend doesn't directly call a backend's python function, but rather sends commands to the backend module via a JSON API. Every command is a JSON dictionary consisting of the following parameters:

- `command`: A string defining the name of the command (see below)
- `version`: A string defining the JSON API version that the backend should use in the response
- `source`: A string defining where the backend should load the data from
- `arguments`: A dictionary of additional arguments (see below)

The following command names are available:

- `add_node` (Create a new task)
- `change_description`
- `change_label`
- `change_prio`
- `change_tags`
- `delete_nodes`
- `load_all` (Returns the entire database in the response)
- `move_nodes`
- `sync` (For backends that can be synced, e.g. the `caldav` backend will execute the external command `vdirsyncer sync`)

Most commands accept additional parameters:

- add_node
    - `label`: a string containing the label/summary of the task
    - `prio`: a number between 0 and 3 specifying the priority of the new node
    - `target_column`: the node ID of the column into which the node should be placed
    - `tags`: a list of strings specifying the tags of the new node
- change_description:
    - `item_id`: the node ID of the task to be edited
    - `new_description`: a string containing the new description for the node
- change_label:
    - `item_id`: the node ID of the task to be edited
    - `new_label`: a string containing the new label for the node
- change_prio:
    - `item_id`: the node ID of the task to be edited
    - `prio`: an integer number between 0 and 3
- change_tags:
    - `item_id`: the node ID of the task to be edited
    - `tags`: a list of strings containing the tags that are to be added or removed
    - `action`: a string that specifies whether the tags should be added, removed, or cleared. The strings are defined by the following constants:
        - `panban.json_api.json_api_v1.PARAM_TAG_ADD`
        - `panban.json_api.json_api_v1.PARAM_TAG_REMOVE`
        - `panban.json_api.json_api_v1.PARAM_TAG_CLEAR`
- delete_nodes
    - `item_ids`: a list of the node IDs to be deleted
- load_all
    - no parameters
- move_nodes
    - `item_ids`: a list of the node IDs to be moved
    - `target_column`: the node ID of the column into which the nodes should be moved
- sync
    - no parameters

### Responses

The backend always returns a response on receiving a command.  A response is a JSON dictionary with the following parameters (in version 1):

- `version`: a string specifying the version of the response
- `status`: a string, either `panban.json_api.eternal.PortableResponse.STATUS_OK` or `panban.json_api.eternal.PortableResponse.STATUS_FAIL`
- `features`: a list of strings from `panban.json_api.json_api_vX.AVAILABLE_FEATURES`, through which a backend can influence the behavior of the frontend
- `data`: either null/None or a dictionary containing response data. Typically empty, except in response to the `load_all` command, which returns all tasks of the database.

## Supported Features by Backend

Not every backend supports every feature.

- `caldav`: All features are supported
- `markdown`: All features are supported
- `todotxt`: All features except priorities, tags, descriptions are supported
- `github`: Read-only

## List of Hidden Hacks

Some things are implemented in a hacky way and are not obvious:

- You can customize the order of tags in the tag list by assigning tag priorities through the special task "Tag Priorities" (see [HOWTO](HOWTO.md))
- You can highlight a task visually by assigning the special tag "important"
