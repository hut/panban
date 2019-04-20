from panban.json_api.exceptions import *
from panban.json_api import eternal
import sys

VERSION = '1'

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

def decode_node(json_data):
    """
    >>> node = decode_node(dict(pos=3))
    >>> node.pos
    3
    """
    node = eternal.PortableNode()
    for key in ('label', 'id', 'parent', 'pos', 'children'):
        if key in json_data and json_data[key]:
            setattr(node, key, json_data[key])
    return node

def encode_node(*args, **kwargs):
    raise NotImplementedError()

def encode_response(status, data=None):
    response = {
        'status': status,
        'version': VERSION,
    }
    if data is not None:
        response['data'] = data
    return response

def decode_response(json_data):
    status = json_data['status']
    version = json_data['version']
    data = json_data.get('data', None)
    response = PortableResponse(version, status, data)
    return response

def validate_request(json):
    if not isinstance(json, dict):
        raise NotADictError()
    if 'command' not in json:
        raise NoCommandError()

    if json['command'] not in VALID_COMMANDS:
        raise InvalidCommandError(json['command'])

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
