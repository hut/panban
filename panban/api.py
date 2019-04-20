import json
import sys
import panban.json_api.eternal
from panban.json_api.exceptions import HandlerException
from panban.json_api.eternal import PortableCommand
from panban import json_api


class UserFacingException(Exception):
    pass


class Handler(object):
    def __init__(self, integrated=False):
        self.integrated = integrated

    def handle(self, query):
        raise NotImplementedError("Please override this method!")

    def dump_js(self, arg=None, **kwargs):
        json.dump(arg or kwargs, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()

    def main(self, data_stream):
        try:
            json_data = json.load(data_stream)
        except ValueError as e:
            raise InvalidJSONDataError()

        self.dump_js(self.query(json_data))

    def query(self, query):
        if isinstance(query, PortableCommand):
            query = query.to_json()
        elif isinstance(query, dict):
            pass
        else:
            raise ValueError("Query should be dict or PortableCommand")
        version = json_api.eternal.get_version(query)
        self.json_api = json_api.get_api_version(version)
        self.json_api.validate_request(query)
        response = self.handle(query)
        self.json_api.validate_response(response)
        return response

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

    @staticmethod
    def dict(**kwargs):
        result = {'children': []}
        result.update(kwargs)
        return result
