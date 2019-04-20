"""
This file provides database abstractions.

The task of objects here is to provide a fixed interface with operations that
manipulate the locally cached data representation, and at the same time,
synchronize the data on the server.
"""

from panban import json_api
from panban.json_api import exceptions
from panban.api import UserFacingException


class DatabaseAbstraction(object):
    def __init__(self, backend_handler, source):
        self.handler = backend_handler
        self.source = source
        self.tabs = []
        self.json_api_version = None
        self.json_api = None

    def reload(self):
        self.get_columns()

    def get_columns(self):
        # TODO: This should be a function of handler
        response = self.handler.query({
            'command': 'getcolumndata',
            'source': self.source,
        })
        if response['status'] != 'ok':
            raise UserFacingException('Could not fetch columns.  More info: %s'
                    % repr(response))
        self.tabs = tabs = []
        for tab_data in response['data']:
            tabs.append(Node.from_json(tab_data, self))
        return tabs

    def query(self, query_dict):
        if self.json_api_version is None:
            json_api_version = json_api.get_highest_api_version()
        else:
            json_api_version = self.json_api_version

        # JSON API version negotiation
        query_dict.update(dict(version=json_api_version))
        try:
            self.handler.query(query_dict)
        except exceptions.JSONAPIVersionUnsupportedByServer as e:
            for v in reversed(json_api.AVAILABLE_VERSIONS):
                if v in server_versions:
                    json_api_version = json_api.get_version(v)
                    break
            else:
                raise exceptions.NoCommonJSONAPIVersions(server_versions)
            query_dict.update(dict(version=json_api_version))
            try:
                # Try again with negotiated JSON API version
                self.handler.query(query_dict)
            except exceptions.JSONAPIVersionUnsupportedByServer:
                # The backend lied about the supported versions!
                raise exceptions.JSONAPIVersionNegotiationFailed()

        if self.json_api_version is None:
            self.json_api_version = json_api_version

    def command(self, command_string, **parameters):
        # TODO: remove this method for better separation of concerns?
        query = {'command': command_string, 'source': self.source}
        query.update(parameters)
        return self.handler.query(query)


class Node(object):
    @staticmethod
    def from_json(data, db):
        node = Node()
        node.label = data['label']
        if not 'id' in data:
            raise Exception(data)
        node.id = data['id']
        node.position = data['pos']
        node.children = []
        node.parent = data.get('parent', None)
        node.db = db
        node._raw_json = data

        for child_data in data['children']:
            child = Node.from_json(child_data, db)
            child.parent = node
            node.children.append(child)

        return node

    def __repr__(self):
        return '<Node "{0.label}" of [{entries}]>'.format(self,
                entries=", ".join(repr(entry) for entry in self.entries))

    def _raw_remove_child(self, child):
        if child in self.children:
            self.children.remove(child)

    def delete(self):
        if self.parent is None:
            raise UserFacingException('Could not delete node, since it has no parent!')

        result = self.db.command('deleteitems', item_ids=[self.id])
        if result['status'] != 'ok':
            raise UserFacingException('Could not delete.  More info: %s' % repr(result))

        self.parent._raw_remove_child(self)
        return True
