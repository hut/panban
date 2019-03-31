#!/usr/bin/python
import os.path
import sys
import re
import time
import hashlib
import argparse
import json
try:
    import canban.api
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    import canban.api

class Handler(canban.api.Handler):
    def cmd_getcolumndata(self):
        filename = self.json_data['source']
        columns, items = self.load_markdown(filename)
        self.dump_js(result=columns)

    def cmd_moveitemstocolumn(self):
        filename = self.json_data['source']
        ids = self.json_data['item_ids']
        target_column = self.json_data['target_column']
        columns, items_by_id = self.load_markdown(filename)

        objects = []
        for title, items in columns:
            for i in reversed(range(len(items))):
                item = items[i]
                if item['id'] in ids:
                    del items[i]
        new_items = [items_by_id[item_id] for item_id in ids]

    @staticmethod
    def generate_id(title, label, pos):
        """
        >>> Handler.generate_id("Todo", "dry laundry", 12)
        '647c0d6d35c0090e34b1bc6229086cf8dfd2bd9b1ca177a19df154b5d0c1a6ff'
        >>> Handler.generate_id("Todo", "dry laundry", 13)
        'd458052c5254ae93933b1a5e3e66646cb5f3c5c9560ce420b9699ae3f416469d'
        """
        concatenated = "{}\0{}\0{}".format(title, label, pos)
        return hashlib.sha256(concatenated).hexdigest()

    def load_markdown(self, filename):
        if not os.path.exists(filename):
            raise canban.api.SourceFileDoesNotExist(filename)

        # TODO: use proper markdown parser
        columns = []
        items = {}
        with open(filename, 'r') as f:
            for line in f:
                line = line.rstrip()
                if line.startswith('# '):
                    title = line[2:]
                    if title and title not in [col[0] for col in columns]:
                        columns.append([title, []])
                elif line.startswith('- '):
                    label = line[2:]
                    if label and columns:
                        title = columns[-1][0]
                        pos = len(columns[-1][1])
                        obj = {
                            'label': label,
                            'id': self.generate_id(title, label, pos),
                        }
                        items[obj['id']] = obj
                        columns[-1][1].append(obj)
        return columns, items

    def dump_markdown(self, data, filename):
        with open(filename, 'w') as f:
            last_title = data[-1][0] if data else None
            for title, list_items in data:
                f.write("# {title}\n\n".format(title=title))
                for item in list_items:
                    f.write("- {item}\n".format(item=item))
                if list_items and not title == last_title:
                    f.write("\n")

    def handle(self):
        if self.command == 'getcolumndata':
            self.cmd_getcolumndata()

if __name__ == '__main__':
    if '--doctest' in sys.argv:
        import doctest
        doctest.testmod()
    else:
        handler = Handler()
        raise SystemExit(handler.main_with_error_handling(sys.stdin))
