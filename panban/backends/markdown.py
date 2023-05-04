#!/usr/bin/python
import os.path
import sys
import re
import time
import hashlib
import argparse
import panban.api
import panban.json_api.eternal
from panban.json_api.eternal import PortableResponse, PortableNode
from panban.json_api import exceptions

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
        items_by_id = self.load_markdown(filename)
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

    def cmd_changelabel(self, query):
        filename = query.source
        nodes_by_id = self.load_markdown(filename)

        node = nodes_by_id[query.arguments['item_id']]
        node.label = query.arguments['new_label']

        self.dump_markdown(nodes_by_id, filename)
        return self.response()

    def cmd_addnode(self, query):
        filename = query.source
        label = query.arguments['label']
        column_id = query.arguments['target_column']

        nodes_by_id = self.load_markdown(filename)

        parent = nodes_by_id[column_id]
        pos = len(parent.children)

        new_node = self.make_node(label, column_id, pos)
        parent.children.append(new_node.id)
        nodes_by_id[new_node.id] = new_node

        self.dump_markdown(nodes_by_id, filename)
        return self.response()

    def load_markdown(self, filename):
        """
        >>> h = Handler(json_api='1')
        >>> nodes = h.load_markdown("demos/markdown/markdown.md")
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
            raise exceptions.SourceFileDoesNotExist(filename)

        with open(filename, 'r') as f:
            markdown_string = f.read()
        return self.load_markdown_string(markdown_string)

    def load_markdown_string(self, markdown_string):
        # TODO: use proper markdown parser
        current_column = None
        parent = None
        nodes_by_id = {}
        root_node = self.make_node("All Tasks", None, 0)
        nodes_by_id[root_node.id] = root_node
        for line in markdown_string.split('\n'):
            line = line.rstrip()
            if line.startswith('# '):
                label = line[2:]
                if label:
                    pos = len(root_node.children)
                    parent = self.make_node(label, root_node, pos)
                    root_node.children.append(parent.id)
                    nodes_by_id[parent.id] = parent
            elif line.startswith('- '):
                label = line[2:]
                if label and parent:
                    pos = len(parent.children)
                    entry = self.make_node(label, parent, pos)
                    parent.children.append(entry.id)
                    nodes_by_id[entry.id] = entry
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
