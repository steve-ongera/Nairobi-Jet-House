from django import template

register = template.Library()

@register.filter
def replace_underscore(value):
    """Replace underscores with spaces and apply title case"""
    if value:
        return str(value).replace('_', ' ').title()
    return value

@register.filter
def replace_char(value, args):
    """Replace any character with another character
    Usage: {{ value|replace_char:"_| " }}
    This replaces underscores with spaces
    """
    if value and args:
        try:
            old_char, new_char = args.split('|')
            return str(value).replace(old_char, new_char)
        except ValueError:
            return value
    return value

@register.filter
def format_trip_type(value):
    """Specifically format trip type strings"""
    if value:
        return str(value).replace('_', ' ').title()
    return value

@register.filter
def clean_and_title(value):
    """Clean underscores and apply title case in one filter"""
    if value:
        return str(value).replace('_', ' ').replace('-', ' ').title()
    return value
