"""
events/pagination.py — Standard pagination for EventHub.

TRD Section 9:
  - Default page size: 20
  - Configurable query parameter: page_size (e.g. ?page_size=50)
  - Maximum page size: 100
"""

from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
