"""
Stub corpus for Q9 pilot. Chunks reconstructed from the trace narrative.
Not a faithful quote of Fluent Python — text matches what the trace claimed
the chunks contain, so the pilot exercises the same disambiguation surface.
"""

CHUNKS: dict[str, dict] = {
    "c008": {
        "doc": "fluent_ch12",
        "kind": "prose",
        "text": (
            "The Vector class behaves as a sequence of components. "
            "It supports iteration, slicing, and equality comparison."
        ),
    },
    "c009": {
        "doc": "fluent_ch12",
        "kind": "prose",
        "text": (
            "In this chapter we will see the special methods "
            "__repr__, __abs__, __add__, and __mul__ at work."
        ),
    },
    "c010_canonical": {
        "doc": "fluent_ch12",
        "kind": "prose",
        "text": (
            "Example 1-2 shows the Vector class. "
            "We implemented five special methods in addition to "
            "the familiar __init__."
        ),
    },
    "c010_code": {
        "doc": "fluent_ch12",
        "kind": "code",
        "text": (
            "class Vector:\n"
            "    def __init__(self, x=0, y=0):\n"
            "        self.x = x\n"
            "        self.y = y\n"
            "    def __repr__(self):\n"
            "        return f'Vector({self.x!r}, {self.y!r})'\n"
            "    def __abs__(self):\n"
            "        return math.hypot(self.x, self.y)\n"
            "    def __bool__(self):\n"
            "        return bool(abs(self))\n"
            "    def __add__(self, other):\n"
            "        return Vector(self.x + other.x, self.y + other.y)\n"
            "    def __mul__(self, scalar):\n"
            "        return Vector(self.x * scalar, self.y * scalar)\n"
        ),
    },
    "c011": {
        "doc": "fluent_ch12",
        "kind": "prose",
        "text": (
            "By implementing dunder methods, user-defined types can behave "
            "like built-in types and benefit from the Python data model."
        ),
    },
}
