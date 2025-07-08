from django import template

register = template.Library()

@register.filter
def ACTIONS(value):
    return value.upper()  # Example logic