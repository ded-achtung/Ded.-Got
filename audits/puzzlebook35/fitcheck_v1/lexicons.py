"""Hand-curated lexicons for fit_check v1.

All sets are sorted (or use frozenset) to keep determinism explicit.
Russian-first; English variants included for the few mixed-language
chunks (e.g., "by", "year", "author").

Scope: minimal — just enough vocabulary to validate the design.
Expansions belong in v2 along with broader test coverage.
"""
from __future__ import annotations

RU_STOP: frozenset[str] = frozenset({
    # function words
    "а", "и", "но", "или", "да", "же", "ли", "бы", "не", "ни",
    "в", "во", "на", "по", "с", "со", "у", "к", "ко", "за", "из",
    "от", "до", "об", "о", "под", "над", "при", "для", "через",
    "что", "как", "так", "это", "этот", "эта", "эти", "тот", "та", "те",
    "был", "была", "были", "есть", "будет", "будут", "быть",
    "если", "когда", "пока", "чтобы", "ради",
    "я", "ты", "он", "она", "оно", "мы", "вы", "они",
    "его", "её", "их", "мой", "твой", "наш", "ваш", "свой",
    "вам", "нам", "мне", "тебе", "себя", "себе",
    "только", "уже", "ещё", "также", "тоже", "очень", "более",
    "то", "там", "тут", "здесь", "тогда", "потом",
    "может", "можно", "нужно", "должна", "должен", "должны",
    "по-разному", "вообще",
})

RU_INTERROGATIVES: frozenset[str] = frozenset({
    "какой", "какая", "какое", "какие", "каких", "каким", "каким",
    "кто", "кого", "кому", "кем", "чём",
    "когда", "где", "куда", "откуда",
    "сколько", "почему", "зачем", "как",
    "что",  # also in RU_STOP — keep here for explicit interrogative drop
})

INTENT_TRIGGERS: dict[str, frozenset[str]] = {
    "when": frozenset({
        "год", "году", "года", "годом", "годах",
        "выпущ", "издан", "опубликован", "вышел", "вышла", "вышли",
        "издани", "редакци",
        "year", "date", "published", "released", "edition",
    }),
    "who": frozenset({
        "автор", "авторы", "авторов", "автору", "автором", "авторская", "авторски",
        "написал", "написала", "написали", "написан", "написана",
        "редактор", "редактора",
        "перевод", "переводчик",
        "by", "author", "wrote", "written",
    }),
    "why": frozenset({
        "потому", "поскольку", "так",  # "так как" handled at phrase level if needed
        "ради", "чтобы",
        "благодаря", "из-за", "вследствие",
        "because", "since",
        # discourse / reasoning markers
        "значит", "следовательно", "таким", "поэтому",
    }),
    "how": frozenset({
        "шаг", "шага", "шаги", "шагом", "шагов",
        "сначала", "затем", "далее", "после",
        "следует", "нужно", "требуется", "необходимо",
        "процедура", "способ", "метод",
        "step", "first", "then", "next", "follow",
    }),
}

OUT_OF_SCOPE_TERMS: frozenset[str] = frozenset({
    "решени", "решить", "ответ", "answer", "solution",
})

OUT_OF_SCOPE_SECTION_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("Решения",),
    ("Ответы",),
)

CARDINAL_WORDS: frozenset[str] = frozenset({
    "ноль", "один", "одна", "одно", "одни",
    "два", "две", "три", "четыре", "пять", "шесть", "семь",
    "восемь", "девять", "десять",
    "одиннадцать", "двенадцать", "тринадцать",
    "пятнадцать", "двадцать", "пятьдесят", "сто",
})


def stem(token: str) -> str:
    """Aggressive prefix-5 normalization. Not pymorphy3 — just enough to
    collapse common nominal/verbal/adjectival paradigms to a shared form
    for set-overlap purposes.

    Tokens of length ≤ 5 are returned as-is. Longer tokens are truncated
    to their first 5 characters. This loses precision (e.g., "выходить"
    and "выходной" both → "выход") but is good enough to make
    "внешних"/"внешние" share a stem, which exact suffix-stripping cannot
    guarantee without a dictionary.
    """
    if len(token) <= 5:
        return token
    return token[:5]
