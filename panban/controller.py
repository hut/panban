class DatabaseAbstraction(object):
    def __init__(self, backend_handler, source):
        self.handler = backend_handler
        self.source = source

    def get_columns(self):
        response = self.handler.query({
            'command': 'getcolumndata',
            'source': self.source,
        })
        columns_data = response['result']

        result = []
        for column_data in columns_data:
            result.append(Column.from_json(column_data))
        return result


class Column(object):
    def __init__(self):
        pass

    def from_json(data):
        # data looks like ['title', [{...}, ...]]
        # with {...} being the data for of an entry

        column = Column()
        column.title = data[0]
        column.entries = []
        for entry_data in data[1]:
            entry = Entry.from_json(entry_data, column)
            column.entries.append(entry)
        return column

    def __repr__(self):
        return '<Column "{title}" of [{entries}]>'.format(
                title=self.title,
                entries=", ".join(repr(entry) for entry in self.entries))



class Entry(object):
    def __init__(self):
        pass

    @staticmethod
    def from_json(data, column):
        entry = Entry()
        entry.label = data['label']
        entry.id = data['id']
        entry.column = column
        return entry

    def __repr__(self):
        return '<Entry "%s">' % self.label
