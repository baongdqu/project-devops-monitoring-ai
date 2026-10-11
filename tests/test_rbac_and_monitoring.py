from app_ai_telegram.backend.config import settings, is_admin


def test_rbac_is_admin_check():
    # Khi admin_id được cấu hình
    original_admin = settings.TELEGRAM_ADMIN_ID
    try:
        settings.TELEGRAM_ADMIN_ID = "12345678"

        # Khớp ID -> True
        assert is_admin(12345678) is True
        assert is_admin("12345678") is True

        # Khác ID -> False
        assert is_admin("99999999") is False
        assert is_admin(99999999) is False

        # Khi không cấu hình admin ID -> Cho phép (backward compatibility)
        settings.TELEGRAM_ADMIN_ID = ""
        assert is_admin("99999999") is True
    finally:
        settings.TELEGRAM_ADMIN_ID = original_admin


def test_monitoring_settings_defaults():
    assert hasattr(settings, "TARGET_APP_URL")
    assert hasattr(settings, "MONITOR_INTERVAL_SECONDS")
    assert hasattr(settings, "ENABLE_PROACTIVE_MONITORING")
    assert settings.MONITOR_INTERVAL_SECONDS > 0
    assert isinstance(settings.ENABLE_PROACTIVE_MONITORING, bool)
