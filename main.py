"""Provide a class that implements an http-service app, and, run the app.

This app may be run locally, for dev and testing, or on Google Cloud 
Platform.

To run locally, for dev and testing, start like
    % python main.py
or in a venv, like
    % (source $VENVS/3.12+cherrypy/bin/activate && python main.py)
Then,
    Browse to 
        http://localhost:8080
        http://localhost:8080?cowsays=moo
    Run python to POST,
        % (source $VENVS/3.12+cherrypy/bin/activate && 
            python tests/test_post.py http://localhost:8080)
    Browse to
        http://localhost:8080?dogsays=woof&action=walk
    
To run on GCP, start like
    % gcloud init
    % gcloud app deploy
    % gcloud app versions list
    % gcloud app versions delete version [version ...]
    % gcloud app logs tail -s default
Then,
    Browse to 
        https://...appspot.com
        https://...appspot.com?cowsays=moo
    Run python to POST,
        % (source $VENVS/3.12+cherrypy/bin/activate && 
            python tests/test_post.py http://...appspot.com)
    Browse to
        https://... .appspot.com?dogsays=woof&action=walk

     name=value
     (name only produces value '')
"""

# Standard library imports.
import ast
from datetime import datetime
import inspect
import json
import logging
import os
import pprint
import sys
import textwrap
import uuid
from zoneinfo import ZoneInfo


logging.basicConfig(level=logging.INFO)


def is_running_on_gcp():
    """Return True if the application is running on Google Cloud Platform."""
    return 'GOOGLE_CLOUD_PROJECT' in os.environ


# Related third party imports.
import cherrypy  # Object-Oriented HTTP framework
if is_running_on_gcp():
    from google.cloud import storage  # google-cloud-storage
else:
    storage = None
import yaml  # PyYAML, YAML parser and emitter for Python

# Local application/library specific imports.
# (none)


# logging.info('%s: %r', 'storage', storage)
# import google.cloud
# from google.cloud import storage
# logging.info('%s: %r', 'storage', storage)
# sys.exit('intentional abend')
# 
# # bucket_name for google cloud storage
# bucket_name = 'bucketname'
# 
# with open('config-gcp.yaml', 'r') as f:
#     config = yaml.safe_load(f)
# bucket_name = config.get('bucket_name')
# logging.info('%s: %r', 'config', config)


@cherrypy.expose
class MyWebService(object):

    def __init__(self, bucket=None):
          self.bucket = bucket
          logging.info('%s: %r', 'self.bucket', self.bucket)


    def myname(self):
        """Return the caller's method name and the class name."""
        method_name = inspect.currentframe().f_back.f_code.co_name
        class_name = __class__.__name__
        # return f'method {method_name} of class {class_name}'
        return f'{class_name}.{method_name}'

    def mywrite_jsonfile(self, file_name, data):
        # sanity check
        assert file_name.endswith('.json')
    
        if self.bucket:
            assert is_running_on_gcp()
    
            blob = bucket.blob(file_name)
            with blob.open(mode='w') as f:
                json.dump(data, f)
    
        else:
            with open(file_name, 'w') as f:
                json.dump(data, f)
    

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
       
        logging.info(f'Method {self.myname()} entered ...')
        logging.debug('%s: %r', 'args', args)
        # logging.debug('%s: %r', 'kwargs', kwargs)
        logging.debug('%s: %s', 'kwargs', 
            textwrap.indent(pprint.pformat(kwargs, indent=2, width=72), '  '))

        # Assign now, a timestamp string suitable for use in a filename.
        now = datetime.now(ZoneInfo('US/Eastern')).strftime('%Y-%m-%dT%H%M%S%z')

        # The ...
        #
        # The kwargs msg value dictionary looks like json, but it's python not
        # json.  Decode it with ast.literal_eval, not json.loads.
        data = ast.literal_eval(kwargs.get('msg'))
        # add a received timestamp to the msg dictionary
        data.update({'received': now})

        # Assign a new output filename with timestamp+uuid, for easy
        # sorting and guaranteed uniqueness.
        basename = f'{now}.{uuid.uuid1()}'

        logging.info('%s: %r', 'data', data)

        self.mywrite_jsonfile(f'{basename}.json', data)

        response = f'Method {self.myname()} returning.'
        logging.info(response)
        return response

    @cherrypy.tools.accept(media='text/plain')
    def GET(self, *args, **kwargs):
        """Respond to an HTTP GET request.

        In an HTTP GET request, parameters are typically passed in the 
        URL as query parameters. 
        Query parameters are key-value pairs appended to the URL after a 
        question mark (?). 
        Here's how they are structured:
        1.  Start with a question mark: The query string begins with a ?.
        2.  Use key-value pairs: Each parameter consists of a key and a 
            value, separated by an equals sign (=).
        3.  Separate multiple parameters: If you need to include more 
            than one parameter, separate them with an ampersand (&). 

        ...?action=walk
            walk the current dir and report
        """

        logging.info(f'Method {self.myname()} entered ...')
        # logging.debug('%s: %r', 'args', args)
        # logging.debug('%s: %r', 'kwargs', kwargs)
        logging.debug('%s: %s', 'kwargs', 
            textwrap.indent(pprint.pformat(kwargs, indent=2, width=72), '  '))

        data = []
        if True:
            # with a query parameter, if enabled, get data
            data = [
                {"ID": 1, "Name": "Alice", "Age": 30},
                {"ID": 2, "Name": "Bob", "Age": 25},
                {"ID": 3, "Name": "Charlie", "Age": 35}
                ]

        if kwargs.get('action') == 'walk':
            if is_running_on_gcp():
                # storage_client = storage.Client()
                # bucket = storage_client.bucket(bucket_name)

                data = []
                for root, dirs, files in os.walk(os.getcwd()):
                    # data += f'{root}, {dirs}, {files}\n'
                    data.append({'root': root, 'dirs': dirs, 'files': files})
                    # for val in ['.git', 'tmp.gitignore']:
                    #     if val in dirs:
                    #         dirs.remove(val)

                data.append('- - - - - - - - ')
                blobs = self.bucket.list_blobs()
                # data = []
                for blob in blobs:
                    data.append(blob.name)

                logging.info('%s: %s', 'data', pprint.pformat(data))

            else:
                data = []
                for root, dirs, files in os.walk(os.getcwd()):
                    # data += f'{root}, {dirs}, {files}\n'
                    data.append({'root': root, 'dirs': dirs, 'files': files})
                    for val in ['.git', 'tmp.gitignore']:
                        if val in dirs:
                            dirs.remove(val)

        table = ''

        for key, value in kwargs.items():
            table += f'{key}: {value!r}\n'

        table += '\n'

        for row in data:
            table += f'{row}\n'

        response = f'Method {self.myname()} returning.'
        logging.info(response)
        return f'{response}\n\n{table}'
    
    def PUT(self, *args, **kwargs):
        response = f'Method {self.myname()} is not implemented'
        logging.info(response)
        return response
    
    def DELETE(self, *args, **kwargs):
        response = f'Method {self.myname()} is not implemented'
        logging.info(response)
        return response


conf = {
    '/': {
        'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        'tools.sessions.on': True,
        'tools.response_headers.on': True,
        'tools.response_headers.headers': [('Content-Type', 'text/plain')],
    }
}
# cherrypy.config.update({
#     'server.socket_host': '0.0.0.0',
#     'server.socket_port': 8080,
#     })


if is_running_on_gcp():
    logging.info('Running on Google Cloud')

    with open('config-gcp.yaml', 'r') as f:
        config = yaml.safe_load(f)
    logging.info('%s: %r', 'config', config)

    client = storage.Client()
    bucket = client.get_bucket(config.get('bucket_name'))

    # This adapted from search: cherrypy app wsgi main
    #   Mount the CherryPy application to get a WSGI callable
    #   1.  myapp = cherrypy.tree.mount(Root())
    #       You can then use this 'application' callable with any WSGI 
    #       server.
    #       For example, if using Gunicorn:
    #       gunicorn -w 4 your_module:myapp

    myapp = cherrypy.tree.mount(MyWebService(bucket=bucket), '/', conf)
    # myapp = cherrypy.tree
    # myapp = cherrypy.tree.mount(MyWebService(), '/', conf)
    
    # Use the following configuration for App Engine.
    # It's important to bind to 0.0.0.0 to listen on all interfaces
    # and to set the port to 8080 as required by App Engine.
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080,
        })

elif __name__ == '__main__':
    logging.info('Not running on Google Cloud')
    cherrypy.quickstart(MyWebService(), '/', conf)

else:
    logging.info('Not running on Google Cloud')
    logging.error('Unexpected... this module is being imported?')
