def main():
    parse_arguments()

def parse_arguments():
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-x', '--long', metavar='N', type=int, default=1, help='foo')
    parser.add_argument('-d', '--days', nargs='+', default=['a', 'b'], dest='days', type=lambda s: s + "day")
