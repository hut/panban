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
