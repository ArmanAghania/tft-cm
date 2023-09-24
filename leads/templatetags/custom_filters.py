from django import template
from leads.models import Agent
from extensions.utils import jalali_converter

register = template.Library()

@register.filter
def zip_lists(a, b):
    return zip(a, b)


@register.filter(name='to_jalali')
def to_jalali(value):
    return jalali_converter(value)