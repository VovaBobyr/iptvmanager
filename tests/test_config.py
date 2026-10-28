from iptv_manager.config import Settings


def test_codespaces_environment_sets_runner_and_public_url(monkeypatch):
    monkeypatch.setenv("CODESPACE_NAME", "friendly-space")
    monkeypatch.setenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    monkeypatch.delenv("IPTV_RUNNER_NAME", raising=False)
    monkeypatch.delenv("IPTV_PUBLIC_BASE_URL", raising=False)

    settings = Settings.from_env()

    assert settings.runner_name == "codespace:friendly-space"
    assert settings.public_base_url == "https://friendly-space-8000.app.github.dev"
