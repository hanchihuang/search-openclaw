"""Independent X keyword search copied and simplified from local prototype scripts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Error, TimeoutError, sync_playwright

from search_openclaw.social.browser_config import get_browser_args, get_context_options
from search_openclaw.social.reporting import build_simple_html, safe_name, write_csv, write_json, write_markdown_summary

STATUS_PATH_RE = re.compile(r"(?:https?://x\.com)?/(?:i/web/)?([^/]+)/status/(\d+)")
COUNT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)([KMB]?)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search X by keyword and save top results.")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--lang", default="")
    parser.add_argument("--state", required=True)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--max-scrolls", type=int, default=180)
    parser.add_argument("--no-new-stop", type=int, default=10)
    parser.add_argument("--scroll-pause", type=int, default=1800)
    return parser.parse_args()


def make_search_url(keyword: str, lang: str) -> str:
    query = re.sub(r"\s+", " ", keyword).strip()
    if lang:
        query = f"{query} lang:{lang}"
    return f"https://x.com/search?q={quote(query, safe=':')}&src=typed_query&f=live"


def parse_count(raw: str) -> int:
    if not raw:
        return 0
    match = COUNT_RE.search(str(raw).replace(",", "").replace(" ", ""))
    if not match:
        digits = re.findall(r"\d+", raw)
        return int(digits[0]) if digits else 0
    value = float(match.group(1))
    suffix = match.group(2).upper()
    multiplier = {"": 1, "K": 1000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    return int(value * multiplier)


def parse_network_result(result: dict) -> dict | None:
    legacy = result.get("legacy") or {}
    tweet_id = result.get("rest_id") or legacy.get("id_str")
    text = legacy.get("full_text") or ""
    if not tweet_id or not text:
        return None
    core = ((result.get("core") or {}).get("user_results") or {}).get("result") or {}
    user_legacy = core.get("legacy") or {}
    handle = user_legacy.get("screen_name") or ""
    url = f"https://x.com/{handle}/status/{tweet_id}" if handle else f"https://x.com/i/web/status/{tweet_id}"
    views = (result.get("views") or {}).get("count")
    view_count = int(views) if isinstance(views, str) and views.isdigit() else (views if isinstance(views, int) else 0)
    return {
        "tweet_id": str(tweet_id),
        "user_handle": handle,
        "url": url,
        "text": text,
        "posted_at": legacy.get("created_at", ""),
        "reply_count": int(legacy.get("reply_count") or 0),
        "retweet_count": int(legacy.get("retweet_count") or 0),
        "like_count": int(legacy.get("favorite_count") or 0),
        "bookmark_count": int(legacy.get("bookmark_count") or 0),
        "view_count": view_count,
    }


def walk_collect_network(obj, out: list[dict]) -> None:
    if isinstance(obj, dict):
        tweet_results = obj.get("tweet_results")
        if isinstance(tweet_results, dict):
            result = tweet_results.get("result")
            if isinstance(result, dict):
                item = parse_network_result(result)
                if item:
                    out.append(item)
        for value in obj.values():
            walk_collect_network(value, out)
        return
    if isinstance(obj, list):
        for value in obj:
            walk_collect_network(value, out)


def create_context(playwright, state_path: str, headless: bool):
    browser = playwright.chromium.launch(headless=headless, args=get_browser_args())
    options = get_context_options()
    state = Path(state_path).expanduser().resolve()
    if state.exists():
        options["storage_state"] = str(state)
    return browser.new_context(**options)


def validate_auth_state(page) -> bool:
    try:
        page.wait_for_selector('nav[aria-label="Primary"], input[data-testid="SearchBox_Search_Input"]', timeout=6000)
        return True
    except TimeoutError:
        return False


def goto_with_retry(page, url: str, attempts: int = 3) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            return
        except Error as exc:
            last_error = exc
            if attempt >= attempts:
                break
            page.wait_for_timeout(1500 * attempt)
    if last_error:
        raise last_error


def parse_status_href(href: str) -> tuple[str | None, str | None]:
    match = STATUS_PATH_RE.search(href or "")
    if not match:
        return None, None
    return match.group(1), match.group(2)


def extract_tweet(article) -> dict | None:
    link = article.query_selector('a[href*="/status/"]')
    if not link:
        return None
    href = (link.get_attribute("href") or "").strip()
    user_handle, tweet_id = parse_status_href(href)
    if not tweet_id:
        return None

    text_parts = []
    for selector in ['div[data-testid="tweetText"]', 'div[lang]', 'span[lang]']:
        for el in article.query_selector_all(selector):
            text = (el.inner_text() or "").strip()
            if text and text not in text_parts:
                text_parts.append(text)
    text = "\n".join(text_parts).strip()
    if not text:
        text = (article.inner_text() or "").strip()

    metric_buttons = {
        "reply_count": 'button[data-testid="reply"]',
        "retweet_count": 'button[data-testid="retweet"]',
        "like_count": 'button[data-testid="like"]',
        "bookmark_count": 'button[data-testid="bookmark"]',
    }
    metrics = {}
    for key, selector in metric_buttons.items():
        btn = article.query_selector(selector)
        metrics[key] = parse_count((btn.inner_text() or "").strip()) if btn else 0

    time_el = article.query_selector("time")
    posted_at = time_el.get_attribute("datetime") if time_el else ""

    return {
        "tweet_id": tweet_id,
        "user_handle": user_handle or "",
        "url": href if href.startswith("http") else f"https://x.com{href}",
        "text": text,
        "posted_at": posted_at,
        **metrics,
    }


def merge_tweet(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for key, value in incoming.items():
        if key in {"reply_count", "retweet_count", "like_count", "bookmark_count", "view_count"}:
            merged[key] = max(int(merged.get(key, 0) or 0), int(value or 0))
        elif value and (not merged.get(key) or len(str(value)) > len(str(merged.get(key, "")))):
            merged[key] = value
    return merged


def collect_tweets(
    page,
    max_items: int,
    max_scrolls: int,
    no_new_stop: int,
    scroll_pause: int,
    network_items: dict[str, dict],
) -> list[dict]:
    seen_ids: set[str] = set()
    items: list[dict] = []
    items_by_id: dict[str, dict] = {}
    no_new_rounds = 0
    last_height = 0

    for round_no in range(1, max_scrolls + 1):
        new_items = 0
        batch = list(network_items.values())
        for article in page.query_selector_all('article[data-testid="tweet"]'):
            tweet = extract_tweet(article)
            if tweet:
                batch.append(tweet)
        for tweet in batch:
            if not tweet or tweet["tweet_id"] in seen_ids:
                if tweet and tweet["tweet_id"] in items_by_id:
                    items_by_id[tweet["tweet_id"]].update(merge_tweet(items_by_id[tweet["tweet_id"]], tweet))
                continue
            seen_ids.add(tweet["tweet_id"])
            items_by_id[tweet["tweet_id"]] = tweet
            items.append(items_by_id[tweet["tweet_id"]])
            new_items += 1
            if len(items) >= max_items:
                break
        print(f"Page {round_no}: + {new_items} new, total {len(items)}")
        if len(items) >= max_items:
            break
        no_new_rounds = 0 if new_items else no_new_rounds + 1
        page.mouse.wheel(0, 2600)
        page.wait_for_timeout(scroll_pause)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height and no_new_rounds >= no_new_stop:
            break
        last_height = new_height
    return items


def write_outputs(run_dir: Path, keyword: str, search_url: str, rows: list[dict]) -> None:
    payload = {
        "keyword": keyword,
        "search_url": search_url,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": rows,
    }
    write_json(run_dir / "results_stage1.json", payload)
    write_json(run_dir / "results.json", payload)
    write_csv(
        run_dir / "results.csv",
        rows,
        ["tweet_id", "user_handle", "url", "posted_at", "reply_count", "retweet_count", "like_count", "bookmark_count", "view_count", "text"],
    )
    write_markdown_summary(
        run_dir / "summary.md",
        f"X keyword search - {keyword}",
        [f"- Search URL: {search_url}", f"- Results: {len(rows)}"],
        rows,
        "text",
    )
    (run_dir / "article.html").write_text(
        build_simple_html(f"X keyword search - {keyword}", [f"Search URL: {search_url}", f"Results: {len(rows)}"], rows, "text"),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    out_base = Path(args.out_dir).expanduser().resolve()
    run_dir = out_base / f"{safe_name(args.keyword)}_500_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    search_url = make_search_url(args.keyword, args.lang)
    print(f"运行目录: {run_dir}")
    print(f"搜索URL: {search_url}")

    with sync_playwright() as p:
        context = create_context(p, args.state, args.headless)
        page = context.new_page()
        network_items: dict[str, dict] = {}

        def on_response(response) -> None:
            if "/SearchTimeline?" not in response.url:
                return
            try:
                text = response.text()
            except Exception:
                return
            if not text:
                return
            try:
                data = json.loads(text)
            except Exception:
                return
            batch: list[dict] = []
            walk_collect_network(data, batch)
            for item in batch:
                existing = network_items.get(item["tweet_id"])
                network_items[item["tweet_id"]] = merge_tweet(existing or {}, item) if existing else item

        page.on("response", on_response)
        goto_with_retry(page, search_url)
        page.wait_for_timeout(3000)
        if not validate_auth_state(page):
            raise RuntimeError("X 登录态无效，请先重新执行 login-x")
        items = collect_tweets(page, args.max_items, args.max_scrolls, args.no_new_stop, args.scroll_pause, network_items)
        context.close()

    if not items:
        raise RuntimeError("未收集到任何 X 结果")
    write_outputs(run_dir, args.keyword, search_url, items)
    print(f"完成！已收集 {len(items)} 条推文。")
    print(f"Results JSON: {run_dir / 'results.json'}")
    print(f"Results CSV: {run_dir / 'results.csv'}")
    print(f"Summary Markdown: {run_dir / 'summary.md'}")
    print(f"Article HTML: {run_dir / 'article.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
