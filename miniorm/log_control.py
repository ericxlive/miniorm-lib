# miniorm/log_control.py

"""
This module controls suppression of logs when nested domain objects
are loaded indirectly (e.g., via encapsulate_nested).

Usage:

from miniorm.log_control import log_suppressed, suppress_logs

with log_suppressed():
    # any log() calls here will be suppressed
    ...

# Outside of the context, logging resumes normally.
"""

from contextlib import contextmanager

# Private counter to track suppression depth
_log_suppression_depth = 0

def suppress_logs():
    """
    Returns True if we are currently inside a log-suppressed context.
    """
    return _log_suppression_depth > 0

@contextmanager
def log_suppressed():
    """
    Context manager to suppress log() output temporarily.

    Example:
        with log_suppressed():
            domain.encapsulate_nested()
    """
    global _log_suppression_depth
    _log_suppression_depth += 1
    try:
        yield
    finally:
        _log_suppression_depth -= 1