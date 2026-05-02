"""Minimal unit tests for fit_check v1 — canonical inputs only.

Run: python -m unittest test_fitcheck_v1.py
or:  python test_fitcheck_v1.py

These tests pin behavior on the three pilot audit rows (Q2 known-hit,
Q7 ambiguity, Q22 not_in_corpus) plus a few synthetic edge cases. If
any test fails after a fitcheck_v1 change, the fix or the design
needs review — do not paper over the test.
"""
from __future__ import annotations

import unittest

from fitcheck_v1 import fit_check, final_outcome


def chunk(cid: str, content: str, section_path=None) -> dict:
    return {
        "chunk_id": cid,
        "content": content,
        "section_path": section_path or ["test"],
    }


class TestQ2KnownHit(unittest.TestCase):
    """Q2: pygame + PythonTurtle in single chunk; alignment floor must match."""

    def test_q2_match_on_real_chunk(self):
        chunks = {
            "pb_raw_09": chunk(
                "pb_raw_09",
                "Используемые в книге внешние модули можно установить, "
                "выполнив следующие команды: python -m pip install pygame; "
                "python -m pip install PythonTurtle.",
                ["Приступая к работе", "Подготовка среды", "Внешние библиотеки Python"],
            ),
            "pb_raw_07": chunk(
                "pb_raw_07",
                "Процедура установки Python зависит от операционной системы. "
                "Если установщик спросит, хотите ли вы установить менеджер "
                "пакетов pip, соглашайтесь.",
                ["Приступая к работе", "Подготовка среды", "Установка Python"],
            ),
        }
        status, _, _ = fit_check(
            "what",
            "Какие два внешних Python-модуля устанавливаются через pip?",
            ["pb_raw_09", "pb_raw_07"], chunks, downstream_k=2,
        )
        self.assertEqual(status, "match")
        self.assertEqual(final_outcome(status, "what"), "hit")


class TestQ22NotInCorpus(unittest.TestCase):
    """Q22: corpus has no year tokens; must mismatch → fit_refuse."""

    def test_q22_refuses_on_ascii_codes(self):
        chunks = {
            "pb_raw_26": chunk(
                "pb_raw_26",
                "ASCII код 80 для 'P', 114 для 'r', 111 для 'o'. "
                "Никаких годов в этом задании.",
            ),
            "pb_raw_05": chunk(
                "pb_raw_05",
                "Введение. Книга состоит из двух частей: серьёзные и шуточные задачи.",
            ),
        }
        status, _, _ = fit_check(
            "when",
            "Когда была впервые выпущена книга «Programming Puzzles, Python Edition»?",
            ["pb_raw_26", "pb_raw_05"], chunks, downstream_k=2,
        )
        self.assertEqual(status, "mismatch")
        self.assertEqual(final_outcome(status, "when"), "fit_refuse")

    def test_q22_match_when_year_with_trigger(self):
        chunks = {
            "pb_raw_X": chunk(
                "pb_raw_X",
                "Книга была опубликована в 2023 году издательством DMK Press.",
            ),
        }
        status, _, _ = fit_check(
            "when", "Когда была выпущена книга?", ["pb_raw_X"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "match")

    def test_q22_mismatch_year_without_trigger(self):
        chunks = {
            "pb_raw_Y": chunk("pb_raw_Y", "Файл содержит 2024 строки кода и 1995 функций."),
        }
        status, _, _ = fit_check(
            "when", "Когда была выпущена книга?", ["pb_raw_Y"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "mismatch")


class TestQ7Ambiguity(unittest.TestCase):
    """Q7: pp.12-38 contain no authorship statement; must mismatch."""

    def test_q7_refuses_on_capitalized_noise(self):
        chunks = {
            "pb_raw_05": chunk(
                "pb_raw_05",
                "Введение. Задачи собранные в этой книге задуманы так, чтобы "
                "читатели любого уровня могли испытать на них свои силы. "
                "Python и Java упоминаются. Если возникнут вопросы, обращайтесь.",
            ),
        }
        status, _, _ = fit_check(
            "who",
            "Кто является автором задач в книге?",
            ["pb_raw_05"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "mismatch")
        self.assertEqual(final_outcome(status, "who"), "fit_refuse")

    def test_q7_match_when_explicit_author(self):
        chunks = {
            "pb_raw_X": chunk(
                "pb_raw_X",
                "Автор книги — Mat Whiteside, написал её в 2023 году.",
            ),
        }
        status, _, _ = fit_check(
            "who", "Кто автор книги?", ["pb_raw_X"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "match")


class TestHowMany(unittest.TestCase):
    def test_count_with_question_noun(self):
        chunks = {
            "pb_raw_05": chunk(
                "pb_raw_05",
                "В первой части 50 (+ несколько дополнительных) задач, трудность "
                "которых постепенно растёт.",
            ),
        }
        status, _, _ = fit_check(
            "how_many", "Сколько серьёзных задач в книге?",
            ["pb_raw_05"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "match")

    def test_digit_without_question_noun_mismatches(self):
        chunks = {
            "pb_raw_X": chunk(
                "pb_raw_X",
                "1. Первый пункт списка. 2. Второй пункт. 3. Третий пункт.",
            ),
        }
        status, _, _ = fit_check(
            "how_many", "Сколько параметров принимает функция?",
            ["pb_raw_X"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "mismatch")

    def test_cardinal_word_with_question_noun(self):
        chunks = {
            "pb_raw_15": chunk(
                "pb_raw_15",
                "Определите функцию filter_strings_containing_a, принимающую "
                "один параметр.",
            ),
        }
        status, _, _ = fit_check(
            "how_many",
            "Сколько параметров принимает функция filter_strings_containing_a?",
            ["pb_raw_15"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "match")


class TestOutOfScope(unittest.TestCase):
    def test_q26_решение_with_no_solution_section(self):
        chunks = {
            "pb_raw_19": chunk(
                "pb_raw_19", "Задание. Определите функцию get_longest_string.",
                ["Серьезные задачи", "Задача 5"],
            ),
        }
        status, expected, _ = fit_check(
            "how", "Какое предлагаемое решение задачи 5 (get_longest_string)?",
            ["pb_raw_19"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "mismatch")
        self.assertEqual(expected, "out_of_scope_within_topic")

    def test_question_about_решение_passes_when_solution_section_present(self):
        chunks = {
            "pb_raw_S": chunk(
                "pb_raw_S", "Решение задачи 5: используйте max(strs, key=len).",
                ["Решения", "Задача 5"],
            ),
        }
        status, _, _ = fit_check(
            "how", "Какое предлагаемое решение задачи 5?",
            ["pb_raw_S"], chunks, downstream_k=1,
        )
        self.assertNotEqual(status, "mismatch")


class TestAlignmentFloor(unittest.TestCase):
    def test_what_zero_overlap_mismatches(self):
        chunks = {
            "pb_raw_X": chunk(
                "pb_raw_X", "Совершенно неотносящийся текст про погоду и облака.",
            ),
        }
        status, _, _ = fit_check(
            "what", "Какие операционные системы поддерживаются?",
            ["pb_raw_X"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "mismatch")

    def test_what_high_overlap_matches(self):
        chunks = {
            "pb_raw_07": chunk(
                "pb_raw_07",
                "Процедура установки Python зависит от операционной системы: "
                "Windows, macOS или Linux.",
            ),
        }
        status, _, _ = fit_check(
            "what", "Какие операционные системы поддерживаются для установки Python?",
            ["pb_raw_07"], chunks, downstream_k=1,
        )
        self.assertEqual(status, "match")


if __name__ == "__main__":
    unittest.main()
