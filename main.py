"""Provide a class that implements an http-service app, and, run the app.

This app may be run (A) locally, for dev and testing, or (B) on Google
Cloud Platform.

(A) To run locally, for dev and testing, start like
        % python main.py
    or in a venv, like
        % (source $VENVS/3.12+cherrypy/bin/activate && python main.py)

    Then,
        Run a python script to POST new data, like
            % (source $VENVS/3.12+cherrypy/bin/activate &&
                python tests/test_post.py http://localhost:8080)
        Browse to
            http://localhost:8080
            http://localhost:8080?action=walk

    (B) To run on GCP, start like
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
    import gcsfs
    from google.cloud import storage  # google-cloud-storage
else:
    storage = None
import yaml  # PyYAML, YAML parser and emitter for Python

# Local application/library specific imports.
# (none)


@cherrypy.expose
class MyWebService(object):

    def __init__(self, bucket=None, gcs_filesystem=None):
        self.bucket = bucket
        logging.info('%s: %r', 'self.bucket', self.bucket)
        self.gcs_filesystem = gcs_filesystem
        logging.info('%s: %r', 'self.gcs_filesystem', self.gcs_filesystem)


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
            assert not is_running_on_gcp()
            with open(file_name, 'w') as f:
                json.dump(data, f)


    def mylist(self):
        """Return a list of filenames."""
        if self.bucket:
            assert is_running_on_gcp()
            result = []

            for root, dirs, files in os.walk(os.getcwd()):
                for file in files:
                    result.append(os.path.join(root, file))

            result.append('')

            blobs = self.bucket.list_blobs()
            for blob in blobs:
                result.append(blob.name)

        else:
            assert not is_running_on_gcp()
            result = []
            for root, dirs, files in os.walk(os.getcwd()):
                for file in files:
                    result.append(os.path.join(root, file))
                for val in ['.git', 'tmp.gitignore']:
                    if val in dirs:
                        dirs.remove(val)

        logging.info('%s: %s', 'result', pprint.pformat(result))
        return result


    def mydump(self, flavor=None):
        """Return a list of records."""
        if self.bucket:
            assert is_running_on_gcp()
            result = []

            fieldnames = ['received', 'name', 'email', 'affiliation', 'platform']
            if flavor == 'csv':
                result.append(','.join(fieldnames))

            blobs = self.bucket.list_blobs()
            for blob in blobs:
                # result.append(blob.name)
                gcs_path = f'gs://{bucket.name}/{blob.name}'
                logging.info('%s: %r', 'gcs_path', gcs_path)
                with self.gcs_filesystem.open(gcs_path) as f:
                    record = json.load(f)

                if flavor == 'csv':
                    buf = []
                    for fieldname in fieldnames:
                        buf.append(record.pop(fieldname, ''))
                    result.append(','.join([*buf, f'{record}']))
                else:
                    result.append(f'{record}')

        else:
            assert not is_running_on_gcp()
            result = []

        logging.info('%s: %s', 'result', pprint.pformat(result))
        return result


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

        msg = f'Method {self.myname()} returning.'
        logging.info(msg)
        return msg

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

        # prepare a list of 'action' value(s)
        actions = kwargs.get('action', [])
        if isinstance(actions, str):
            actions = [actions]

        # result is a list of strings
        result = []

        for key, value in kwargs.items():
            result.append(f'{key}: {value!r}')
        result.extend(['', ''])

        # process the actions
        for index, action in enumerate(actions):
            if index > 0:
                result.append('')

            if action == 'list':
                result.extend(self.mylist())
            elif action == 'dump':
                result.extend(self.mydump())
            elif action == 'dumpcsv':
                result.extend(self.mydump(flavor='csv'))
            elif action == 'nop':
                result.append('nop')
            elif action == 'evil':
                result.append('evil')
            else:
                result.append('unrecognized action')

        msg = f'Method {self.myname()} returning.'
        logging.info(msg)
        return '\n'.join([msg, '', '', *result])


    def PUT(self, *args, **kwargs):
        msg = f'Method {self.myname()} is not implemented'
        logging.info(msg)
        return msg


    def DELETE(self, *args, **kwargs):
        msg = f'Method {self.myname()} is not implemented'
        logging.info(msg)
        return msg


conf = {
    '/': {
        'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        'tools.sessions.on': True,
        'tools.response_headers.on': True,
        'tools.response_headers.headers': [('Content-Type', 'text/plain')],
    }
}


if is_running_on_gcp():
    logging.info('Running on Google Cloud')

    with open('config-gcp.yaml', 'r') as f:
        config = yaml.safe_load(f)
    logging.info('%s: %r', 'config', config)

    client = storage.Client()
    bucket = client.get_bucket(config.get('bucket_name'))
    gcs_filesystem = gcsfs.GCSFileSystem(project=config.get('project_name'))

    # This adapted from search: cherrypy app wsgi main
    #   Mount the CherryPy application to get a WSGI callable
    #   1.  myapp = cherrypy.tree.mount(Root())
    #       You can then use this 'application' callable with any WSGI
    #       server.
    #       For example, if using Gunicorn:
    #       gunicorn -w 4 your_module:myapp

    myapp = cherrypy.tree.mount(
        MyWebService(bucket=bucket, gcs_filesystem=gcs_filesystem),
        '/', conf)
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
