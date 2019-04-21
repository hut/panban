from panban.formats import markdown
from panban.formats import todotxt

ALL_BACKENDS = {
    'markdown': markdown,
    'todotxt': todotxt,
}

DEFAULT_BACKEND = 'markdown'
