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
        self.columns = []

    def reload(self):
        self.get_columns()

    def get_columns(self):
        response = self.handler.query({
            'command': 'getcolumndata',
            'source': self.source,
        })
        columns_data = response['result']

        result = []
        for column_data in columns_data:
            result.append(Column.from_json(column_data, self))
        self.columns = result
        return result

    def command(self, command_string, **parameters):
        query = {'command': command_string, 'source': self.source}
        query.update(parameters)
        return self.handler.query(query)


class Column(object):
    def __init__(self):
        pass

    def from_json(data, db):
        # data looks like ['title', [{...}, ...]]
        # with {...} being the data for of an entry

        column = Column()
        column.title = data[0]
        column.entries = []
        column.db = db
        for entry_data in data[1]:
            entry = Entry.from_json(entry_data, column)
            column.entries.append(entry)
        return column

    def __repr__(self):
        return '<Column "{title}" of [{entries}]>'.format(
                title=self.title,
                entries=", ".join(repr(entry) for entry in self.entries))

    def _raw_remove_entry(self, entry):
        if entry in self.entries:
            self.entries.remove(entry)


class Entry(object):
    def __init__(self):
        pass

    @staticmethod
    def from_json(data, column):
        entry = Entry()
        entry.label = data['label']
        entry.id = data['id']
        entry.column = column
        entry.db = column.db
        return entry

    def __repr__(self):
        return '<Entry "%s">' % self.label

    def delete(self):
        result = self.db.command('deleteitems', item_ids=[self.id])
        if result['result'] != 'ok':
            raise UserFacingException('Could not delete.  More info: %s' % repr(result))

        self.column._raw_remove_entry(self)
        return True
