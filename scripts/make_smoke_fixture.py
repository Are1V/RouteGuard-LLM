"""Generate the smoke-test fixture ``benchmarks/samples/smoke.jsonl``.

These items exist **only to test the software** (CI, the simulated demo). They are
templated arithmetic problems, simple facts, and tiny coding tasks with
deterministic answers, written by the RouteGuard authors in English, Kazakh,
Russian, and Persian. They are *not* a benchmark: they are too easy, too small,
and the non-English templates have not been reviewed by native speakers.
Never report results on them. Released under CC0-1.0.

The ``difficulty`` field is a hand-assigned latent value that only the
simulated backend reads.

Usage: python scripts/make_smoke_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "benchmarks" / "samples" / "smoke.jsonl"
NOTE = "software-test fixture; not a benchmark; do not report results"
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

ARITHMETIC = {
    "add": {
        "en": "What is {a} plus {b}?",
        "ru": "Сколько будет {a} плюс {b}?",
        "kk": "{a} мен {b} сандарының қосындысы нешеге тең?",
        "fa": "حاصل جمع {a} و {b} چند است؟",
    },
    "mul": {
        "en": "What is {a} multiplied by {b}?",
        "ru": "Сколько будет {a} умножить на {b}?",
        "kk": "{a} санын {b} санына көбейткенде неше шығады?",
        "fa": "حاصل ضرب {a} در {b} چند است؟",
    },
    "word": {
        "en": "A shop had {a} apples and sold {b} of them. How many apples are left?",
        "ru": "В магазине было {a} яблок, из них продали {b}. Сколько яблок осталось?",
        "kk": "Дүкенде {a} алма болды, оның {b} алмасы сатылды. Неше алма қалды?",
        "fa": "یک مغازه {a} سیب داشت و {b} سیب فروخت. چند سیب باقی ماند؟",
    },
}
PAIRS = [(12, 7), (48, 25), (135, 89), (17, 23)]
BASE_DIFFICULTY = {"add": 0.12, "mul": 0.42, "word": 0.55}

FACTS = [
    {
        "id": "planet",
        "q": {
            "en": "Which planet is closest to the Sun?",
            "ru": "Какая планета ближе всего к Солнцу?",
            "kk": "Күнге ең жақын планета қайсы?",
            "fa": "کدام سیاره به خورشید نزدیک‌تر است؟",
        },
        "choices": {
            "en": ["Venus", "Mercury", "Mars", "Earth"],
            "ru": ["Венера", "Меркурий", "Марс", "Земля"],
            "kk": ["Шолпан", "Меркурий", "Марс", "Жер"],
            "fa": ["زهره", "عطارد", "مریخ", "زمین"],
        },
        "answer": "B",
        "difficulty": 0.2,
    },
    {
        "id": "ocean",
        "q": {
            "en": "Which is the largest ocean on Earth?",
            "ru": "Какой океан самый большой на Земле?",
            "kk": "Жердегі ең үлкен мұхит қайсы?",
            "fa": "بزرگ‌ترین اقیانوس زمین کدام است؟",
        },
        "choices": {
            "en": ["Atlantic", "Indian", "Arctic", "Pacific"],
            "ru": ["Атлантический", "Индийский", "Северный Ледовитый", "Тихий"],
            "kk": ["Атлант", "Үнді", "Солтүстік Мұзды", "Тынық"],
            "fa": ["اطلس", "هند", "منجمد شمالی", "آرام"],
        },
        "answer": "D",
        "difficulty": 0.25,
    },
    {
        "id": "boil",
        "q": {
            "en": "At sea level, at what temperature does water boil?",
            "ru": "При какой температуре кипит вода на уровне моря?",
            "kk": "Теңіз деңгейінде су қандай температурада қайнайды?",
            "fa": "آب در سطح دریا در چه دمایی می‌جوشد؟",
        },
        "choices": {
            "en": ["50 °C", "100 °C", "150 °C", "200 °C"],
            "ru": ["50 °C", "100 °C", "150 °C", "200 °C"],
            "kk": ["50 °C", "100 °C", "150 °C", "200 °C"],
            "fa": ["۵۰ درجه", "۱۰۰ درجه", "۱۵۰ درجه", "۲۰۰ درجه"],
        },
        "answer": "B",
        "difficulty": 0.15,
    },
    {
        "id": "continents",
        "q": {
            "en": "How many continents are traditionally counted in the seven-continent model?",
            "ru": "Сколько континентов в модели семи континентов?",
            "kk": "Жеті құрлық моделінде неше құрлық бар?",
            "fa": "در مدل هفت قاره، چند قاره وجود دارد؟",
        },
        "choices": {
            "en": ["5", "6", "7", "8"],
            "ru": ["5", "6", "7", "8"],
            "kk": ["5", "6", "7", "8"],
            "fa": ["۵", "۶", "۷", "۸"],
        },
        "answer": "C",
        "difficulty": 0.3,
    },
    {
        "id": "photosynthesis",
        "q": {
            "en": "Which gas do plants absorb from the air for photosynthesis?",
            "ru": "Какой газ растения поглощают из воздуха для фотосинтеза?",
            "kk": "Өсімдіктер фотосинтез үшін ауадан қандай газды сіңіреді?",
            "fa": "گیاهان برای فتوسنتز کدام گاز را از هوا جذب می‌کنند؟",
        },
        "choices": {
            "en": ["Oxygen", "Nitrogen", "Carbon dioxide", "Helium"],
            "ru": ["Кислород", "Азот", "Углекислый газ", "Гелий"],
            "kk": ["Оттегі", "Азот", "Көмірқышқыл газы", "Гелий"],
            "fa": ["اکسیژن", "نیتروژن", "دی‌اکسید کربن", "هلیوم"],
        },
        "answer": "C",
        "difficulty": 0.45,
    },
]

CODE = [
    (
        "add_numbers",
        "Write a Python function add_numbers(a, b) that returns the sum of a and b.",
        "def add_numbers(a, b):\n    return a + b",
        ["assert add_numbers(2, 3) == 5"],
        ["assert add_numbers(-1, 1) == 0", "assert add_numbers(10, 5) == 15"],
        0.1,
    ),
    (
        "reverse_string",
        "Write a Python function reverse_string(s) that returns s reversed.",
        "def reverse_string(s):\n    return s[::-1]",
        ["assert reverse_string('abc') == 'cba'"],
        ["assert reverse_string('') == ''", "assert reverse_string('ab') == 'ba'"],
        0.2,
    ),
    (
        "is_even",
        "Write a Python function is_even(n) that returns True if n is even.",
        "def is_even(n):\n    return n % 2 == 0",
        ["assert is_even(4)"],
        ["assert not is_even(7)", "assert is_even(0)"],
        0.1,
    ),
    (
        "factorial",
        "Write a Python function factorial(n) that returns n! for n >= 0.",
        "def factorial(n):\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n"
        "    return result",
        ["assert factorial(3) == 6"],
        ["assert factorial(0) == 1", "assert factorial(5) == 120"],
        0.4,
    ),
    (
        "second_largest",
        "Write a Python function second_largest(xs) that returns the second largest "
        "distinct value in a list of integers.",
        "def second_largest(xs):\n    return sorted(set(xs))[-2]",
        ["assert second_largest([1, 3, 2]) == 2"],
        ["assert second_largest([5, 5, 4, 1]) == 4", "assert second_largest([-1, -2]) == -2"],
        0.6,
    ),
    (
        "count_vowels",
        "Write a Python function count_vowels(s) that counts the vowels a, e, i, o, u "
        "(case-insensitive) in s.",
        "def count_vowels(s):\n    return sum(ch in 'aeiou' for ch in s.lower())",
        ["assert count_vowels('Hello') == 2"],
        ["assert count_vowels('xyz') == 0", "assert count_vowels('AEIOU') == 5"],
        0.35,
    ),
]


def rows() -> list[dict]:
    out = []
    for op, templates in ARITHMETIC.items():
        for k, (a, b) in enumerate(PAIRS):
            result = {"add": a + b, "mul": a * b, "word": a - b}[op]
            if op == "word" and a < b:
                a, b = b, a
                result = a - b
            size = 0.15 if max(a, b) > 50 else 0.0
            for lang, template in templates.items():
                text = template.format(a=a, b=b)
                if lang == "fa":
                    text = text.translate(FA_DIGITS)
                out.append(
                    {
                        "id": f"smoke-{op}-{k}-{lang}",
                        "question": text,
                        "answer": str(result),
                        "answer_type": "numeric",
                        "category": "math",
                        "language": lang,
                        "parallel_id": f"smoke-{op}-{k}",
                        "source": "smoke-fixture",
                        "license": "CC0-1.0",
                        "difficulty": round(BASE_DIFFICULTY[op] + size, 2),
                        "metadata": {"note": NOTE},
                    }
                )
    for fact in FACTS:
        for lang in ("en", "ru", "kk", "fa"):
            out.append(
                {
                    "id": f"smoke-fact-{fact['id']}-{lang}",
                    "question": fact["q"][lang],
                    "answer": fact["answer"],
                    "answer_type": "choice",
                    "choices": fact["choices"][lang],
                    "category": "factual_qa",
                    "language": lang,
                    "parallel_id": f"smoke-fact-{fact['id']}",
                    "source": "smoke-fixture",
                    "license": "CC0-1.0",
                    "difficulty": fact["difficulty"],
                    "metadata": {"note": NOTE},
                }
            )
    for name, prompt, solution, public, hidden, difficulty in CODE:
        out.append(
            {
                "id": f"smoke-code-{name}",
                "question": prompt + "\nExample: " + public[0],
                "answer": solution,
                "answer_type": "code",
                "category": "coding",
                "language": "en",
                "public_tests": public,
                "eval_tests": public + hidden,
                "entry_point": name,
                "solution": solution,
                "source": "smoke-fixture",
                "license": "CC0-1.0",
                "difficulty": difficulty,
                "metadata": {"note": NOTE},
            }
        )
    return out


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = rows()
    with OUT.open("w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(data)} items to {OUT}")


if __name__ == "__main__":
    main()
