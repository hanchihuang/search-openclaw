from search_openclaw.config import Config
from search_openclaw.social_scrape import _extract_run_dir, _redact_command, scrape_social


def test_extract_run_dir():
    assert _extract_run_dir("运行目录: /tmp/demo\n") == "/tmp/demo"
    assert _extract_run_dir("Run directory: /tmp/demo2\n") == "/tmp/demo2"


def test_redact_command():
    cmd = ["python", "-m", "demo", "--cookie", "secret-cookie", "--state", "/tmp/state.json"]
    assert _redact_command(cmd) == ["python", "-m", "demo", "--cookie", "<REDACTED>", "--state", "/tmp/state.json"]


def test_scrape_social_x(monkeypatch, tmp_path):
    config = Config(config_path=tmp_path / "config.yaml")
    config.set("x_auth_state_path", "/tmp/auth_state.json")

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            self.cmd = cmd
            self.returncode = 0
            self.stdout = iter(["运行目录: /tmp/run-x\n"])

        def wait(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", FakePopen)
    result = scrape_social(config, "x", "AI Agent", headless=True)
    assert result["x"]["run_dir"] == "/tmp/run-x"
    assert "search_openclaw.social.x_keyword_search" in result["x"]["command"]
