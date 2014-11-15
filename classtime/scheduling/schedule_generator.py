
import multiprocessing

from angular_flask.logging import logging
logging = logging.getLogger(__name__) # pylint: disable=C0103

import classtime

import heapq
from .schedule import Schedule

CANDIDATE_POOL_SIZE = 120
"""Number of schedules to keep in consideration at any one time"""

WORKERS = 16
"""Maximum number of worker processes to spawn"""

WORKLOAD_SIZE = CANDIDATE_POOL_SIZE / WORKERS
"""Number of candidate schedules to give to each worker process"""

def find_schedules(schedule_params, num_requested):
    """
    :param AcademicCalendar cal: calendar to pull section data from
    :param dict schedule_params: parameters to build the schedule with.
        Check :ref:`api/generate-schedules <api-generate-schedules>`
        for available parameters.
    """
    if 'term' not in schedule_params:
        logging.error("Schedule generation call did not specify <term>")
    term = schedule_params.get('term', '')
    institution = schedule_params.get('institution', 'ualberta')
    cal = classtime.get_calendar(institution)

    if 'courses' not in schedule_params:
        logging.error("Schedule generation call did not specify <courses>")
    course_ids = schedule_params.get('courses', list())
    busy_times = schedule_params.get('busy-times', list())

    logging.info('Received schedule request')

    schedules = _generate_schedules(cal,
        term, course_ids, busy_times,
        num_requested)
    if len(schedules) == 0:
        logging.error('No schedules found for q={}'.format(
            schedule_params))
    else:
        logging.info('Returning {} schedules from request q={}'.format(
            len(schedules), schedule_params))
    return schedules

def _generate_schedules(cal, term, course_ids, busy_times, num_requested):
    """Generate a finite number of schedules

    :param int num_requested: maximum number of schedules to return.
        Upper limit is CANDIDATE_POOL_SIZE.
        Will only return valid schedules, even if that means returning
        less than the requested number.

    :returns: the best possible schedules, sorted by ScheduleScorer
        scoring functions
    :rtype: list of :ref:`schedule objects <api-schedule-object>`
    """
    def _log_scheduling_component(num, component, pace):
        logging.debug('({symbol}/{num}) Scheduling {name}'.format(
            symbol=Schedule.SYMBOLS[pace],
            num=num,
            name=' '.join(component[0].get('asString').split()[:-1])))

    components = cal.get_components(term, course_ids)
    components = sorted(components, key=len)

    candidates = [Schedule(busy_times=busy_times)]
    for pace, component in enumerate(components):
        _log_scheduling_component(len(components), component, pace)
        candidates = _add_component(candidates, component, pace)

    candidates = [candidate for candidate in candidates
                  if len(candidate.sections) == len(components)]
    logging.debug('Generated {} schedules'.format(len(candidates)))
    return sorted(candidates, reverse=True)[:num_requested]

def _add_component(candidates, component, pace):
    """
    Schedule generation algorithm
    1. Pick a schedule candidate from the list.
    2. Pick a section ("A2") for a component ("LAB") of a course ("CHEM")
      2b. If the section conflicts with the schedule, throw it out
      2c. Otherwise, add it to the schedule.
    3. Do 2 for all section options ("A3") for the component ("LAB").
    4. Do 3 for all components ("LAB") of a course ("CHEM")
    5. Do 4 for all schedule candidates
    6. Do battle royale with the schedules. Only keep the best.

    7. Add the next component using (1->6).
    8. Repeat until all courses are scheduled.
    """
    def _candidate_battle_royale(candidates, component, pace, heap_size, out_q):
        """Put the `heap_size` best candidates onto the `out_q`

        :param list candidates: candidate schedules
        :param list component: sections to consider. Exactly one is added to any
            given schedule.
        :param int pace: the number of components which should already have been
            added to a schedule. If a schedule has less than this, it can never
            be a complete schedule. Therefore, time should not be wasted on it.
        :param int heap_size: number of candidate schedules which should escape
            alive
        :param multiprocessing.Queue out_q: a multiprocessing Queue to put 
            results onto.

        :returns: the best schedules
        :rtype: list of schedules
        """
        for candidate in candidates[:]:
            if _is_hopeless(candidate, pace):
                continue
            for section in component:
                if candidate.has_dependency_conflict(section):
                    continue
                if candidate.conflicts(section):
                    continue
                _add_candidates(candidates,
                    candidate.clone().add_section(section),
                    heap_size)
        out_q.put(candidates)
        return

    out_q = multiprocessing.Queue()
    procs = list()
    for chunk in _chunks(candidates):
        proc = multiprocessing.Process(
            target=_candidate_battle_royale,
            args=(chunk, component, pace,
                  WORKLOAD_SIZE+1, out_q))
        procs.append(proc)
        proc.start()
    candidates = list()
    for _ in range(len(procs)):
        candidates.extend(out_q.get())
    candidates = candidates[:CANDIDATE_POOL_SIZE]
    for proc in procs:
        proc.join()
    return candidates

def _add_candidates(candidates, candidate, heap_size):
    discard = heapq.heapreplace(candidates, candidate)
    if len(candidates) < heap_size:
        heapq.heappush(candidates, discard)

def _is_hopeless(candidate, sections_chosen):
    return len(candidate.sections) < sections_chosen

# http://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks-in-python
def _chunks(full_list, chunk_size=None):
    """ Yield successive n-sized chunks from l.
    """
    if chunk_size is None:
        chunk_size = WORKLOAD_SIZE
    for i in xrange(0, len(full_list), chunk_size):
        yield full_list[i:i+chunk_size]
