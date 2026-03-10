"""Built-in wrappers around vendored X / Zhihu scraping modules."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from search_openclaw.config import Config


class SocialScrapeError(RuntimeError):
    """Raised when a social scraping workflow fails."""


def detect_repo(config: Config) -> Path:
    return Path(__file__).resolve().parents[1]


def detect_python(config: Config, repo: Path) -> str:
    configured = config.get("x_aggregator_python")
    if configured:
        return str(configured)
    return sys.executable or "python3"


def run_x_login(config: Config, timeout: int = 180) -> str:
    repo = detect_repo(config)
    python_bin = detect_python(config, repo)
    state_path = config.get("x_auth_state_path")
    if not state_path:
        state_path = str((Config.CONFIG_DIR / "social" / "auth_state_cookie.json").resolve())
    Path(state_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [python_bin, "-m", "search_openclaw.social.login_x", "--state", state_path, "--timeout", str(timeout)],
        cwd=repo,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise SocialScrapeError(proc.stderr.strip() or proc.stdout.strip() or "X 登录失败")
    config.set("x_auth_state_path", state_path)
    return proc.stdout


def scrape_social(
    config: Config,
    platform: str,
    keyword: str,
    headless: bool = True,
    out_dir: str | None = None,
    zhihu_cookie: str | None = None,
    max_items: int | None = None,
    max_scrolls: int | None = None,
    no_new_stop: int | None = None,
    scroll_pause: int | None = None,
    page_delay_ms: int | None = None,
    detail_delay_ms: int | None = None,
    detail_limit: int | None = None,
    stage1_only: bool = False,
) -> dict[str, dict]:
    repo = detect_repo(config)
    python_bin = detect_python(config, repo)
    output: dict[str, dict] = {}

    if platform in {"x", "both"}:
        x_state = config.get("x_auth_state_path")
        if not x_state:
            raise SocialScrapeError("未找到 X 登录态文件，请先执行 search-openclaw login-x")
        cmd = [python_bin, "-m", "search_openclaw.social.x_keyword_search", "--keyword", keyword, "--state", str(x_state)]
        if headless:
            cmd.append("--headless")
        if out_dir:
            cmd.extend(["--out-dir", out_dir])
        if max_items:
            cmd.extend(["--max-items", str(max_items)])
        if max_scrolls:
            cmd.extend(["--max-scrolls", str(max_scrolls)])
        if no_new_stop:
            cmd.extend(["--no-new-stop", str(no_new_stop)])
        if scroll_pause:
            cmd.extend(["--scroll-pause", str(scroll_pause)])
        output["x"] = _run_and_parse(cmd, repo)

    if platform in {"zhihu", "both"}:
        cookie = zhihu_cookie or config.get("zhihu_cookie")
        if not cookie:
            raise SocialScrapeError("未配置 zhihu_cookie；请先运行 search-openclaw configure zhihu_cookie <COOKIE>")
        cmd = [python_bin, "-m", "search_openclaw.social.zhihu_keyword_search", "--keyword", keyword, "--cookie", cookie]
        if headless:
            cmd.append("--headless")
        if out_dir:
            cmd.extend(["--out-dir", out_dir])
        if max_items:
            cmd.extend(["--max-items", str(max_items)])
        if max_scrolls:
            cmd.extend(["--max-scrolls", str(max_scrolls)])
        if no_new_stop:
            cmd.extend(["--no-new-stop", str(no_new_stop)])
        if page_delay_ms:
            cmd.extend(["--page-delay-ms", str(page_delay_ms)])
        if detail_delay_ms:
            cmd.extend(["--detail-delay-ms", str(detail_delay_ms)])
        if detail_limit is not None and detail_limit >= 0:
            cmd.extend(["--detail-limit", str(detail_limit)])
        if stage1_only:
            cmd.append("--stage1-only")
        output["zhihu"] = _run_and_parse(cmd, repo)

    return output


def _run_and_parse(cmd: list[str], repo: Path) -> dict[str, str]:
    proc = subprocess.Popen(
        cmd,
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
        lines.append(line)
    proc.wait()
    stdout = "".join(lines)
    if proc.returncode != 0:
        raise SocialScrapeError(stdout.strip() or "爬取失败")

    run_dir = _extract_run_dir(stdout)
    return {
        "command": " ".join(_redact_command(cmd)),
        "run_dir": run_dir or "",
        "stdout": stdout,
    }


def _extract_run_dir(text: str) -> str | None:
    patterns = [
        r"运行目录:\s*(.+)",
        r"Run directory:\s*(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _redact_command(cmd: list[str]) -> list[str]:
    secret_flags = {"--cookie", "--zhihu-cookie", "--token", "--api-key", "--apikey"}
    redacted: list[str] = []
    redact_next = False
    for part in cmd:
        if redact_next:
            redacted.append("<REDACTED>")
            redact_next = False
            continue
        if part in secret_flags:
            redacted.append(part)
            redact_next = True
            continue
        redacted.append(part)
    return redacted
