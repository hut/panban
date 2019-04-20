# After stable version, never introduce a backwards-compatibility-breaking change here!

from panban.json_api import exceptions, get_api_version

def get_version(json):
    try:
        return json['version']
    except KeyError:
        raise exceptions.UnspecifiedJSONAPIVersion()


class PortableNode(object):
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


class PortableResponse(object):
    def __init__(self, version, status, data=None):
        self.status = status
        self.data = data
        self.version = version
        self.json_api = get_api_version(version)

    def to_json(self):
        return self.json_api.encode_response(self.status, self.data)

    @staticmethod
    def from_json(json_api, json_data):
        return json_api.decode_response(json_data)
