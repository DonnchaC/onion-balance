# -*- coding: utf-8 -*-
# OnionBalance - Scheduler
# Copyright: 2015 Federico Ceratto
# Released under GPLv3, see COPYING file

from bisect import insort
from collections import deque
import logging
import time

log = logging.getLogger(__name__)

# next_run_time, interval, function, args
_jobs = deque()


def add_job(interval, function, *fargs, **fkwargs):
    """Add a job to be executed at intervals `interval` in seconds, starting
    from now.
    """
    job = (time.time(), interval, function, fargs, fkwargs)
    insort(_jobs, job)


def _run_job(job, override_run_time=False):
    """Run a job and put it back in the job queue"""
    planned_run_time, interval, function, fargs, fkwargs = job
    log.debug("Running %s" % function.__name__)
    function(*fargs, **fkwargs)

    t = time.time() if override_run_time else planned_run_time
    job = (t + interval, interval, function, fargs, fkwargs)
    insort(_jobs, job)


def run_all(delay_seconds=0):
    """Run all jobs at `delay_seconds` regardless of their schedule
    """
    todo = tuple(_jobs)
    _jobs.clear()
    for job in todo:
        _run_job(job, override_run_time=True)
        time.sleep(delay_seconds)


def run_forever(check_interval=1, catch_all_exceptions=False):
    """Run jobs forever.

    :param check_interval: polling interval
    :type check_interval: bool
    :param catch_all_exceptions: catch all exceptions excluding
    KeyboardInterrupt and log them as errors
    :type catch_all_exceptions: bool
    """
    while True:
        if not _jobs:
            return

        t = time.time()
        # sleep and poll until the earliest job is to be run
        while _jobs[0][0] <= t:
            # more than one job might need to be run right now
            job = _jobs.popleft()
            try:
                _run_job(job)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                if catch_all_exceptions:
                    log.error("Unexpected exception:",
                              exc_info=True)
                else:
                    raise e

        time.sleep(check_interval)
