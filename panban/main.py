from panban.frontends import ALL_FRONTENDS, DEFAULT_FRONTEND
from panban.backends import ALL_BACKENDS, DEFAULT_BACKEND
from panban.controller import DatabaseAbstraction

def main():
    args = parse_arguments()
    theme = args.theme if args.theme != '-' else None

    frontend_module = ALL_FRONTENDS[args.frontend]
    backend_module = ALL_BACKENDS[args.backend]

    backend = backend_module.Handler()
    controller = DatabaseAbstraction(backend, args.source[0])
    frontend = frontend_module.UI(controller,
            initial_tab=args.tab, debug=args.debug, theme=theme)
    frontend.main()

def parse_arguments():
    import argparse

    frontend_choices = ', '.join(s + ' (default)' if s == DEFAULT_FRONTEND
            else s for s in sorted(ALL_FRONTENDS))
    backend_choices = ', '.join(s + ' (default)' if s == DEFAULT_BACKEND
            else s for s in sorted(ALL_BACKENDS))

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-f', '--frontend', type=str, default='urwid',
            help='Which frontend? Choices: ' + frontend_choices)
    parser.add_argument('-b', '--backend', type=str, default='markdown',
            help='Which database type? Choices: ' + backend_choices)
    parser.add_argument('-T', '--theme', type=str, default='-', metavar='PATH',
            help='Load color theme from file, on top of default theme')
    parser.add_argument('--debug', action='store_true',
            help='Enable debugging features')
    parser.add_argument('-t', '--tab', type=str,
            help='Change the default starting tab')
    parser.add_argument('source', type=str, nargs=1, metavar='DATABASE_SOURCE')
    args = parser.parse_args()
    return args
