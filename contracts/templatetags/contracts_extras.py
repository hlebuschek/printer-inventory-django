from django import template
register = template.Library()

def _hex_to_rgb(h: str):
    h = (h or "").lstrip("#")
    if len(h) == 3:  # поддержим #abc
        h = "".join(ch*2 for ch in h)
    if len(h) != 6:
        return (127, 127, 127)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

@register.filter
def contrast(hex_color: str) -> str:
    """Возвращает #000 или #fff в зависимости от яркости фона."""
    r, g, b = _hex_to_rgb(hex_color)
    yiq = (r*299 + g*587 + b*114) / 1000
    return "#000" if yiq > 140 else "#fff"
