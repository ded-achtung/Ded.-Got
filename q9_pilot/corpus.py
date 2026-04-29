"""
Corpora for the pilot.

Q9 chunks (c008-c011) are stubs reconstructed from the trace narrative — text
matches what the v3.x trace claimed the chunks contain.

Q4 chunks (c003, c004, c033) are real fragments from Fluent Python ch.1-2
(FrenchDeck), supplied by the user from the test-retest corpus archive.
"""

Q9_CHUNKS: dict[str, dict] = {
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


Q4_CHUNKS: dict[str, dict] = {
    "c003": {
        "doc": "fluent_ch1",
        "kind": "code",
        "text": (
            "A Pythonic Card Deck Example 1-1 is simple, but it demonstrates "
            "the power of implementing just two special methods, __getitem__ "
            "and __len__. Example 1-1. A deck as a sequence of playing cards\n"
            "\n"
            "import collections\n"
            "Card = collections.namedtuple('Card', ['rank', 'suit'])\n"
            "\n"
            "class FrenchDeck:\n"
            "    ranks = [str(n) for n in range(2, 11)] + list('JQKA')\n"
            "    suits = 'spades diamonds clubs hearts'.split()\n"
            "\n"
            "    def __init__(self):\n"
            "        self._cards = [Card(rank, suit) for suit in self.suits\n"
            "                                        for rank in self.ranks]\n"
            "    def __len__(self):\n"
            "        return len(self._cards)\n"
            "    def __getitem__(self, position):\n"
            "        return self._cards[position]\n"
        ),
    },
    "c004": {
        "doc": "fluent_ch1",
        "kind": "code",
        "text": (
            ">>> deck = FrenchDeck()\n"
            ">>> len(deck)\n"
            "52\n"
            "Reading specific cards from the deck — say, the first or the "
            "last — is easy, thanks to the __getitem__ method:\n"
            ">>> deck[0]\n"
            "Card(rank='2', suit='spades')\n"
        ),
    },
    "c033": {
        "doc": "fluent_ch2",
        "kind": "prose",
        "text": (
            "In Example 1-1 (Chapter 1), I used the following expression to "
            "initialize a card deck with a list made of 52 cards from all 13 "
            "ranks of each of the 4 suits, sorted by suit, then rank:\n"
            "        self._cards = [Card(rank, suit) for suit in self.suits\n"
            "                                        for rank in self.ranks]\n"
        ),
    },
}


# Backwards-compat alias for the original Q9 tests.
CHUNKS = Q9_CHUNKS
