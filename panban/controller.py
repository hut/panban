"""
This file provides database abstractions.

The task of objects here is to provide a fixed interface with operations that
manipulate the locally cached data representation, and at the same time,
synchronize the data on the server.
"""


class UserFacingException(Exception):
    pass


class DatabaseAbstraction(object):
    def __init__(self, backend_handler, source):
        self.handler = backend_handler
        self.source = source
        self.tabs = []

    def reload(self):
        self.get_columns()

    def get_columns(self):
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

    def command(self, command_string, **parameters):
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
