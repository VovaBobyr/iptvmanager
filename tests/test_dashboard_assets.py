from pathlib import Path


TEMPLATES = Path(__file__).parents[1] / "src" / "iptv_manager" / "templates"


def test_dashboard_assets_use_proxy_safe_paths() -> None:
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    dashboard = (TEMPLATES / "dashboard.html").read_text(encoding="utf-8")

    assert 'href="/static/app.css"' in base
    assert 'src="/static/app.js"' in dashboard
    assert "url_for('static'" not in base + dashboard
