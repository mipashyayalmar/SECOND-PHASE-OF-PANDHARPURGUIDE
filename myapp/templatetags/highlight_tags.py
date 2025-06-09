from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter
def highlight(text, search_query):
    if not search_query or not text:
        return text
    pattern = re.compile(re.escape(search_query), re.IGNORECASE)
    highlighted = pattern.sub(
        '<span style="background-color: yellow;">\\g<0></span>',
        str(text)
    )
    return mark_safe(highlighted)