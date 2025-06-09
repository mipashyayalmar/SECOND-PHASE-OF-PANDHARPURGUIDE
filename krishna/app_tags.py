# templatetags/app_tags.py
from django import template

register = template.Library()

@register.filter
def percentage(value, total):
    try:
        # Handle empty strings or None explicitly
        if value == '' or value is None:
            value = 0
        if total == '' or total is None:
            total = 1  # Avoid division by zero
        total = float(total)
        value = float(value)
        return (value / total) * 100 if total != 0 else 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0