from panban.json_api.exceptions import *
from panban.json_api import eternal
import sys
import json

VERSION = '1'

VALID_COMMANDS = [
    'getcolumndata',
    'moveitemstocolumn',
    'deleteitems',
]

class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'to_json'):
            if hasattr(obj, 'json_api'):
                return obj.to_json()
            else:
                this_api_module = sys.modules[__name__]
                return obj.to_json(this_api_module)
        else:
            return json.JSONEncoder.default(self, obj)


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
    if isinstance(json_data, str):
        json_data = json.loads(json_data)
    elif not isinstance(json_data, dict):
        raise TypeError("json_data needs to be dict or str, not %s."
                % type(json_data).__name__)

    node = eternal.PortableNode()
    for key in ('label', 'id', 'parent', 'pos', 'children'):
        if key in json_data and json_data[key]:
            setattr(node, key, json_data[key])
    return node

def encode_node(label, id, children, parent, attrs):
    response = {
        'label': label,
        'id': id,
        'children': children,
        'parent': parent,
        'attrs': attrs,
    }
    try:
        return json.dumps(response)
    except TypeError:
        raise Exception(response)


def encode_response(status, data=None):
    response = {
        'status': status,
        'version': VERSION,
    }
    if data is not None:
        response['data'] = data
    return json.dumps(response, cls=JSONEncoder)

def decode_response(json_data):
    if isinstance(json_data, str):
        json_data = json.loads(json_data)
    elif not isinstance(json_data, dict):
        raise TypeError("json_data needs to be dict or str, not %s."
                % type(json_data).__name__)

    status = json_data['status']
    version = json_data['version']
    data = json_data.get('data', None)
    response = eternal.PortableResponse(version, status, data)
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
