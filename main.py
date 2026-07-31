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
            http://localhost:8080?action=nop&action=walk&action=list

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

        The URL query params (after '?', and '&'-separated), like
            "dogsays=woof&catsays&action=walk&catsays=meow&action=trot"
        are passed into the GET method, like
            kwargs: {
                'action': ['walk', 'trot'],
                'catsays': ['', 'meow'],
                'dogsays': 'woof',
                }

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
implement a status query that reports memory footprint? data footprint?
implement a status query that reports buffer of logs from app
implement a response or handshake or heartbeat suitable for a registering
    with a watchdog service?
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
scalability:
as more small json-files are stored, the walking & reading becomes burdensome
better to store in some other db.

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
clipboard
    % gcloud projects list
    % PROJECT_ID=$(gcloud config get-value project)
    % printf "URL: %s\n" https://$PROJECT_ID.appspot.com

    Deploy service without prompting "Do you want to continue?".
        gcloud app deploy --quiet
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
"""

# Standard library imports.
import ast
import contextlib
from datetime import datetime
import inspect
import json
import logging
import os
from pathlib import Path
import pprint
import sys
import textwrap
import threading
import time
import uuid
from zoneinfo import ZoneInfo


# The logging.basicConfig() statement seems ineffective if executed
# after cherrypy is imported, indicating that the cherrypy import
# attaches one or more handlers to the root logger?
# logging.basicConfig(level=logging.INFO)
logging.basicConfig(
    level=logging.DEBUG,
    datefmt='%H:%M:%S',
    format='\t'.join([
        '%(asctime)s',
        '%(levelname)s',
        # '[%(name)s:%(module)s:%(lineno)d]',
        '[%(module)s:%(lineno)d]',
        '%(message)s',
        ])
    )


def is_running_on_gcp():
    """Return True if the application is running on Google Cloud Platform."""
    return 'GOOGLE_CLOUD_PROJECT' in os.environ


# Related third party imports.
import cherrypy  # Object-Oriented HTTP framework
if is_running_on_gcp():
    import gcsfs
    from google.cloud import storage  # google-cloud-storage
import yaml  # PyYAML, YAML parser and emitter for Python

# Local application/library specific imports.
from healthcheck import HealthCheck
from lockeddict import LockedDict

# Thread-safe storage for job/task status and results.
# For production, consider using Redis or a database.
jobs = LockedDict({})
# jobs is a LockedDict whose keys are uuids, and whose values are 
# ordinary dicts with keys 'status', 'time', and 'result'.


class MyWebService:
    """
    Why expose the individual methods instead of the class?
    No reason... FWIW,
        You can use cherrypy.expose to decorate individual methods that
        should be accessible via a URL, or you can decorate an entire
        class to automatically expose all its methods.

        Decorating a Method
        This is the most common use case. Decorating a method with
        @cherrypy.expose makes it a "page handler", meaning it can be
        mapped to a URL path by the default CherryPy dispatcher.
        Methods not decorated this way are considered internal and
        cannot be accessed via a URL.
    """

    def __init__(self, config={}, jobs=None):
        # Why pass in the jobs obj, instead of using module attribute?
        # Because the same jobs obj is needed in healthcheck, defined in
        # a different module, so using a module attribute would require
        # extra import coupling that jobs pass in does not.
        self.jobs = jobs

        if is_running_on_gcp():
            project_id = config.get('project_id', 'undefined')
            # project_host = f'{project_id}.appspot.com'
            self.gcs_filesystem = gcsfs.GCSFileSystem(project=project_id)

            bucket_host = f'{project_id}.appspot.com'
            self.bucket = storage.Client().get_bucket(bucket_host)

        else:  # running local, not on gcp
            data_subdir = config.get('local_datadir', 'tmp.data-local')
            self.local_projectdir = str(Path(__file__).resolve().parent)
            self.local_datadir = os.path.join(self.local_projectdir,
                data_subdir)

        self.enable_get_actions = config.get('enable_get_actions', False)

        logging.info('%s: %r', 'vars(self)', vars(self))
        logging.debug('%s:\n%s', 'vars(self)', pprint.pformat(vars(self)))


    @cherrypy.expose
    def index(self, **kwargs):
        method = cherrypy.request.method  # Access the method attribute
        if method == 'GET':
            logging.debug('self.GET(**kwargs) -- calling...')
            result = self.GET(**kwargs)
            logging.debug('self.GET(**kwargs) -- returned')
            return result
        elif method == 'POST':
            return self.POST(**kwargs)
        else:
            msg = f'Unsupported request method.  (method: {method})'
            logging.error(msg)
            return msg


    def myname(self):
        """Return the caller's method name and the class name."""
        method_name = inspect.currentframe().f_back.f_code.co_name
        class_name = __class__.__name__
        # return f'method {method_name} of class {class_name}'
        return f'{class_name}.{method_name}'


    def mywrite_jsonfile(self, file_name, data):
        # sanity check
        assert file_name.endswith('.json')

        if is_running_on_gcp():
            blob = self.bucket.blob(file_name)
            with blob.open(mode='w') as f:
                json.dump(data, f)

        else:  # running local, not on gcp
            with open(os.path.join(self.local_datadir, file_name), 'w') as f:
                json.dump(data, f)


    def mylist_projectfiles(self):
        """Return a sorted list of project file names."""
        result = []

        if is_running_on_gcp():
            for root, dirs, files in os.walk(os.getcwd()):
                for file in files:
                    result.append(os.path.join(root, file))

        else:  # running local, not on gcp
          with contextlib.chdir(self.local_projectdir):
            for root, dirs, files in os.walk('.'):
                for file in files:
                    # append root/file, except strip leading './'
                    result.append(os.path.join(root, file)[2:])

                # prevent descent into some special dirs
                exclude = ['.git', 'tmp.gitignore']
                for dir in dirs[:]:
                    # The items in dirs[:] list are unique, so no risk
                    # of double remove from dirs list.
                    if dir in exclude:
                        dirs.remove(dir)
                for dir in dirs[:]:
                    # The items in dirs[:] list are unique, so no risk
                    # of double remove from dirs list.
                    if Path(dir).resolve() == Path(self.local_datadir):
                        dirs.remove(dir)

        # rearrange and annotate
        result.sort()
        # replace result list with result from a list comprehension
        result = [f'{i}\t{s}' for i, s in enumerate(result, start=1)]
        result.insert(0, 'List of project file names:')

        return result


    def mylist_datafiles(self):
        """Return a list of data file names."""
        result = []

        if is_running_on_gcp():
            blobs = self.bucket.list_blobs()
            for blob in blobs:
                result.append(blob.name)

        else:  # running local, not on gcp
          with contextlib.chdir(self.local_datadir):
            for root, dirs, files in os.walk('.'):
                for file in files:
                    # append root/file, except strip leading './'
                    result.append(os.path.join(root, file)[2:])

        # rearrange and annotate
        result.sort()
        # replace result list with result from a list comprehension
        result = [f'{i}\t{s}' for i, s in enumerate(result, start=1)]
        result.insert(0, 'List of data file names:')

        return result


    def mylist(self):
        """Return a list of filenames."""
        result = self.mylist_projectfiles()
        result.append('')  # separator line between the two lists
        result.extend(self.mylist_datafiles())

        logging.info('%s:\n%s', 'result', pprint.pformat(result))
        return result


    def mydump(self, flavor=None):
        """Return a list of records (not sorted!)."""
        result = []

        if flavor == 'csv':
            fieldnames = [
                'received',
                'name', 'email', 'affiliation', 'platform']
            result.append(','.join(fieldnames))

        if is_running_on_gcp():
            blobs = self.bucket.list_blobs()
            for blob in blobs:
                # result.append(blob.name)
                gcs_path = f'gs://{self.bucket.name}/{blob.name}'
                logging.info('%s: %r', 'gcs_path', gcs_path)
                with self.gcs_filesystem.open(gcs_path) as f:
                    record = json.load(f)

                if flavor == 'csv':
                    # flatten the received timestamp into the data dictionary
                    if (set(record.keys()) == set(['received', 'data'])
                            and 'received' not in record['data'].keys()):
                        data = record.pop('data')
                        record.update(data)

                    buf = []
                    for fieldname in fieldnames:
                        buf.append(record.pop(fieldname, ''))
                    result.append(','.join([*buf, f'{record}']))
                else:
                    result.append(f'{record}')

        else:  # running local, not on gcp
          with contextlib.chdir(self.local_datadir):
            files = []
            for root, dirs, _files in os.walk('.'):
                files.extend(_files)

            for file in files:
                if not file.endswith('.json'):
                    continue

                with open(file, 'r') as f:
                    record = json.load(f)

                if flavor == 'csv':
                    # flatten the received timestamp into the data dictionary
                    if (set(record.keys()) == set(['received', 'data'])
                            and 'received' not in record['data'].keys()):
                        data = record.pop('data')
                        record.update(data)

                    buf = []
                    for fieldname in fieldnames:
                        buf.append(record.pop(fieldname, ''))
                    result.append(','.join([*buf, f'{record}']))
                else:
                    result.append(f'{record}')

        logging.info('%s:\n%s', 'result', pprint.pformat(result))
        return result


    def POST(self, **kwargs):
        """Process an HTTP POST.

        The args from a POST from a logging.handlers.HTTPHandler object
        are like:
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
        # logging.debug('%s: %r', 'kwargs', kwargs)
        logging.debug('%s:\n%s', 'kwargs',
            textwrap.indent(pprint.pformat(kwargs, indent=2, width=72), '  '))

        # Assign now, a timestamp string suitable for use in a filename.
        now = datetime.now(ZoneInfo('US/Eastern')).strftime('%Y-%m-%dT%H%M%S%z')

        # The ...
        #
        # The kwargs msg value dictionary looks like json, but it's python not
        # json.  Decode it with ast.literal_eval, not json.loads.
        data = ast.literal_eval(kwargs.get('msg'))

        # # add a received timestamp to the data dictionary
        # data.update({'received': now})
        # add a received timestamp, external to the original data dictionary
        data = {'received': now, 'data': data}

        # Assign a new output filename with timestamp+uuid, for easy
        # sorting and guaranteed uniqueness.
        basename = f'{now}.{uuid.uuid1()}'

        logging.info('%s: %r', 'data', data)

        self.mywrite_jsonfile(f'{basename}.json', data)

        # # intentionally slow processing for test purposes
        # time.sleep(8)

        msg = f'Method {self.myname()} returning.'
        logging.info(msg)
        return msg


    def GET(self, **kwargs):
        logging.info(f'Method {self.myname()} entered ...')
        logging.debug('%s: %r', 'kwargs', kwargs)

        # 1. Create a unique job ID
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            'status': 'processing', 
            'time': time.time(),
            'result': None,
            }

        # 2. Start the slow process in a background thread
        threading.Thread(
            target=self.slow_process,
            args=(job_id,),
            kwargs=kwargs,
            ).start()

        logging.info(f'Thread started...')

        # 3. Return 202 Accepted and the polling script
        cherrypy.response.status = 202

        msg = f'Method {self.myname()} returning'
        logging.info(msg)

        return f"""
        <html>
            <head>
                <style>
                    /* This ensures the status element uses a fixed-width font */
                    #status {{
                        font-family: 'Courier New', Courier, monospace;
                        white-space: pre-wrap; /* Optional: preserves spacing and line breaks */
                        background: #f4f4f4;
                        padding: 10px;
                        border-radius: 4px;
                    }}
                </style>
            </head>
            <body>
                <div id="status">Starting process...</div>
                <script>
                    // Capture the start time (in milliseconds)
                    const startTime = Date.now();

                    function getDuration() {{
                        const seconds = ((Date.now() - startTime) / 1000).toFixed(1);
                        return `[${{seconds}}s]`;
                    }}

                    async function pollStatus() {{
                        const response = await fetch('/status?id={job_id}');
                        const data = await response.json();
                        const duration = getDuration();

                        if (data.status === 'complete') {{
                            // document.getElementById('status').innerText = "Result: " + data.result;
                            document.getElementById('status').innerText = `${{duration}} Result: ${{data.result}}`;
                        }} else {{
                            // document.getElementById('status').innerText = "Still processing...";
                            document.getElementById('status').innerText = `${{duration}} Still processing...`;
                            setTimeout(pollStatus, 2000); // Poll every 2 seconds
                        }}
                    }}
                    pollStatus();
                </script>
            </body>
        </html>
        """


    # @cherrypy.tools.accept(media='text/plain')
    def slow_process(self, job_id, *args, **kwargs):
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
        logging.debug('%s: %r', 'args', args)
        # logging.debug('%s: %r', 'kwargs', kwargs)
        logging.debug('%s:\n%s', 'kwargs',
            textwrap.indent(pprint.pformat(kwargs, indent=2, width=72), '  '))

        # Use start_time to implement a lower-bound on task duration by
        # delaying the return of this function if necessary, to ensure
        # that "status polling" by the browser is demonstrated.
        min_duration = 4.0  # in seconds
        start_time = time.time()

        # prepare a list of 'action' value(s)
        actions = kwargs.get('action', [])
        if isinstance(actions, str):
            actions = [actions]

        # result is a list of strings
        result = []

        # append the query string's key-value pairs
        for key, value in kwargs.items():
            result.append(f'{key}: {value!r}')

        # extend with two blank lines of separation
        result.extend(['', ''])

        # process the actions
        if self.enable_get_actions == True:
            for index, action in enumerate(actions):
                if index > 0:
                    result.append('')

                result.append(f'DEBUG\tProcessing action {action!r}')
                if action == 'list':
                    result.extend(self.mylist())
                elif action == 'dump':
                    result.extend(self.mydump())
                elif action == 'dumpcsv':
                    result.extend(self.mydump(flavor='csv'))
                elif action == 'nop':
                    result.append(f'action {action!r}')
                else:
                    result.append(f'action {action!r} unrecognized')
        else:
            for index, action in enumerate(actions):
                result.append(f'action {action!r} disabled')

        msg = f'Method {self.myname()} returning.'
        logging.info(msg)
        # return '\n'.join([msg, '', '', *result])
        result = '\n'.join([msg, '', '', *result])

        # Sleep until minimum time is expired.
        elapsed = time.time() - start_time
        if elapsed < min_duration:
            sleep_val = min_duration - elapsed
            time.sleep(sleep_val)
            msg = f'Execution: {elapsed:.1f}s, Sleep: {sleep_val:.1f}s'
        else:
            msg = f'Execution: {elapsed:.1f}s'

        result = f'{result}\n\n{msg}'

        # Instead of returning the result,
        # update the job's status and result.
        self.jobs[job_id] = {
            'status': 'complete', 
            'time': time.time(),
            'result': result,
            }

        logging.debug('%s:\n%s', f'self.jobs[{job_id}]',
            textwrap.indent(pprint.pformat(
                self.jobs[job_id],
                indent=2, width=72), '  '))


    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self, id):
        # Endpoint for the browser to poll

        logging.info(f'Method {self.myname()} entered ...')

        with self.jobs.lock:  # lock the jobs object
            jobdata = self.jobs.get(id, {'status': 'not_found'})
            if jobdata['status'] == 'complete':
                del self.jobs[id]

        msg = f'Method {self.myname()} returning'
        logging.info(msg)

        return jobdata


conf = {
    '/': {
        # 'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        # 'tools.sessions.on': True,
        # 'tools.response_headers.on': True,
        # 'tools.response_headers.headers': [('Content-Type', 'text/plain')],
    }
}


if is_running_on_gcp():
    assert __name__ == 'main'

    logging.info('Running on Google Cloud')

    with open('main-gcp.yaml', 'r') as f:
        main_config = yaml.safe_load(f)
    logging.info('%s: %r', 'main_config', main_config)

    # This adapted from search: cherrypy app wsgi main
    #     Mount the CherryPy application to get a WSGI callable
    #         myapp = cherrypy.tree.mount(Root())
    #     You can then use this 'application' callable with any WSGI server.
    #     For example, if using Gunicorn:
    #         gunicorn -w 4 your_module:myapp

    # Mount the CherryPy application
    cherrypy.tree.mount(
        # root: An instance of a "controller class" (a collection of
        # page handler methods) which represents the root of the
        # application. This object's methods are exposed as pages in the
        # web application. This argument can also be an existing
        # cherrypy.Application instance, or None if a custom dispatcher
        # is used.
        MyWebService(config=main_config, jobs=jobs),

        # script_name: A string that defines the "mount point" or base
        # path of the application within the web server's URL hierarchy.
        # This should start with a forward slash (e.g., / for the root
        # of the site, or /api/stats for a specific path). There should
        # be no trailing slash.
        '/',

        # config (optional): A dictionary, a filename string, or an open
        # file object containing configuration entries for the
        # application. Application-specific configuration entries in the
        # dictionary are typically nested, using keys like '/' to denote
        # configuration settings that apply to the entire mounted
        # application (e.g., {'/' : {'tools.staticdir.on': True}}).
        conf,
        )

    # Mount the HealthCheck obj at /health.  This Health Check Endpoint
    # makes the app "watchable" by most watchdog systems.  The watchdog
    # software polls the app.  If "200 OK" is returned, the app is
    # alive.  Anything else (or a timeout) is abnormal.
    cherrypy.tree.mount(HealthCheck(jobs=jobs), '/health')

    # Get the WSGI callable.  In CherryPy, the cherrypy.tree object acts
    # as a registry for all mounted applications and itself serves as
    # the WSGI callable.
    myapp = cherrypy.tree

    # Use the following configuration for App Engine.
    # It's important to bind to 0.0.0.0 to listen on all interfaces
    # and to set the port to 8080 as required by App Engine.
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080,
        })

else:
    # running local, not on gcp
    assert __name__ == '__main__'

    logging.info('Not running on Google Cloud')

    with open('main-local.yaml', 'r') as f:
        main_config = yaml.safe_load(f)
    logging.info('%s: %r', 'main_config', main_config)

    # Mount the CherryPy application
    cherrypy.tree.mount(
        MyWebService(config=main_config, jobs=jobs),
        '/',
        conf,
        )

    # Mount the HealthCheck obj at /health.  This Health Check Endpoint
    # makes the app "watchable" by most watchdog systems.  The watchdog
    # software polls the app.  If "200 OK" is returned, the app is
    # alive.  Anything else (or a timeout) is abnormal.
    cherrypy.tree.mount(HealthCheck(jobs=jobs), '/health')

    # start()
    # Activate the engine in the background.  Initialize the internal
    # componeents and begin listening for requests.  Crucially, this
    # method is non-blocking by default -- the code following it will
    # execute immediately after the engine starts.
    cherrypy.engine.start()

    # block()
    # Pause the main execution thread of the Python script.  Tell the
    # program "don't exit or do anything else; just stay here and keep
    # the engine alive."  Without block(), the scrippt would reach the
    # end of its file and exit immediately after starting the engine,
    # causing the web server to shut down before it even processed a
    # single request.
    cherrypy.engine.block()
