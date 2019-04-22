"""
This file provides database abstractions.

The task of objects here is to provide a fixed interface with operations that
manipulate the locally cached data representation, and at the same time,
synchronize the data on the server.
"""

import time
from panban import json_api
from panban.json_api import exceptions
from panban.api import UserFacingException
from panban.json_api.eternal import (
        PortableCommand, PortableResponse, PortableNode)

class DatabaseAbstraction(object):
    def __init__(self, backend_handler, source):
        self.handler = backend_handler
        self.source = source
        self.root_node_ids = []
        self.nodes_by_id = {}
        self.features = []
        self.json_api_version = None
        self.json_api = None
        self.last_modification = 0

    def reload(self):
        self.get_columns()

    def get_columns(self):
        response = self.command('load_all')
        if response.status != response.STATUS_OK:
            raise UserFacingException('Could not fetch columns.  More info: %s'
                    % repr(response))

        self.root_node_ids = []
        self.nodes_by_id = {}
        for node_id, node_json in response.data.items():
            pnode = PortableNode.from_json(self.json_api, node_json)
            node = Node.from_portable_node(pnode, self)
            if not node.parent:
                self.root_node_ids.append(node.id)
            self.nodes_by_id[node.id] = node

    def get_root_nodes(self):
        return [self.nodes_by_id[id] for id in self.root_node_ids]

    def command(self, command_string, **parameters):
        """
        Args:
            command_string: A command string as specified in
                json_api_XYZ.VALID_COMMANDS.
            parameters: Further parameters passed along with the command.
        Returns:
            A panban.json_api.eternal.PortableResponse object containing the
            response from the backend.  Its "version" attribute containst the
            JSON API version as negotiated with the backend.
        """
        query = PortableCommand(self.json_api_version, command_string,
                source=self.source, arguments=parameters)

        if self.json_api_version is None:
            json_api_version = json_api.HIGHEST_VERSION
        else:
            json_api_version = self.json_api_version

        # JSON API version negotiation
        query.version = json_api_version
        try:
            response = self.handler.query(query.to_json())
        except exceptions.JSONAPIVersionUnsupportedByServer as e:
            for v in reversed(json_api.AVAILABLE_VERSIONS):
                if v in server_versions:
                    json_api_version = v
                    break
            else:
                raise exceptions.NoCommonJSONAPIVersions(server_versions)
            query.version = json_api_version
            try:
                # Try again with negotiated JSON API version
                # TODO: No need to try again, just have the server send the
                # data with the highest version that it supports, and we can
                # check if we support it.
                response = self.handler.query(query.to_json())
            except exceptions.JSONAPIVersionUnsupportedByServer:
                # The backend lied about the supported versions!
                raise exceptions.JSONAPIVersionNegotiationFailed()

        if self.json_api_version is None:
            self.json_api_version = json_api_version
        self.json_api = json_api.get_api_version(self.json_api_version)

        response = PortableResponse.from_json(self.json_api, response)
        if response.features:
            self.features = response.features
        return response

    def _change_id_of_node(self, old_id, new_id):
        node = self.nodes_by_id[old_id]

        # Update ID of node
        node.id = new_id

        # Update "nodes_by_id"
        del self.nodes_by_id[old_id]
        self.nodes_by_id[new_id] = node

        # Update parent's children
        if node.parent:
            parent = self.nodes_by_id[node.parent]
            for i in range(len(parent.children)):
                if parent.children[i] == old_id:
                    parent.children[i] = new_id


class Node(object):
    """
    A node class providing methods to manipulate data on the backend.

    As you change the data of this node, it sends commands via the linked
    DatabaseAbstraction object to manipulate the respective Node on the backend
    as well, keeping both sides in sync.
    """

    @staticmethod
    def from_portable_node(portable_node, db):
        """
        >>> Node.from_portable_node(None, None)
        Traceback (most recent call last):
            ...
        ValueError: portable_node should be a PortableNode, not NoneType!
        >>> from panban.json_api import json_api_v1 as json_api
        >>> pnode = PortableNode.from_json(json_api, dict(label="test"))
        >>> node = Node.from_portable_node(pnode, None)
        Traceback (most recent call last):
            ...
        ValueError: portable_node has no id.
        >>> pnode = PortableNode.from_json(json_api, dict(id="XYZ",
        ...     label="test"))
        >>> node = Node.from_portable_node(pnode, None)
        >>> node.label
        'test'
        """
        if not isinstance(portable_node, PortableNode):
            raise ValueError("portable_node should be a PortableNode, not %s!"
                    % type(portable_node).__name__)

        if portable_node.id is None:
            raise ValueError("portable_node has no id.")

        node = Node()
        node.db = db
        node.label = portable_node.label
        node.id = portable_node.id
        node.children = portable_node.children
        node.parent = portable_node.parent
        node._raw_json = portable_node._raw_json

        # Not needed anymore, since children is now a list of IDs
        #for child_data in data['children']:
        #    child = Node.from_json(child_data, db)
        #    child.parent = node
        #    node.children.append(child)

        return node

    def __repr__(self):
        return '<Node "{0.label}">'.format(self)

    def getChildrenNodes(self):
        for node_id in self.children:
            if node_id in self.db.nodes_by_id:
                yield self.db.nodes_by_id[node_id]
            else:
                raise ValueError("Node with ID %s is child of %s but was not "
                    "found in database!" % (node_id, self.id))

    def delete(self):
        if self.parent is None:
            raise UserFacingException('Could not delete node, since it has no parent!')

        response = self.db.command('delete_nodes', item_ids=[self.id])
        if response.status != response.STATUS_OK:
            raise UserFacingException('Could not delete.  More info: %s' % repr(response))

        if self.id in self.db.nodes_by_id:
            del self.db.nodes_by_id[self.id]
        if self.parent in self.db.nodes_by_id:
            parent = self.db.nodes_by_id[self.parent]
            while self.id in parent.children:
                parent.children.remove(self.id)
        self.db.last_modification = time.time()

        return True

    def move_to_column(self, column_id):
        # TODO: handle failure
        response = self.db.command('move_nodes', item_ids=[self.id],
            target_column=column_id)

        parent = None
        if self.parent:
            parent = self.db.nodes_by_id[self.parent]
            while self.id in parent.children:
                parent.children.remove(self.id)
        target = self.db.nodes_by_id[column_id]
        target.children.append(self.id)
        self.parent = column_id
        self._update()

        if parent:
            for child in parent.children:
                self.db.nodes_by_id[child]._update()

        self.db.last_modification = time.time()
        return True

    def change_label(self, new_label):
        # TODO: handle failure
        response = self.db.command('change_label', item_id=self.id,
            new_label=new_label)
        self.label = new_label
        self._update()
        self.db.last_modification = time.time()  # TODO: doesn't refresh view?
        return True

    def _update(self):
        parent = self.db.nodes_by_id[self.parent]
        if self.id in parent.children:
            self.pos = parent.children.index(self.id)

        if 'autogenerate_node_ids' in self.db.features:
            old_id = self.id
            self.id = self.db.json_api.generate_node_id(self, debug=True)
            self.db._change_id_of_node(old_id, self.id)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
