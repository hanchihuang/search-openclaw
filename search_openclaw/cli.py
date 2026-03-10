"""CLI for Search OpenClaw."""

from __future__ import annotations

import argparse
import importlib.resources
import os
import sys

from search_openclaw import __version__
from search_openclaw.config import Config
from search_openclaw.doctor import check_all, format_report
from search_openclaw.search import (
    SearchError,
    auto_provider,
    dump_results_json,
    format_results,
    search,
    search_iflow_structured,
    stream_iflow,
)
from search_openclaw.social_scrape import SocialScrapeError, run_x_login, scrape_social


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="search-openclaw",
        description="Configure and diagnose OpenClaw web search providers",
    )
    parser.add_argument("--version", action="version", version=f"Search OpenClaw v{__version__}")
    sub = parser.add_subparsers(dest="command")

    install_parser = sub.add_parser("install", help="Install Search OpenClaw skill and print next steps")
    install_parser.add_argument("--dry-run", action="store_true", help="Show what would be installed")
    install_parser.add_argument("--safe", action="store_true", help="Skip optional system package hints")

    configure_parser = sub.add_parser("configure", help="Set a configuration value")
    configure_parser.add_argument(
        "key",
        choices=[
            "brave_api_key",
            "tavily_api_key",
            "exa_api_key",
            "perplexity_api_key",
            "iflow_api_key",
            "iflow_base_url",
            "iflow_model",
            "github_token",
            "zhihu_cookie",
            "x_aggregator_repo_path",
            "x_aggregator_python",
            "x_auth_state_path",
        ],
    )
    configure_parser.add_argument("value")

    doctor_parser = sub.add_parser("doctor", help="Run provider health checks")
    doctor_parser.add_argument("--fix", action="store_true", help="Auto-install skill and detect local integrations")
    search_parser = sub.add_parser("search", help="Run a search using a configured provider")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--provider",
        default="auto",
        choices=["auto", "brave", "tavily", "exa", "perplexity", "iflow", "github"],
        help="Which provider to use",
    )
    search_parser.add_argument("--limit", type=int, default=5, help="Number of results")
    search_parser.add_argument("--json", action="store_true", help="Print raw JSON output")
    search_parser.add_argument("--stream", action="store_true", help="Stream iFlow output")
    search_parser.add_argument("--structured", action="store_true", help="Use iFlow structured JSON mode")
    sub.add_parser("version", help="Show version")
    sub.add_parser("show-config", help="Show current masked config")
    uninstall_parser = sub.add_parser("uninstall", help="Remove skill files and local config")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Preview removals only")
    login_x_parser = sub.add_parser("login-x", help="Open browser and save X login state")
    login_x_parser.add_argument("--timeout", type=int, default=180, help="Seconds to wait for manual login")
    scrape_parser = sub.add_parser("scrape-social", help="One-command keyword scraping for X / Zhihu")
    scrape_parser.add_argument("keyword", help="Search keyword")
    scrape_parser.add_argument("--platform", default="both", choices=["x", "zhihu", "both"])
    scrape_parser.add_argument("--headed", action="store_true", help="Run browsers in headed mode")
    scrape_parser.add_argument("--out-dir", default="", help="Optional output directory")
    scrape_parser.add_argument("--zhihu-cookie", default="", help="Optional Zhihu cookie override")
    scrape_parser.add_argument("--max-items", type=int, default=0, help="Optional max result count")
    scrape_parser.add_argument("--max-scrolls", type=int, default=0, help="Optional max scroll rounds")
    scrape_parser.add_argument("--no-new-stop", type=int, default=0, help="Stop after N rounds with no new results")
    scrape_parser.add_argument("--scroll-pause", type=int, default=0, help="X scraping pause in ms")
    scrape_parser.add_argument("--page-delay-ms", type=int, default=0, help="Zhihu page delay in ms")
    scrape_parser.add_argument("--detail-delay-ms", type=int, default=0, help="Zhihu detail delay in ms")
    scrape_parser.add_argument("--detail-limit", type=int, default=-1, help="Limit Zhihu detail hydration count")
    scrape_parser.add_argument("--stage1-only", action="store_true", help="Zhihu only: collect search results without hydrating details")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        raise SystemExit(0)

    if args.command == "version":
        print(f"Search OpenClaw v{__version__}")
        raise SystemExit(0)
    if args.command == "install":
        _cmd_install(args)
        return
    if args.command == "configure":
        _cmd_configure(args)
        return
    if args.command == "doctor":
        _cmd_doctor(args)
        return
    if args.command == "search":
        _cmd_search(args)
        return
    if args.command == "show-config":
        _cmd_show_config()
        return
    if args.command == "uninstall":
        _cmd_uninstall(args)
        return
    if args.command == "login-x":
        _cmd_login_x(args)
        return
    if args.command == "scrape-social":
        _cmd_scrape_social(args)
        return


def _cmd_install(args: argparse.Namespace) -> None:
    print()
    print("Search OpenClaw Installer")
    print("=" * 40)
    print("目标：安装 Search OpenClaw skill，并给出搜索层配置建议。")
    print()

    if args.dry_run:
        print("DRY RUN — 不会写入任何文件")
    elif args.safe:
        print("SAFE MODE — 只安装 skill，不做任何额外系统修改")

    _install_skill(dry_run=args.dry_run)
    print()
    print("推荐下一步：")
    print("  1. 有卡：search-openclaw configure brave_api_key <YOUR_KEY>")
    print("  2. 没卡：search-openclaw configure tavily_api_key <YOUR_KEY>")
    print("  3. 已有 OpenClaw iFlow：直接复用，无需重复填 key")
    print("  4. 检查状态：search-openclaw doctor")
    print(f"  4. 直接搜索：search-openclaw search \"latest AI developments\" --provider {auto_provider(Config())}")


def _install_skill(dry_run: bool = False) -> None:
    skill_dirs = [
        os.path.expanduser("~/.openclaw/skills"),
        os.path.expanduser("~/.claude/skills"),
        os.path.expanduser("~/.agents/skills"),
    ]
    installed = False

    for skill_dir in skill_dirs:
        target = os.path.join(skill_dir, "search-openclaw")
        if dry_run:
            print(f"[dry-run] Would install skill to: {target}")
            installed = True
            continue
        try:
            os.makedirs(target, exist_ok=True)
            skill_md = importlib.resources.files("search_openclaw").joinpath("skill", "SKILL.md").read_text()
            with open(os.path.join(target, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write(skill_md)
            print(f"Skill installed: {target}")
            installed = True
        except Exception:
            continue

    if not installed and not dry_run:
        print("未能安装 skill；请手动创建 ~/.openclaw/skills/search-openclaw/SKILL.md")


def _cmd_configure(args: argparse.Namespace) -> None:
    config = Config()
    config.set(args.key, args.value.strip())
    print(f"已写入 {args.key}")
    print(f"配置文件：{config.config_path}")


def _cmd_doctor(args: argparse.Namespace) -> None:
    config = Config()
    if getattr(args, "fix", False):
        _cmd_doctor_fix(config)
    print(format_report(check_all(config)))


def _cmd_search(args: argparse.Namespace) -> None:
    config = Config()
    if args.provider == "iflow" and args.stream:
        for chunk in stream_iflow(args.query, config):
            print(chunk, end="", flush=True)
        print()
        return
    if args.provider == "iflow" and args.structured:
        import json

        print(json.dumps(search_iflow_structured(args.query, config), ensure_ascii=False, indent=2))
        return
    provider, results = search(args.query, args.provider, args.limit, config)
    if args.json:
        print(dump_results_json(provider, results))
        return
    print(format_results(provider, results))


def _cmd_show_config() -> None:
    config = Config()
    print(config.to_dict())


def _cmd_uninstall(args: argparse.Namespace) -> None:
    config = Config()
    targets = [
        config.config_path,
        os.path.expanduser("~/.openclaw/skills/search-openclaw"),
        os.path.expanduser("~/.claude/skills/search-openclaw"),
        os.path.expanduser("~/.agents/skills/search-openclaw"),
    ]
    if args.dry_run:
        for target in targets:
            print(f"[dry-run] Would remove: {target}")
        return

    for target in targets:
        if os.path.isdir(target):
            import shutil

            shutil.rmtree(target, ignore_errors=True)
            print(f"Removed directory: {target}")
        elif os.path.isfile(target):
            os.remove(target)
            print(f"Removed file: {target}")


def _cmd_doctor_fix(config: Config) -> None:
    _install_skill(dry_run=False)
    default_state = str((Config.CONFIG_DIR / "social" / "auth_state_cookie.json").resolve())
    if not config.get("x_auth_state_path"):
        config.set("x_auth_state_path", default_state)
        print(f"已设置 X 登录态路径: {default_state}")

    iflow = config.get_iflow_settings()
    if iflow:
        print(f"已检测到 OpenClaw iFlow 配置: {iflow.get('source_path')}")
    else:
        print("未检测到 OpenClaw iFlow 配置")

    if not config.get("zhihu_cookie"):
        print("知乎 Cookie 尚未配置；如需抓取知乎，请执行 search-openclaw configure zhihu_cookie <COOKIE>")
    print("X / 知乎抓取现已使用 search-openclaw 内置副本，不再依赖 x_search_aggregator")


def _cmd_login_x(args: argparse.Namespace) -> None:
    config = Config()
    print(run_x_login(config, timeout=args.timeout))


def _cmd_scrape_social(args: argparse.Namespace) -> None:
    import json

    config = Config()
    result = scrape_social(
        config=config,
        platform=args.platform,
        keyword=args.keyword,
        headless=not args.headed,
        out_dir=args.out_dir or None,
        zhihu_cookie=args.zhihu_cookie or None,
        max_items=args.max_items or None,
        max_scrolls=args.max_scrolls or None,
        no_new_stop=args.no_new_stop or None,
        scroll_pause=args.scroll_pause or None,
        page_delay_ms=args.page_delay_ms or None,
        detail_delay_ms=args.detail_delay_ms or None,
        detail_limit=None if args.detail_limit < 0 else args.detail_limit,
        stage1_only=args.stage1_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def run_main() -> int:
    try:
        main()
        return 0
    except SearchError as exc:
        print(f"Search error: {exc}", file=sys.stderr)
        return 2
