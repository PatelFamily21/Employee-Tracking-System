from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    A filter to access dictionary items by key in templates.
    """
    return dictionary.get(key, '—')