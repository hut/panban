# Never introduce a backwards-compatibility-breaking change here!

from panban.json_api import exceptions

def get_version(json):
    try:
        return json['version']
    except KeyError:
        raise exceptions.UnspecifiedJSONAPIVersion()


class Node(object):
    # A read-only representation of the data of a node

    def __init__(self):
        self.label = None
        self.id = None
        self.children = []
        self.parent = None
        self._raw_json = None

    def update_from_json(self, json_api, json_data):
        self._raw_json = json_data
        json_api.fill_node_data_from_json(node, json_data)

    @staticmethod
    def from_json(json_api, json_data):
        node = Node(json_api)
        node.update_from_json(json_api, json_data)
        return node
