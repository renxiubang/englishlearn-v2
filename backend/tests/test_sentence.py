"""SentenceAccumulator 断句单测。"""

from app.gateway.sentence import SentenceAccumulator


def test_basic_split_on_stream():
    acc = SentenceAccumulator()
    out = acc.push("Hello there! How are")
    assert out == ["Hello there!"]
    out = acc.push(" you today? I am")
    assert out == ["How are you today?"]
    assert acc.flush() == "I am"


def test_short_sentence_merged_with_next():
    acc = SentenceAccumulator(min_len=8)
    # "OK." 过短不单独发射，与后续句子合并
    assert acc.push("OK. ") == []
    out = acc.push("Let's play football together! And")
    assert out == ["OK. Let's play football together!"]
    assert acc.flush() == "And"


def test_short_sentence_not_stuck():
    """短句不会永久阻塞缓冲区（回归：第一版 head-break bug）。"""
    acc = SentenceAccumulator(min_len=12)
    assert acc.push("No. ") == []
    assert acc.push("Yes. ") == []
    out = acc.push("Sounds great to me! ")
    assert out == ["No. Yes. Sounds great to me!"]
    assert acc.flush() is None


def test_flush_empty_returns_none():
    acc = SentenceAccumulator()
    assert acc.flush() is None
    acc.push("Complete sentence here. ")
    assert acc.flush() is None  # 已全部发射


def test_multiple_sentences_in_one_push():
    acc = SentenceAccumulator()
    out = acc.push("First sentence here. Second one too! Third tail")
    assert out == ["First sentence here.", "Second one too!"]
    assert acc.flush() == "Third tail"
