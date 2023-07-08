#!/usr/bin/python
import os.path
import sys
import re
import time
import hashlib
import argparse
import panban.api
import panban.json_api.eternal
from panban.json_api.eternal import PortableResponse, PortableNode, DEFAULT_PRIO
from panban.json_api import exceptions

TAG_PATTERN = r' \+([^ ]+)'
TAG_FORMAT = ' +{tag}'
TAG_FORMAT_LABEL = '{label}{tags}'
PRIO_PATTERN = r'^(\(|~~|\*\*)(.*)(\)|~~|\*\*)$'
PRIO_DECORATORS = {
    0: ('~~', '~~'),
    1: ('(', ')'),
    2: ('', ''),
    3: ('**', '**'),
}
PRIO_DECORATORS_REVERSE = dict((v, k) for k, v in PRIO_DECORATORS.items())

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

    def cmd_changedescription(self, query):
        filename = query.source
        nodes_by_id = self.load_markdown(filename)

        node = nodes_by_id[query.arguments['item_id']]

        old_value = node.description
        new_value = query.arguments['new_description']

        if new_value != old_value:
            node.description = new_value
            self.dump_markdown(nodes_by_id, filename)

        return self.response()

    def cmd_changeprio(self, query):
        filename = query.source
        nodes_by_id = self.load_markdown(filename)

        node = nodes_by_id[query.arguments['item_id']]
        node.prio = query.arguments['prio']

        self.dump_markdown(nodes_by_id, filename)
        return self.response()

    def cmd_changetags(self, query):
        filename = query.source
        nodes_by_id = self.load_markdown(filename)

        node = nodes_by_id[query.arguments['item_id']]

        old_value = list(node.tags)
        new_value = list(old_value)
        target_tags = query.arguments['tags']
        action = query.arguments['action']

        if action == self.json_api.PARAM_TAG_ADD:
            for tag in target_tags:
                if tag not in new_value:
                    new_value.append(tag)
        elif action == self.json_api.PARAM_TAG_REMOVE:
            for tag in target_tags:
                if tag in new_value:
                    new_value.remove(tag)
        elif action == self.json_api.PARAM_TAG_CLEAR:
            new_value = []

        if old_value != new_value:
            node.tags = new_value
            self.dump_markdown(nodes_by_id, filename)

        return self.response()

    def cmd_addnode(self, query):
        filename = query.source
        label = query.arguments['label']
        column_id = query.arguments['target_column']
        prio = query.arguments['prio']

        nodes_by_id = self.load_markdown(filename)

        parent = nodes_by_id[column_id]
        pos = len(parent.children)

        new_node = self.make_node(label, column_id, pos)

        if query.arguments['prio'] is not None:
            new_node.prio = query.arguments['prio']

        if query.arguments['tags']:
            new_node.tags = query.arguments['tags']

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
        return self.load_markdown_string(markdown_string, source_label=filename)

    def load_markdown_string(self, markdown_string, source_label=panban.DATA_FROM_STRING):
        # TODO: use proper markdown parser
        current_column = None
        parent = None
        entry = None
        nodes_by_id = {}
        root_node = self.make_node(source_label, None, 0)
        nodes_by_id[root_node.id] = root_node
        for line in markdown_string.split('\n'):
            line = line.rstrip()

            # Extract columns
            if line.startswith('# '):
                label = line[2:]
                if label:
                    pos = len(root_node.children)
                    parent = self.make_node(label, root_node, pos)
                    root_node.children.append(parent.id)
                    nodes_by_id[parent.id] = parent

            # Extract tasks
            elif line.startswith('- '):
                label = line[2:]

                # Extract priority
                priomatch = re.match(PRIO_PATTERN, label)
                if priomatch:
                    left, label, right = priomatch.groups()
                    prio = PRIO_DECORATORS_REVERSE[(left, right)]
                else:
                    prio = DEFAULT_PRIO

                if label and parent:
                    pos = len(parent.children)
                    label, tags = self.extract_tags(label)
                    entry = self.make_node(label, parent, pos, tags, prio)
                    parent.children.append(entry.id)
                    nodes_by_id[entry.id] = entry

            # Extract task descriptions
            elif line.startswith('    ') and entry is not None:
                text = line[4:]
                if entry.description is None:
                    entry.description = text
                else:
                    entry.description += "\n" + text

        return nodes_by_id

    def extract_tags(self, label):
        pattern = re.compile(TAG_PATTERN)
        tags = pattern.findall(label)
        label = pattern.sub('', label)  # Remove tags
        return label, tags

    def make_node(self, label, parent, pos, tags=(), prio=DEFAULT_PRIO):
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
        pnode.prio = prio
        if tags is None:
            pnode.tags = []
        else:
            pnode.tags = list(tags)
        pnode.id = self.json_api.generate_node_id(pnode)
        return pnode

    def dump_markdown(self, nodes, filename):
        roots = [n for n in nodes.values() if n.is_root()]
        root = roots[0]
        columns = [nodes[id] for id in root.children]
        content = []
        last_title = columns[-1].label if columns else None
        for column in columns:
            content.append("# {title}".format(title=column.label))
            content.append("")
            entries = [nodes[entry_id] for entry_id in list(column.children)]
            for entry in entries:
                content.append(self._format_line(entry))
                if entry.description is not None:
                    for line in entry.description.split("\n"):
                        content.append(f"    {line}")
            if entries and not column.label == last_title:
                content.append("")
        finalized_content = "\n".join(content)
        with open(filename, 'w') as f:
            f.write(finalized_content)

    def _format_line(self, entry):
        if entry.prio != DEFAULT_PRIO:
            left, right = PRIO_DECORATORS[entry.prio]
            label = f"{left}{entry.label}{right}"
        else:
            label = entry.label

        if entry.tags:
            tags = "".join(TAG_FORMAT.format(tag=tag) for tag in entry.tags)
            label = TAG_FORMAT_LABEL.format(label=label, tags=tags)

        return f"- {label}"

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
        elif command == 'change_prio':
            response = self.cmd_changeprio(query)
        elif command == 'change_tags':
            response = self.cmd_changetags(query)
        elif command == 'change_description':
            response = self.cmd_changedescription(query)
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
