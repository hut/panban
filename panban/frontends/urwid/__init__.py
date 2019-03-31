import urwid

VIM_KEYS = {
    'h': 'cursor left',
    'l': 'cursor right',
    'j': 'cursor down',
    'k': 'cursor up',
    'd': 'cursor page down',
    'u': 'cursor page up',
    'g': 'cursor max left',
    'G': 'cursor max right',
}

class Frontend(object):
    def __init__(self, db):
        self.db = db

    def get_entries(self):
        return self.db.get_columns()

    def main(self):
        data = self.get_entries()
        print(data)
