from routeguard.answers import (
    answers_equivalent,
    canonical_number,
    extract_answer,
    extract_choice,
    extract_code,
    extract_numeric,
    extract_text,
)
from routeguard.types import AnswerType
from routeguard.utils.text import normalize_digits, normalize_text, tokenize


def test_normalize_digits_persian_and_arabic_indic():
    assert normalize_digits("۱۲۳ و ٤٥٦") == "123 و 456"
    assert normalize_digits("۳٫۵") == "3.5"


def test_normalize_text_folds_arabic_variants_and_punctuation():
    # Arabic yeh/kaf and Persian yeh/keheh must compare equal after normalisation.
    assert normalize_text("كتابي") == normalize_text("کتابی")
    assert normalize_text("The  Answer!") == "answer"


def test_cyrillic_letters_with_diacritics_are_preserved():
    # й and ё are distinct letters in Russian/Kazakh and must not be folded to и / е.
    assert normalize_text("Йошкар-Ола ёлка") == "йошкар ола ёлка"
    assert normalize_text("café") == "cafe"


def test_zero_width_non_joiner_is_a_word_boundary():
    assert tokenize("می‌خواهم") == ["می", "خواهم"]


def test_canonical_number():
    assert canonical_number("1,234.50") == "1234.5"
    assert canonical_number("−7") == "-7"
    assert canonical_number("abc") is None


def test_extract_numeric_prefers_final_marker():
    text = "We have 3 boxes and 4 more.\nFinal answer: 12"
    assert extract_numeric(text) == "12"
    assert extract_numeric("First 3 then 4, so 7") == "7"
    assert extract_numeric("Ответ: ۱۹") == "19"
    assert extract_numeric("no digits here") is None


def test_extract_choice_marker_and_cyrillic_lookalike():
    assert extract_choice("Reasoning...\nFinal answer: (C)") == "C"
    # Model answered with Cyrillic "В" inside the answer segment.
    assert extract_choice("Ответ: В", ["a", "b", "c", "d"]) == "B"


def test_extract_choice_does_not_misread_russian_preposition():
    assert extract_choice("Он живёт в городе и работает в школе") is None


def test_extract_choice_by_option_text():
    assert extract_choice("Final answer: Mercury", ["Venus", "Mercury", "Mars", "Earth"]) == "B"


def test_extract_code_and_text():
    code = "Here:\n```python\ndef f(x):\n    return x\n```\nDone"
    assert extract_code(code) == "def f(x):\n    return x"
    assert extract_code("def g():\n    pass") == "def g():\n    pass"
    assert extract_text("blah\nFinal answer: Paris\n") == "Paris"
    assert extract_answer("Final answer: **Astana**", AnswerType.TEXT) == "Astana"


def test_answers_equivalent():
    assert answers_equivalent("19", "19.0", AnswerType.NUMERIC)
    assert answers_equivalent("b", "B", AnswerType.CHOICE)
    assert not answers_equivalent(None, "B", AnswerType.CHOICE)
    assert answers_equivalent("The Paris", "paris", AnswerType.TEXT)
