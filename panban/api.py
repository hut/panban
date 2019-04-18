import json
import sys

VALID_COMMANDS = [
    'getcolumndata',
    'moveitemstocolumn',
    'deleteitems',
]


class Handler(object):
    def __init__(self, integrated=False):
        self.integrated = integrated

    def _reset(self):
        self.command = None

    def handle(self):
        raise NotImplementedError("Please override this method!")

    @staticmethod
    def validate_data(data):
        if not isinstance(data, dict):
            raise NotADictError()
        if 'command' not in data:
            raise NoCommandError()

        command = data['command']

        if command not in VALID_COMMANDS:
            raise InvalidCommandError(command)

        return command

    def dump_js(self, arg=None, **kwargs):
        json.dump(arg or kwargs, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()

    def main(self, data_stream):
        self._reset()
        try:
            self.json_data = json.load(data_stream)
        except ValueError as e:
            raise InvalidJSONDataError()

        self.command = self.validate_data(self.json_data)
        result = self.handle()
        self.dump_js(result)

    def query(self, query_dict):
        self._reset()
        self.json_data = query_dict
        self.command = self.validate_data(self.json_data)
        return self.handle()

    def main_with_error_handling(self, data_stream):
        self._reset()
        try:
            error_code = self.main(data_stream)
        except HandlerException as e:
            if e.args:
                print(e.message.format(*e.args))
            else:
                print(e.message)
            return e.exit_code
        return 0

    @staticmethod
    def dict(**kwargs):
        result = {'children': []}
        result.update(kwargs)
        return result


class HandlerException(Exception):
    exit_code = 1
    message = 'Undefined error in file handling'


class InvalidJSONDataError(HandlerException):
    exit_code = 2
    message = 'Invalid JSON data from stdin'


class NoCommandError(HandlerException):
    exit_code = 3
    message = 'No command specified'


class NotADictError(HandlerException):
    exit_code = 4
    message = 'The JSON data is valid, but not a dictionary'


class InvalidCommandError(HandlerException):
    exit_code = 5
    message = 'Invalid command: `{}`'


class SourceFileDoesNotExist(HandlerException):
    exit_code = 6
    message = 'Source file does not exist: `{}`'
