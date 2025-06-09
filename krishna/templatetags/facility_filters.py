from django import template

register = template.Library()

@register.filter
def has_true_values(dictionary):
    return any(value for value in dictionary.values())