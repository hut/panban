import os
from panban.backends import caldav
from panban.backends import github
from panban.backends import markdown
from panban.backends import todotxt

ALL_BACKENDS = {
    'caldav': caldav,
    'github': github,
    'markdown': markdown,
    'todotxt': todotxt,
}

DEFAULT_BACKEND = 'markdown'

def get_backend_from_uri(uri):
    if '://' not in uri:
        uri = 'file://' + uri

    if uri.startswith('https://github.com'):
        return github
    if uri.startswith('file://'):
        if uri.endswith('.txt'):
            return todotxt

        path = uri[7:]
        if os.path.isdir(path):
            return caldav
    return markdown
