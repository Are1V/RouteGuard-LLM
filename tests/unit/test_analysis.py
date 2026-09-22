import pytest

from routeguard.analysis import LanguageDetector, LanguageProfile, register_language
from routeguard.analysis.analyzer import QueryAnalyzer
from routeguard.analysis.features import FEATURE_NAMES, extract_features
from routeguard.analysis.task import LearnedTaskClassifier, build_task_classifier
from routeguard.types import AnswerType, Query


@pytest.mark.parametrize(
    "text,lang",
    [
        ("What is the capital of France?", "en"),
        ("Какая столица Франции?", "ru"),
        ("Францияның астанасы қандай?", "kk"),
        ("12 мен 7 сандарының қосындысы нешеге тең?", "kk"),
        ("پایتخت فرانسه کجاست؟", "fa"),
        ("حاصل جمع ۱۲ و ۷ چند است؟", "fa"),
        ("ما هي عاصمة فرنسا؟", "ar"),
    ],
)
def test_language_detection(text, lang):
    assert LanguageDetector().detect(text).language == lang


def test_language_detection_undetermined_and_mixed():
    det = LanguageDetector()
    assert det.detect("12 + 7 = ?").language == "und"
    mixed = det.detect("Напишите функцию def reverse_list(xs) которая возвращает список")
    assert mixed.language == "ru"
    assert mixed.mixed_script


def test_code_heavy_query_keeps_natural_language_script():
    assert LanguageDetector().detect("def f(x): return x  # напиши функцию").language == "ru"


def test_register_new_language():
    register_language(
        LanguageProfile("uk", "Ukrainian", "Cyrillic", "їєґі", frozenset({"що", "як", "який"}))
    )
    det = LanguageDetector(["ru", "kk", "uk"])
    assert det.detect("Яка столиця України? Що це за місто, їх багато").language == "uk"
    with pytest.raises(ValueError):
        LanguageDetector(["xx"])


@pytest.mark.parametrize(
    "text,answer_type,category",
    [
        ("Сколько будет 12 плюс 7?", AnswerType.NUMERIC, "math"),
        ("Write a Python function that reverses a list", AnswerType.CODE, "coding"),
        ("Who invented the telephone?", AnswerType.TEXT, "factual_qa"),
        ("این متن را خلاصه کن", AnswerType.TEXT, "summarization"),
        ("Translate 'good morning' into Kazakh", AnswerType.TEXT, "translation"),
    ],
)
def test_rule_task_classifier(text, answer_type, category):
    clf = build_task_classifier("rules")
    assert clf.classify(Query(text=text, answer_type=answer_type))[0] == category


def test_rule_classifier_passage_topic_question_is_classification():
    q = Query(
        text="Which topic does the passage belong to?",
        context="جهش تنوع ژنتیکی",
        answer_type=AnswerType.CHOICE,
        choices=["a", "b"],
    )
    assert build_task_classifier("rules").classify(q)[0] == "classification"


def test_given_none_and_learned_classifiers():
    q = Query(text="x", category="math")
    assert build_task_classifier("given").classify(q) == ("math", 1.0)
    assert build_task_classifier("none").classify(q)[0] == "general"
    clf = LearnedTaskClassifier()
    train = [Query(text=f"How much is {i} plus {i + 1}?", category="math") for i in range(10)]
    train += [Query(text=f"Who was the king number {i}?", category="factual_qa") for i in range(10)]
    clf.fit(train)
    assert clf.classify(Query(text="How much is 3 plus 9?"))[0] == "math"
    with pytest.raises(ValueError):
        build_task_classifier("bogus")


def test_learned_classifier_falls_back_with_single_class():
    clf = LearnedTaskClassifier().fit([Query(text="a", category="math")] * 3)
    assert not clf.fitted
    assert (
        clf.classify(Query(text="Сколько будет 2 плюс 2?", answer_type=AnswerType.NUMERIC))[0]
        == "math"
    )


def test_features_and_analyzer_uses_context_for_language():
    feats = extract_features(Query(text="Compute 3 * 4 + 5 = ? Explain step by step."))
    assert set(feats) == set(FEATURE_NAMES)
    assert feats["n_math_ops"] >= 2 and feats["step_cues"] >= 1
    analyzer = QueryAnalyzer(LanguageDetector(), build_task_classifier("rules"))
    q = Query(
        text="Which topic does the passage belong to?",
        context="Бұл мәтін спорт туралы және қазақ тілінде жазылған.",
    )
    assert analyzer.analyze(q).language == "kk"
