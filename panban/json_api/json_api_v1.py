from panban.json_api.exceptions import *
from panban.json_api import eternal

VALID_COMMANDS = [
    'getcolumndata',
    'moveitemstocolumn',
    'deleteitems',
]

def new_node(label=None, parent=None, pos=None, id=None):
    node = {
        'children': [],
        'label': label,
        'parent': parent,
        'pos': pos,
        'id': id,
    }
    return node

def fill_node_data_from_json(node, json_data):
    """
    >>> node = eternal.Node()
    >>> json_node = new_node(pos=3)
    >>> fill_node_data_from_json(node, json_node)
    >>> node.pos
    3
    """
    for key in ('label', 'id', 'parent', 'pos', 'children'):
        if key in json_data and json_data[key]:
            setattr(node, key, json_data[key])

def validate_request(json):
    if not isinstance(data, dict):
        raise NotADictError()
    if 'command' not in data:
        raise NoCommandError()

    if data['command'] not in VALID_COMMANDS:
        raise InvalidCommandError(data['command'])

def validate_response(json):
    pass

def delete_item_ids(json, item_ids):
    def recursively_delete(node, ids):
        children = node['children']
        for i in reversed(range(len(children))):
            child = children[i]
            if child['children']:
                recursively_delete(child, ids)
            if child['id'] in ids:
                del children[i]

    for node in json:
        recursively_delete(node, item_ids)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
