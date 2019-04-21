#!/usr/bin/python
import os.path
import sys
import re
import time
import hashlib
import argparse
import todotxtio
import panban.api
import panban.json_api.eternal
from panban.json_api.eternal import PortableResponse, PortableNode

class Handler(panban.api.Handler):
    def response(self, data=None, status=None):
        if status is None:
            status = PortableResponse.STATUS_OK

        response = PortableResponse(
            version=self.json_api.VERSION,
            status=status,
            data=data,
            features=['autogenerate_node_ids'],
        )
        return response

    def cmd_getcolumndata(self, query):
        filename = query.source
        items_by_id = self.load_data(filename)
        return self.response(items_by_id)

    def cmd_moveitemstocolumn(self, query):
        filename = query.source
        nodes = self.load_markdown(filename)

        ids = query.arguments['item_ids']
        target_column = query.arguments['target_column']
        self.json_api.move_node_ids_to_column(nodes, ids, target_column)

        self.dump_markdown(nodes, filename)
        return self.response()

    def cmd_deleteitems(self, query):
        filename = query.source
        nodes = self.load_markdown(filename)

        ids = query.arguments['item_ids']
        self.json_api.delete_node_ids(nodes, ids)

        self.dump_markdown(nodes, filename)
        return self.response()

    def load_data(self, filename):
        """
        >>> h = Handler(json_api='1')
        >>> nodes = h.load_data("test/todo.txt")
        >>> isinstance(nodes, dict)
        True
        >>> len(nodes)
        10
        >>> roots = [n for n in nodes.values() if not n.parent]
        >>> len(roots)
        1
        >>> root = roots[0]
        >>> columns = [n for n in nodes.values() if n.parent == root.id]
        >>> len(columns)
        3
        >>> [len(nodes[column].children) for column in root.children]  # Entries
        [3, 1, 2]
        """
        if not os.path.exists(filename):
            raise panban.api.SourceFileDoesNotExist(filename)

        nodes_by_id = {}

        root_node = self.make_node(filename, None, 0)
        nodes_by_id[root_node.id] = root_node

        col_todo = self.make_node('Todo', root_node, 0)
        nodes_by_id[col_todo.id] = col_todo

        col_active = self.make_node('Active', root_node, 1)
        nodes_by_id[col_active.id] = col_active

        col_done = self.make_node('Done', root_node, 2)
        nodes_by_id[col_done.id] = col_done

        root_node.children = [col_todo.id, col_active.id, col_done.id]

        with open(filename, 'r') as f:
            content = f.read()
        list_of_todos = todotxtio.from_string(content)
        for todo in list_of_todos:
            if todo.completed:
                target_column = col_done
            elif 'active' in todo.contexts:
                target_column = col_active
            else:
                target_column = col_todo

            pos = len(target_column.children)
            node = self.make_node(todo.text, target_column.id, pos)
            target_column.children.append(node.id)
            nodes_by_id[node.id] = node

        return nodes_by_id

    def make_node(self, label, parent, pos):
        if isinstance(parent, PortableNode):
            parent_id = parent.id
        elif isinstance(parent, str):
            parent_id = parent
        else:
            parent_id = ''
        pnode = PortableNode()
        pnode.label = label
        pnode.parent = parent_id
        pnode.pos = pos
        pnode.id = self.json_api.generate_node_id(pnode)
        return pnode

    def dump_markdown(self, nodes, filename):
        roots = [n for n in nodes.values() if n.is_root()]
        root = roots[0]
        columns = [nodes[id] for id in root.children]
        with open(filename, 'w') as f:
            last_title = columns[-1].label if columns else None
            for column in columns:
                f.write("# {title}\n\n".format(title=column.label))
                for entry_id in column.children:
                    entry = nodes[entry_id]
                    f.write("- {entry}\n".format(entry=entry.label))
                if column.children and not column.label == last_title:
                    f.write("\n")

    def handle(self, query):
        command = query.command
        if command == 'getcolumndata':
            response = self.cmd_getcolumndata(query)
        elif command == 'moveitemstocolumn':
            response = self.cmd_moveitemstocolumn(query)
        elif command == 'deleteitems':
            response = self.cmd_deleteitems(query)
        else:
            raise panban.api.InvalidCommandError(command)
        return response.to_json()


if __name__ == '__main__':
    if '--doctest' in sys.argv:
        import doctest
        doctest.testmod()
    else:
        handler = Handler()
        raise SystemExit(handler.main_with_error_handling(sys.stdin))