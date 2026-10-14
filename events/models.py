"""
events/models.py  (M1 stub — fully filled in M2)

The models are defined here in stub form so migrations can run cleanly in M1.
All constraints, indexes, and fields are added in M2.
"""

from django.db import models


# Stubs — replaced with full implementations in M2
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Event(models.Model):
    title = models.CharField(max_length=200)

    def __str__(self):
        return self.title


class Reservation(models.Model):
    pass


class WaitlistEntry(models.Model):
    pass
