from panban.formats import github
from panban.formats import markdown
from panban.formats import todotxt
from panban.formats import vtodo

ALL_BACKENDS = {
    'markdown': markdown,
    'todotxt': todotxt,
    'github': github,
    'vtodo': vtodo,
}

DEFAULT_BACKEND = 'markdown'
