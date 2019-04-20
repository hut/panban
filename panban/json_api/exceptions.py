class NoSuchJSONAPIVersionException(Exception):
    pass

class JSONAPIVersionUnsupportedByServer(Exception):
    def __init__(self, supported_versions):
        self.supported_versions = supported_versions
        super(JSONAPIVersionUnsupportedByServer, self).__init__()

class NoCommonJSONAPIVersions(Exception):
    pass

class JSONAPIVersionNegotiationFailed(Exception):
    pass

class UnspecifiedJSONAPIVersion(Exception):
    pass

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


class UserFacingException(Exception):
    pass
