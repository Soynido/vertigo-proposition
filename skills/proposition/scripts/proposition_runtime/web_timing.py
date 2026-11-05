"""One complete run clock. Installation time and unknown counters stay separate."""
from datetime import datetime,timedelta,timezone


def utc_now():return datetime.now(timezone.utc)


def deadlines(run):
    start=datetime.fromisoformat(run['created_at'])
    if start.tzinfo is None:raise ValueError('Run creation time requires its timezone')
    return {'target_at':(start+timedelta(seconds=600)).isoformat(),
        'deadline_at':(start+timedelta(seconds=1200)).isoformat()}


def budget(run,*,now=None):
    start=datetime.fromisoformat(run['created_at']);end=now or utc_now()
    elapsed=(end-start).total_seconds()
    if elapsed<0:raise ValueError('Run clock precedes creation; do not reset the measured duration')
    return dict(deadlines(run),wall_seconds=round(elapsed,3),target_seconds=600,ceiling_seconds=1200,
        target_status='PASS' if elapsed<=600 else 'FAIL',may_continue=elapsed<1200,
        ceiling_remaining_seconds=round(max(0,1200-elapsed),3),tokens_used=None,
        scope='complete_wall_time_since_run_creation_not_installation_or_individual_token_cost')


def require_time(run):
    result=budget(run)
    if not result['may_continue']:
        raise ValueError('Web qualification ceiling exceeded (1200 seconds); retain the actual checkpoint')
    return result
