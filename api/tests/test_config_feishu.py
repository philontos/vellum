from app import config


def test_feishu_creds_read_and_strip_env(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "  cli_abc  ")
    monkeypatch.setenv("FEISHU_APP_SECRET", "  sec_xyz  ")
    assert config.feishu_app_id() == "cli_abc"
    assert config.feishu_app_secret() == "sec_xyz"


def test_feishu_enabled_only_when_both_present(monkeypatch):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    assert config.feishu_enabled() is False

    monkeypatch.setenv("FEISHU_APP_ID", "cli_abc")
    assert config.feishu_enabled() is False        # secret still missing

    monkeypatch.setenv("FEISHU_APP_SECRET", "sec_xyz")
    assert config.feishu_enabled() is True
