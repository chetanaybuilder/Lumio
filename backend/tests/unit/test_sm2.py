from app.features.flashcards import calculate_sm2

def test_sm2_failed_recall():
    """Quality < 3 resets repetitions to 0 and interval to 1 day."""
    rep, interval, ease = calculate_sm2(quality=2, repetitions=4, interval_days=10, ease_factor=2.5)
    assert rep == 0
    assert interval == 1

def test_sm2_progression():
    """Initial review (rep 0) -> interval 1; second review (rep 1) -> interval 6."""
    rep1, int1, ease1 = calculate_sm2(quality=4, repetitions=0, interval_days=0, ease_factor=2.5)
    assert rep1 == 1
    assert int1 == 1

    rep2, int2, ease2 = calculate_sm2(quality=4, repetitions=1, interval_days=1, ease_factor=ease1)
    assert rep2 == 2
    assert int2 == 6

    # Third review multiplies interval by ease
    rep3, int3, ease3 = calculate_sm2(quality=5, repetitions=2, interval_days=6, ease_factor=ease2)
    assert rep3 == 3
    assert int3 >= 14

def test_sm2_minimum_ease_floor():
    """Ease factor cannot fall below 1.3."""
    rep, interval, ease = calculate_sm2(quality=3, repetitions=2, interval_days=6, ease_factor=1.35)
    assert ease >= 1.3
