"""
events/admin.py  (M1 stub)
"""

from django.contrib import admin
from .models import Category, Event, Reservation, WaitlistEntry

admin.site.register(Category)
admin.site.register(Event)
admin.site.register(Reservation)
admin.site.register(WaitlistEntry)
