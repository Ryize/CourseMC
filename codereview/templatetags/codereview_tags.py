from django import template

register = template.Library()


@register.filter(name='github')
def github(value):
    """
      Returns the value turned into a list.
    """
    return value.split('/')[4]
