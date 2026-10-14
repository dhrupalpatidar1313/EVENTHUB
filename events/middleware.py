"""
events/middleware.py

RequestLoggingMiddleware — copied exactly from the brief (TRD §10, checklist item 9).

Logs: METHOD  PATH  →  STATUS  (duration ms)
"""

import logging
import time

logger = logging.getLogger("events")


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = (time.monotonic() - start) * 1000

        logger.info(
            "%s %s → %d (%.1f ms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response
