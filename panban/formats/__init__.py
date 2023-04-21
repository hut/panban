from panban.formats import caldav
from panban.formats import github
from panban.formats import markdown
from panban.formats import todotxt

ALL_BACKENDS = {
    'caldav': caldav,
    'github': github,
    'markdown': markdown,
    'todotxt': todotxt,
}

DEFAULT_BACKEND = 'markdown'
