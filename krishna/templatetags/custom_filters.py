# your_app/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter(name='subtract')
def subtract(value, arg):
    """Subtracts the arg from the value"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='multiply')
def multiply(value, arg):
    """Multiplies value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter(name='format_currency')
def format_currency(value):
    """Formats value as currency"""
    try:
        return f"₹{float(value):.2f}"
    except (ValueError, TypeError):
        return value