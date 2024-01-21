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

JALALI_MONTH_NAMES = {
    1: 'Farvardin',
    2: 'Ordibehesht',
    3: 'Khordad',
    4: 'Tir',
    5: 'Mordad',
    6: 'Shahrivar',
    7: 'Mehr',
    8: 'Aban',
    9: 'Azar',
    10: 'Dey',
    11: 'Bahman',
    12: 'Esfand'
}

@register.filter(name='to_jalali_month')
def to_jalali_month(month_number):
    # Convert Gregorian month number to Jalali month name
    # Using the defined dictionary
    return JALALI_MONTH_NAMES.get(month_number, "Unknown Month")

@register.simple_tag
def generate_range(start, end):
    return range(start, end + 1)

@register.filter
def access(dictionary, key):
    return dictionary.get(key)