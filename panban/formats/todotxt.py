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
from panban.json_api import exceptions
from panban.json_api.eternal import PortableResponse, PortableNode

def today():
    return time.strftime('%Y-%m-%d')

class Handler(panban.api.Handler):
    COLUMN_LABEL_TODO = 'Todo'
    COLUMN_LABEL_URGENT = 'High Prio'
    COLUMN_LABEL_ACTIVE = 'Active'
    COLUMN_LABEL_DONE = 'Done'
    ACTIVE_CONTEXT = 'active'
    PROJECT_NAME_ALL = '.*'
    PROJECT_NAME_NONE = '^$'

    @staticmethod
    def node_label_to_todo_label(node_label):
        return node_label.replace('\n', '<br>')

    @staticmethod
    def todo_label_to_node_label(todo_label):
        return todo_label.replace('<br>', '\n')

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

    def cmd_addnode(self, query):
        self.load_data(query.source)

        todo = todotxtio.Todo(
            text=self.node_label_to_todo_label(query.arguments['label']),
            creation_date=today()
        )

        # Infer metadata from column
        parent_id = query.arguments['target_column']
        parent = self.nodes_by_id[parent_id]
        if parent.label == self.COLUMN_LABEL_DONE:
            todo.completed = True
            todo.completion_date = today()
        elif parent.label == self.COLUMN_LABEL_ACTIVE:
            todo.contexts.append(self.ACTIVE_CONTEXT)
        elif parent.label == self.COLUMN_LABEL_URGENT:
            todo.priority = 'A'

        # Set the project
        project_node_id = parent.parent
        project_node = self.nodes_by_id[project_node_id]
        if project_node.label not in (
                self.PROJECT_NAME_ALL, self.PROJECT_NAME_NONE):
            todo.projects.append(project_node.label)

        self.list_of_todos.append(todo)

        self.dump_data(query.source)
        return self.response()

    def cmd_getcolumndata(self, query):
        filename = query.source
        self.load_data(filename)
        return self.response(self.nodes_by_id)

    def cmd_changelabel(self, query):
        self.load_data(query.source)

        todo = self.todos_by_node_id[query.arguments['item_id']]
        todo.text = self.node_label_to_todo_label(query.arguments['new_label'])

        self.dump_data(query.source)
        return self.response()

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
                todo.priority = None
                if self.ACTIVE_CONTEXT in todo.contexts:
                    todo.contexts.remove(self.ACTIVE_CONTEXT)
            elif target_column.label == self.COLUMN_LABEL_ACTIVE:
                todo.completed = False
                todo.completion_date = None
                if self.ACTIVE_CONTEXT not in todo.contexts:
                    todo.contexts.append(self.ACTIVE_CONTEXT)
            elif target_column.label == self.COLUMN_LABEL_URGENT:
                todo.completed = False
                todo.completion_date = None
                todo.priority = 'A'
                if self.ACTIVE_CONTEXT in todo.contexts:
                    todo.contexts.remove(self.ACTIVE_CONTEXT)
            elif target_column.label == self.COLUMN_LABEL_DONE:
                todo.completed = True
                todo.completion_date = time.strftime('%Y-%m-%d')
            else:
                raise Exception('Invalid column')

        self.dump_data(filename)
        return self.response()

    def cmd_deleteitems(self, query):
        self.load_data(query.source)

        ids = query.arguments['item_ids']
        to_be_deleted = [self.todos_by_node_id[node_id] for node_id in ids]
        for i in reversed(range(len(self.list_of_todos))):
            if self.list_of_todos[i] in to_be_deleted:
                del self.list_of_todos[i]

        self.dump_data(query.source)
        return self.response()

    def load_data(self, filename):
        """
        >>> h = Handler(json_api='1')
        >>> h.load_data("test/todo.txt")
        >>> nodes = h.nodes_by_id
        >>> isinstance(nodes, dict)
        True
        >>> len(nodes)
        25
        >>> roots = [n for n in nodes.values() if not n.parent]
        >>> len(roots)  # 1 unfiltered root + 2 roots filtering by project
        3
        >>> root = roots[0]
        >>> columns = [n for n in nodes.values() if n.parent == root.id]
        >>> len(columns)
        4
        >>> [len(nodes[column].children) for column in root.children]  # Entries
        [3, 0, 1, 2]
        """
        if not os.path.exists(filename):
            raise exceptions.SourceFileDoesNotExist(filename)

        with open(filename, 'r') as f:
            content = f.read()
        self.list_of_todos = todotxtio.from_string(content)

        nodes_by_id = {}
        todos_by_node_id = {}
        projects = {}
        column_labels = [
            self.COLUMN_LABEL_TODO,
            self.COLUMN_LABEL_URGENT,
            self.COLUMN_LABEL_ACTIVE,
            self.COLUMN_LABEL_DONE,
        ]

        def add_project(name, pos):
            project_node = self.make_node(name, None, pos)
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
        add_project(self.PROJECT_NAME_ALL, 0)
        for pos, project_name in enumerate(project_names):
            add_project(project_name, pos + 1)

        for todo in self.list_of_todos:
            if 't' in todo.tags:
                # Hide items that are below the date threshold
                today = time.strftime('%Y-%m-%d')
                if todo.tags['t'] > today:
                    continue

            for project_name in [self.PROJECT_NAME_ALL] + todo.projects:
                project_node = projects[project_name]
                if todo.completed:
                    target_column_id = project_node.children[3]
                elif self.ACTIVE_CONTEXT in todo.contexts:
                    target_column_id = project_node.children[2]
                elif todo.priority == 'A':
                    target_column_id = project_node.children[1]
                else:
                    target_column_id = project_node.children[0]
                target_column = nodes_by_id[target_column_id]

                pos = len(target_column.children)
                label = self.todo_label_to_node_label(todo.text)
                node = self.make_node(label, target_column.id, pos)
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
        if command == 'load_all':
            response = self.cmd_getcolumndata(query)
        elif command == 'move_nodes':
            response = self.cmd_moveitemstocolumn(query)
        elif command == 'delete_nodes':
            response = self.cmd_deleteitems(query)
        elif command == 'change_label':
            response = self.cmd_changelabel(query)
        elif command == 'add_node':
            response = self.cmd_addnode(query)
        else:
            raise exceptions.InvalidCommandError(command)
        return response.to_json()


if __name__ == '__main__':
    if '--doctest' in sys.argv:
        import doctest
        doctest.testmod()
    else:
        handler = Handler()
        raise SystemExit(handler.main_with_error_handling(sys.stdin))
