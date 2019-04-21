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
        """
        Args:
            query: a dictionary with the command query, as created by
                PortableCommand.to_json()
        Returns:
            A dict containing the response from the backend, as created by
            PortableResponse.to_json().  The version of the json api is as
            specified by the "version" parameter in the query dictionary.
        Raises:
            ValueError: If the query is not a dictionary
        """
        if not isinstance(query, dict):
            raise ValueError("Query should be dict")
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
        # TODO: This should be obsolete, no?
        result = {'children': []}
        result.update(kwargs)
        return result
