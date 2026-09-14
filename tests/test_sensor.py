from switchbot_lock_logs.sensor import _display_user


def test_display_user_never_unknown():
    assert _display_user({"user_name": "jo", "source_display": "Keypad"}) == "jo"
    assert _display_user({"user_name": None, "source_display": "Manual"}) == (
        "Manual thumbturn"
    )
    assert _display_user({"user_name": None, "source_display": "System"}) == "Auto-lock"
    assert _display_user({"user_name": None, "source_display": "Keypad"}) == (
        "Keypad (unmapped)"
    )
    assert _display_user({"user_name": None, "source_display": None}) == "Unidentified"
