from panban.formats import markdown
from panban.formats import todotxt
from panban.formats import github

ALL_BACKENDS = {
    'markdown': markdown,
    'todotxt': todotxt,
    'github': github,
}

DEFAULT_BACKEND = 'markdown'
