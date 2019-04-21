from panban.json_api.exceptions import *
from panban.json_api import eternal
import sys
import json
import hashlib

VERSION = '1'

VALID_COMMANDS = [
    'getcolumndata',
    'moveitemstocolumn',
    'deleteitems',
]

VALID_FEATURES = [
    # The feature "autogenerate_node_ids" updates the IDs of nodes by applying
    # json_api.generate_node_id whenever a node changes, to solve the problem
    # that some databases have no IDs for their nodes, e.g. plain markdown or
    # org mode files.  In order to address the node, we construct an ID by
    # hashing its data, but when the data changes, we need to update that ID.
    # A better solution might be if the Backend sends a mapping of old IDs to
    # new IDs in the response to the manipulation request.
    'autogenerate_node_ids',
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


def generate_node_id(node, debug=False):
    """
    >>> node = decode_node(dict(parent="Todo", label="dry laundry", pos=12))
    >>> generate_node_id(node)
    '647c0d6d35c0090e34b1bc6229086cf8dfd2bd9b1ca177a19df154b5d0c1a6ff'
    >>> node = decode_node(dict(parent="Todo", label="dry laundry", pos=13))
    >>> generate_node_id(node)
    'd458052c5254ae93933b1a5e3e66646cb5f3c5c9560ce420b9699ae3f416469d'
    """
    keys = (
        node.parent,
        node.label,
        str(node.pos),
    )
    #if debug or node.label == 'clean dirty things':
        #raise Exception(repr(keys))
    concatenated = "\0".join(keys).encode('utf-8')
    return hashlib.sha256(concatenated).hexdigest()


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

def encode_node(label, id, children, parent, pos, attrs):
    response = {
        'label': label,
        'id': id,
        'children': children,
        'parent': parent,
        'pos': pos,
        'attrs': attrs,
    }
    try:
        return json.dumps(response)
    except TypeError:
        raise Exception(response)


def encode_response(status, data=None, features=None):
    response = {
        'status': status,
        'version': VERSION,
    }
    if features:
        response['features'] = features
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
    features = json_data.get('features', [])
    data = json_data.get('data', None)
    response = eternal.PortableResponse(version, status, features, data)
    return response

def validate_request(command):
    if not command.command:
        raise NoCommandError()

    if command.command not in VALID_COMMANDS:
        raise InvalidCommandError(command.command)

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

def delete_node_ids(nodes_by_id, node_ids):
    for node_id in node_ids:
        if node_id in nodes_by_id:
            del nodes_by_id[node_id]

    for node_id in node_ids:
        for node in nodes_by_id.values():
            while node_id in node.children:
                node.children.remove(node_id)

def move_node_ids_to_column(nodes_by_id, node_ids, target_column_id):
    target = nodes_by_id[target_column_id]
    for node_id in node_ids:
        node = nodes_by_id[node_id]
        if node.parent:
            parent = nodes_by_id[node.parent]
            while node_id in parent.children:
                parent.children.remove(node_id)
        target.children.append(node_id)
        node.parent = target_column_id


if __name__ == '__main__':
    import doctest
    doctest.testmod()
