"""Provide HealthCheck for a health check endpoint.

(This module provide does) provide a HealthCheck class.  An instance
of HealthCheck gets mounted by cherrypy for a health check endpoint.

This module provides a class for creating an HTTP endpoint that responds
to healthcheck polling, and a function that scrubs stale job records.

Classes:
    HealthCheck:

Functions:
    delete_stale_job_records(jobs): Delete stale job records (both
        completed and not completed).

Example
    cherrypy.tree.mount(healthcheck.HealthCheck(jobs=jobs), '/health')

Background
In Python, implementing HTTP-based health observability is is best
handled by creating a lightweight health endpoint.  This allows a
watchdog (like Kubernetes, Monit, or PRTG) to poll the application.

As seen by the watchdog, this endpoint either
1.  returns status "200 OK",
2.  returns status 503, (not presently possible, because there is no
    logic that sets is_running to False)
3.  or, produces an error (e.g. unreachable, unresponsive, timeout, etc.)

Strengths
*   Separation of Concerns: The HealthCheck class is lightweight. Even
    if some worker thread logic hits an infinite loop or a database
    deadlock, the CherryPy server will still answer the Watchdog's HTTP
    request.
*   Standard Status Codes: Most commercial watchdogs (like Monit,
    Nagios, or Site24x7) default to checking for a 200 OK. By setting
    cherrypy.response.status = 503, their "Failure" logic is triggered
    automatically.

Weaknesses
*   As presently implementated, the health check endpoint is publicly
    accessible.
    To add an authentication requirement to observability, so that
    unapproved users can't probe the app's health, use a CherryPy "Tool"
    to ensure that the watchdog must provide a secret "X-API-Key" header
    to get a response.  (In CherryPy, "Tools" are middleware components
    that run before the page handler.)

------------------------------------------------------------------------
clipboard

Use a simple global "health state" to ensure the status reported
isn't just that the app is up, but that the logic is actually
functioning.
Instead of just returning a static "200 OK", the status should
report the app's internal "vital signs" (e.g., database connectivity
or background thread status).

State Validation: Because the worker_thread has to manually update
last_heartbeat, a "zombie" process (where the process is running but
doing nothing) will correctly report as unhealthy after 30 seconds.

------------------------------------------------------------------------
"""

# Standard library imports.
import logging
import os
import sys
import threading
import time

# Related third party imports.
import cherrypy
import psutil

# Local application/library specific imports
# None


logger = logging.getLogger(__name__)


def delete_stale_job_records(jobs):
    """Delete stale job records (both completed and not completed).

    Delete records of jobs that were completed, but whose records have
    become stale because they weren't removed normally upon retrieval
    of completed job results.

    Delete records of jobs that have not completed within the expected
    time limit, as they are presumed lost.

--------------------------------------------------------------------
clipboard

weren't removed normally because the polling ceased before
completion, that is, the browser stopped asking for status.
If the client browser abandons polling for status before the job is
completed, then the normal logic for deleting the job dict won't
run.
This can happen in normal, non-malicious usage, for example if the
user reloads the page.
This is easily demonstrated by hitting refresh repeatedly, which
starts new jobs instead of continuing to poll, waiting for the
existing to complete.

It's also possible to maliciously attempt to swamp the server.
That weakness remains.  Consider limiting the number of concurrent
jobs.

Delete old jobs that did not complete within the time limit.
But this does not try to kill the background thread.
Consider scenarios (a) permanently blocked thread, (b) temporarily
blocked thread that will later recover and try to update the job
dict, and (c) runaway thread consuming growing resources.


Implement scrubbing of stale jobs that were on completed
long ago?  Maybe the browser stopped asking for status.

Implement scrubbing of stale jobs that based on start time?
Maybe the job is runaway, so kill thread and remove job?

Implement scrubbing of stale jobs that based on last
heartbeat time?  Maybe the job is hung, so kill thread and
remove job?

2026-03-15: Actually, not entirely fixed...

If client hits index and a new job is started, but then
interrupts the javascript so that polling is abandoned and the
final result isn't retrieved, then the job record and result
will remain in the jobs dict until deleted by this housekeep().

So bad actors or ...

Demonstrate by hitting refresh repetitively to start new jobs
without allowing previous to complete.
To address this weakness, a garbage collector could be implemented
that
scrubs stale jobs.
Either a separate thread, or, make it an action on the front-end of
handling some other task.
If it's a separate thread, then it *could* be used for "pet the
dog", a freshness stamp of activity.
--------------------------------------------------------------------
    """
    timelimit_for_completed = 2 * 60  # in sec
    timelimit_for_notcompleted = 4 * 60  # in sec

    with jobs.lock:
        for job_id in list(jobs.keys()):
            job_record = jobs[job_id]
            job_staleness = time.time() - job_record['time']

            if (job_record['status'] == 'completed'
                    and job_staleness > timelimit_for_completed):
                # job completed, but wasn't picked up
                logger.warning('Deleting stale completed job record, '
                    f'jobs[{job_id!r}]')
                del jobs[job_id]
            elif (job_record['status'] != 'completed'
                    and job_staleness > timelimit_for_notcompleted):
                # job seems hung
                logger.warning('Deleting stale not-completed job record, '
                    f'jobs[{job_id!r}]')
                del jobs[job_id]


class HealthCheck:
    def __init__(self, jobs=None):
        self.jobs = jobs

        # self.last_heartbeat = time.time()
        self.is_running = True


    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """
        The GET /health endpoint.
        """

        delete_stale_job_records(self.jobs)

        # current_time = time.time()
        # # Define 'stale' as no background activity for 30 seconds
        # is_stale = (current_time - self.last_heartbeat) > 30
        #
        # if self.is_running and not is_stale:
        #     cherrypy.response.status = 200
        #     return {"status": "OK", "last_seen": int(self.last_heartbeat)}
        # else:
        #     # 503 Service Unavailable triggers the watchdog to restart the app
        #     cherrypy.response.status = 503
        #     return {"status": "UNHEALTHY", "reason": "Logic thread hung"}

        data = {}

        # collect jobs footprint data
        with self.jobs.lock:
            buf = {
                'num_jobs': len(self.jobs),
                # 'size_jobs': sum([sys.getsizeof(key)+sys.getsizeof(value)
                #     for key, value in self.jobs.items()]),
                # use a generator expression instead of a list comprehension
                'size_jobs': sum(sys.getsizeof(key)+sys.getsizeof(value)
                    for key, value in self.jobs.items()),
                }
        data.update(buf)

        # collect threads data
        data.update({
            'num_threads': threading.active_count()
            })

        # collect memory footprint data
        process = psutil.Process(os.getpid())
        process_mem_info = process.memory_info()
        # The rss (Resident Set Size) is the physical memory used in bytes
        rss = process_mem_info.rss

        # Get system virtual memory statistics
        mem = psutil.virtual_memory()

        # mem is a named tuple, providing several attributes:
        #     total: total physical memory in bytes
        #     available: the memory that can be given instantly to processes
        #     used: memory used in bytes
        #     free: memory not used at all (psutil recommends using
        #         'available' over 'free')

        buf = ', '.join([
            f'rss: {rss/1024**2:.2f} MiB',
            f'used: {mem.used/1024**3:.2f} GiB',
            f'available: {mem.available/1024**3:.2f} GiB',
            ])

        data.update({'memory': buf})

        if self.is_running:
            cherrypy.response.status = 200
            return {"status": "OK", 'data': f'{data}'}
        else:
            cherrypy.response.status = 503
            return {"status": "UNHEALTHY", "reason": "Logic thread hung"}
