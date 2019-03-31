import json
import sys

VALID_COMMANDS = [
    'getcolumndata',
    'moveitemstocolumn',
]


class Handler(object):
    def __init__(self):
        pass

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
        try:
            self.json_data = json.load(data_stream)
        except ValueError as e:
            raise InvalidJSONDataError()

        self.command = self.validate_data(self.json_data)
        self.handle()

    def main_with_error_handling(self, data_stream):
        try:
            error_code = self.main(data_stream)
        except HandlerException as e:
            if e.args:
                print(e.message.format(*e.args))
            else:
                print(e.message)
            return e.exit_code
        return 0


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
