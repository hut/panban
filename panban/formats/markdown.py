#!/usr/bin/python
import os.path
import sys
import re
import time
import hashlib
import argparse
import json
try:
    import panban.api
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    import panban.api

class Handler(panban.api.Handler):
    def cmd_getcolumndata(self):
        filename = self.json_data['source']
        data, items_by_id = self.load_markdown(filename)
        return dict(status='ok', data=data)

    def cmd_moveitemstocolumn(self):
        filename = self.json_data['source']
        ids = self.json_data['item_ids']
        target_column = self.json_data['target_column']
        tags, items_by_id = self.load_markdown(filename)

        self._delete_item_ids_from_json(tags, ids)
        new_items = [items_by_id[item_id] for item_id in ids]
        success = False
        for tag in tags:
            for column in tag['children']:
                if column['id'] == target_column:
                    column['children'].extend(new_items)
                    success = True
                    break
            if success:
                break
        if not success:
            raise panban.api.UserFacingException(
                    "Column with the ID %s not found. %s" % (target_column))

        self.dump_markdown(tags, filename)
        return dict(status='ok')

    @staticmethod
    def _delete_item_ids_from_json(json, item_ids):
        def recursively_delete(node, ids):
            children = node['children']
            for i in reversed(range(len(children))):
                child = children[i]
                if child['children']:
                    recursively_delete(child, ids)
                if child['id'] in ids:
                    del children[i]

        for node in json:
            recursively_delete(node, item_ids)

    def cmd_deleteitems(self):
        filename = self.json_data['source']
        ids = self.json_data['item_ids']
        tags, items_by_id = self.load_markdown(filename)

        self._delete_item_ids_from_json(tags, ids)

        for item_id in ids:
            if item_id in items_by_id:
                del items_by_id[item_id]

        self.dump_markdown(tags, filename)
        return dict(status='ok')

    @staticmethod
    def generate_id(parent_id, label, pos):
        """
        >>> Handler.generate_id("Todo", "dry laundry", 12)
        '647c0d6d35c0090e34b1bc6229086cf8dfd2bd9b1ca177a19df154b5d0c1a6ff'
        >>> Handler.generate_id("Todo", "dry laundry", 13)
        'd458052c5254ae93933b1a5e3e66646cb5f3c5c9560ce420b9699ae3f416469d'
        """
        concatenated = "{}\0{}\0{}".format(parent_id, label, pos)
        concatenated = concatenated.encode('utf-8')
        return hashlib.sha256(concatenated).hexdigest()

    @staticmethod
    def dict(**kwargs):
        if not 'label' in kwargs:
            raise ValueError("Parameter to markdown Handler.dict() needs to "
                    "have the key 'label'!")
        elif not 'pos' in kwargs:
            raise ValueError("Parameter to markdown Handler.dict() needs to "
                    "have the key 'pos'!")
        result = panban.api.Handler.dict(**kwargs)
        parent_id = result['parent']['id'] if 'parent' in result else ''
        result['id'] = Handler.generate_id(
                parent_id, result['label'], result['pos'])
        return result

    def load_markdown(self, filename):
        """
        >>> h = Handler()
        >>> data, nodes_by_id = h.load_markdown("test/markdown.md")
        >>> isinstance(data, list)
        True
        >>> len(data)  # Tabs
        1
        >>> len(data[0]['children'])  # Columns
        3
        >>> [len(node['children']) for node in data[0]['children']]  # Entries
        [3, 1, 2]
        """
        if not os.path.exists(filename):
            raise panban.api.SourceFileDoesNotExist(filename)

        # TODO: use proper markdown parser
        tab = self.dict(label=filename, pos=0)
        tabs = [tab]
        current_column = None
        path = [filename, '', '']
        nodes_by_id = {}
        with open(filename, 'r') as f:
            for line in f:
                line = line.rstrip()
                if line.startswith('# '):
                    label = line[2:]
                    if label and label not in [col['label'] for col in tab['children']]:
                        pos = len(tab['children'])
                        current_column = self.dict(label=label, pos=pos)
                        tab['children'].append(current_column)
                elif line.startswith('- '):
                    label = line[2:]
                    if label and current_column:
                        pos = len(current_column['children'])
                        entry = self.dict(label=label, pos=pos)
                        nodes_by_id[entry['id']] = entry
                        current_column['children'].append(entry)
        return tabs, nodes_by_id

    def dump_markdown(self, data, filename):
        columns = data[0]['children']
        with open(filename, 'w') as f:
            last_title = columns[-1]['label'] if columns else None
            for column in columns:
                f.write("# {title}\n\n".format(title=column['label']))
                for entry in column['children']:
                    f.write("- {entry}\n".format(entry=entry['label']))
                if column['children'] and not column['label'] == last_title:
                    f.write("\n")

    def handle(self):
        if self.command == 'getcolumndata':
            return self.cmd_getcolumndata()
        if self.command == 'moveitemstocolumn':
            return self.cmd_moveitemstocolumn()
        if self.command == 'deleteitems':
            return self.cmd_deleteitems()
        raise panban.api.InvalidCommandError(self.command)


if __name__ == '__main__':
    if '--doctest' in sys.argv:
        import doctest
        doctest.testmod()
    else:
        handler = Handler()
        raise SystemExit(handler.main_with_error_handling(sys.stdin))
