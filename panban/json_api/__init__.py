from panban.json_api.exceptions import NoSuchJSONAPIVersionException

HIGHEST_VERSION = '1'

AVAILABLE_VERSIONS = [
    '1',
]

def get_api_version(value):
    if value == 'max':
        value = HIGHEST_VERSION

    if value == '1':
        from panban.json_api import json_api_v1
        return json_api_v1

    raise NoSuchJSONAPIVersionException(value)

def get_highest_api_version():
    return get_version('max')
