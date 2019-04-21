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
    COLUMN_LABEL_TODO = 'Todo'
    COLUMN_LABEL_ACTIVE = 'Active'
    COLUMN_LABEL_DONE = 'Done'
    ACTIVE_CONTEXT = 'active'

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
        self.load_data(filename)
        return self.response(self.nodes_by_id)

    def cmd_moveitemstocolumn(self, query):
        filename = query.source
        self.load_data(filename)

        ids = query.arguments['item_ids']
        target_column_id = query.arguments['target_column']
        target_column = self.nodes_by_id[target_column_id]
        for node_id in ids:
            todo = self.todos_by_node_id[node_id]
            if target_column.label == self.COLUMN_LABEL_TODO:
                todo.completed = False
                todo.completion_date = None
                if self.ACTIVE_CONTEXT in todo.contexts:
                    todo.contexts.remove(self.ACTIVE_CONTEXT)
            elif target_column.label == self.COLUMN_LABEL_ACTIVE:
                todo.completed = False
                todo.completion_date = None
                if self.ACTIVE_CONTEXT not in todo.contexts:
                    todo.contexts.append(self.ACTIVE_CONTEXT)
            elif target_column.label == self.COLUMN_LABEL_DONE:
                todo.completed = True
                todo.completion_date = time.strftime('%Y-%m-%d')
            else:
                raise Exception('Invalid column')

        self.dump_data(filename)
        return self.response()

    def cmd_deleteitems(self, query):
        filename = query.source
        items_by_id, todos_by_node_id = self.load_data(filename)

        ids = query.arguments['item_ids']
        self.json_api.delete_node_ids(nodes, ids)

        self.dump_markdown(nodes, filename)
        return self.response()

    def load_data(self, filename):
        """
        >>> h = Handler(json_api='1')
        >>> h.load_data("test/todo.txt")
        >>> nodes = h.nodes_by_id
        >>> isinstance(nodes, dict)
        True
        >>> len(nodes)
        22
        >>> roots = [n for n in nodes.values() if not n.parent]
        >>> len(roots)  # 1 unfiltered root + 2 roots filtering by project
        3
        >>> root = roots[0]
        >>> columns = [n for n in nodes.values() if n.parent == root.id]
        >>> len(columns)
        3
        >>> [len(nodes[column].children) for column in root.children]  # Entries
        [3, 1, 2]
        """
        if not os.path.exists(filename):
            raise panban.api.SourceFileDoesNotExist(filename)

        with open(filename, 'r') as f:
            content = f.read()
        self.list_of_todos = todotxtio.from_string(content)

        nodes_by_id = {}
        todos_by_node_id = {}
        projects = {}
        column_labels = [
            self.COLUMN_LABEL_TODO,
            self.COLUMN_LABEL_ACTIVE,
            self.COLUMN_LABEL_DONE,
        ]

        def add_project(name, pos):
            project_node = self.make_node(
                "%s [%s]" % (filename, name), None, pos)
            nodes_by_id[project_node.id] = project_node
            projects[name] = project_node

            for colpos, column_name in enumerate(column_labels):
                column_node = self.make_node(column_name, project_node, colpos)
                nodes_by_id[column_node.id] = column_node
                project_node.children.append(column_node.id)

        project_names = set()
        for todo in self.list_of_todos:
            project_names |= set(todo.projects)
        project_names = list(sorted(project_names))
        add_project("<ALL>", 0)
        for pos, project_name in enumerate(project_names):
            add_project(project_name, pos + 1)

        for todo in self.list_of_todos:
            for project_name in ['<ALL>'] + todo.projects:
                project_node = projects[project_name]
                if todo.completed:
                    target_column_id = project_node.children[2]
                elif self.ACTIVE_CONTEXT in todo.contexts:
                    target_column_id = project_node.children[1]
                else:
                    target_column_id = project_node.children[0]
                target_column = nodes_by_id[target_column_id]

                pos = len(target_column.children)
                node = self.make_node(todo.text, target_column.id, pos)
                target_column.children.append(node.id)
                nodes_by_id[node.id] = node
                todos_by_node_id[node.id] = todo

        self.todos_by_node_id = todos_by_node_id
        self.nodes_by_id = nodes_by_id

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

    def dump_data(self, filename):
        todotxtio.to_file(filename, self.list_of_todos)

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
