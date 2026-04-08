from server.app.settings.app_log_service import AppLogService


def test_get_app_log_returns_tail_lines(tmp_path):
    log_file = tmp_path / "app.log"
    log_file.write_text("1\n2\n3\n4\n5\n", encoding="utf-8")

    svc = AppLogService(str(log_file))

    result = svc.get_app_log(lines=3)

    assert result["filename"] == "app.log"
    assert result["exists"] is True
    assert result["line_count"] == 5
    assert result["content"] == "3\n4\n5"


def test_get_app_log_handles_missing_file(tmp_path):
    svc = AppLogService(str(tmp_path / "app.log"))

    result = svc.get_app_log(lines=50)

    assert result["filename"] == "app.log"
    assert result["exists"] is False
    assert result["content"] == ""
    assert result["line_count"] == 0
