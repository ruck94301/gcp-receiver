import ast
from datetime import datetime
import inspect
import json
import logging
import os
import pprint
import uuid
from zoneinfo import ZoneInfo


logging.basicConfig(level=logging.INFO)


import cherrypy


def is_running_on_gcp():
    """Return True if the application is running on Google Cloud Platform."""
    return 'GOOGLE_CLOUD_PROJECT' in os.environ


if is_running_on_gcp():
    from google.cloud import storage
    bucket_name = 'bucketname'

    def mywrite_jsonfile(file_name, data):
        # sanity check
        assert file_name.endswith('.json')

        client = storage.Client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(file_name)
        with blob.open(mode='w') as f:
            json.dump(data, f)

else:
    def mywrite_jsonfile(file_name, data):
        # sanity check
        assert file_name.endswith('.json')

        with open(file_name, 'w') as f:
            json.dump(data, f)


@cherrypy.expose
class MyWebService(object):

    def myname(self):
        """Return the caller's method name and the class name."""
        method_name = inspect.currentframe().f_back.f_code.co_name
        class_name = __class__.__name__
        return f'method {method_name} of class {class_name}'

    @cherrypy.tools.accept(media='text/plain')
    def GET(self):
        print(f'Entered {self.myname()}')
        return f'{self.myname()} is not implemented'

    def POST(self, *args, **kwargs):
        """Process an HTTP POST.

        The args from a POST from a logging.handlers.HTTPHandler object 
        are like:
            args: ()
            kwargs: {'args': '()',
             'created': '1751043153.494302',
             'exc_info': 'None',
             'exc_text': 'None',
             'filename': 'test_post.py',
             'funcName': '<module>',
             'levelname': 'INFO',
             'levelno': '20',
             'lineno': '102',
             'module': 'test_post',
             'msecs': '494.0',
             'msg': "{'name': 'James Stewart', 'rank': 'Brigadier General', 'serial number': 'O-433210'}",
             'name': 'Central Logger',
             'pathname': '/Users/john/Public/gcp-receiver/tmp.gitignore/test_post.py',
             'process': '88710',
             'processName': 'MainProcess',
             'relativeCreated': '12.23897933959961',
             'stack_info': 'None',
             'thread': '4656424448',
             'threadName': 'MainThread'}
        """

        print(f'Entered {self.myname()}')

        # print(f'args: {args!r}')
        # print(f'kwargs: {kwargs!r}')
        print(f'kwargs: {pprint.pformat(kwargs)}')

        now = datetime.now(ZoneInfo('US/Eastern')).strftime('%Y-%m-%dT%H%M%S%z')

        # for uniqueness with easy sorting, timestamp+uuid
        basename = f'{now}.{uuid.uuid1()}'

        # add a received timestamp to the msg dictionary
        data = ast.literal_eval(kwargs.get('msg'))
        data.update({'received': now})
        # logging.info('%s: %r', 'data', data)
        # logging.info('%s: %r', 'type(msg)', type(msg))

        mywrite_jsonfile(f'{basename}.json', data)

        return f'{self.myname()} returning'

    def PUT(self):
        print(f'Entered {self.myname()}')
        return f'{self.myname()} is not implemented'

    def DELETE(self):
        print(f'Entered {self.myname()}')
        return f'{self.myname()} is not implemented'


if __name__ == '__main__':
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'text/plain')],
        }
    }
    cherrypy.quickstart(MyWebService(), '/', conf)
