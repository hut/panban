# After stable version, never introduce a backwards-compatibility-breaking change here!

from panban.json_api import exceptions, get_api_version

def get_version(json):
    try:
        return json['version']
    except KeyError:
        raise exceptions.UnspecifiedJSONAPIVersion()

def encode_command(version, command, source, arguments=None):
    cmd_dict = {
        'command': command,
        'source': source,
        'version': version,
    }
    if arguments is not None:
        cmd_dict['arguments'] = arguments
    return cmd_dict

def decode_command(json_data):
    if isinstance(json_data, str):
        json_data = json.loads(json_data)
    elif not isinstance(json_data, dict):
        raise TypeError("json_data needs to be dict or str, not %s."
                % type(json_data).__name__)

    status = json_data['command']
    version = json_data.get('version', None)
    source = json_data['source']
    arguments = json_data.get('arguments', None)
    command = PortableCommand(version, command, source, arguments)
    return command


class PortableNode(object):
    # A read-only representation of the data of a node

    def __init__(self):
        self.label = None
        self.id = None
        self.children = []
        self.parent = None
        self.attrs = {}
        self._raw_json = None

    def __repr__(self):
        return '<PortableNode "%s" children=[%s]>' % (
                self.label, ', '.join(self.children))

    @staticmethod
    def from_json(json_api, json_data):
        return json_api.decode_node(json_data)

    def to_json(self, json_api):
        return json_api.encode_node(
            label=self.label,
            id=self.id,
            children=self.children,
            parent=self.parent,
            attrs=self.attrs,
        )


class PortableResponse(object):
    STATUS_OK = 'ok'

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


class PortableCommand(object):
    """
    Note: The version of the command refers to the requested version of the
    data in the response, not the version of the command request itself.
    The command request is not versioned as of now.
    """
    def __init__(self, version, command, source, arguments=None):
        self.command = command
        self.arguments = arguments
        self.version = version
        self.source = source
        #self.json_api = get_api_version(version)

    def to_json(self):
        return encode_command(self.version, self.command, self.source, self.arguments)

    @staticmethod
    def from_json(json_api, json_data):
        return decode_command(json_data)
