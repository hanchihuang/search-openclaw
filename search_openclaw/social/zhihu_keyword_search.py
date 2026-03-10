"""Independent Zhihu keyword search copied and simplified from local prototype scripts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from html import unescape
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import TimeoutError, sync_playwright

from search_openclaw.social.browser_config import get_browser_args
from search_openclaw.social.reporting import build_simple_html, safe_name, write_csv, write_json, write_markdown_summary
from search_openclaw.social.zhihu_helpers import (
    ANSWER_URL_RE,
    ARTICLE_URL_RE,
    QUESTION_URL_RE,
    DEFAULT_USER_AGENT,
    click_expand_buttons,
    detect_risk_or_login,
    first_text,
    longest_text,
    parse_cookie_string,
)

CONTENT_URL_RE = re.compile(
    r"^https?://(?:www\.zhihu\.com/question/\d+(?:/answer/\d+)?|zhuanlan\.zhihu\.com/p/\d+)(?:[/?#].*)?$"
)


def make_absolute_content_url(value: str) -> str:
    raw = unescape(str(value or "")).strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = f"https:{raw}"
    elif raw.startswith("/question/"):
        raw = f"https://www.zhihu.com{raw}"
    elif raw.startswith("/p/"):
        raw = f"https://zhuanlan.zhihu.com{raw}"
    elif raw.startswith("question/"):
        raw = f"https://www.zhihu.com/{raw}"
    elif raw.startswith("p/"):
        raw = f"https://zhuanlan.zhihu.com/{raw}"
    return canonical_url(raw)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Zhihu content and hydrate top results.")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--cookie", required=True)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--max-items", type=int, default=500)
    parser.add_argument("--max-scrolls", type=int, default=140)
    parser.add_argument("--no-new-stop", type=int, default=8)
    parser.add_argument("--page-delay-ms", type=int, default=1800)
    parser.add_argument("--detail-delay-ms", type=int, default=1200)
    return parser.parse_args()


def make_search_url(keyword: str) -> str:
    return f"https://www.zhihu.com/search?type=content&q={quote(re.sub(r'\\s+', ' ', keyword).strip())}"


def canonical_url(url: str) -> str:
    return (url or "").split("?", 1)[0].split("#", 1)[0].rstrip("/")


def detect_content_type(url: str) -> str:
    if ANSWER_URL_RE.match(url):
        return "answer"
    if ARTICLE_URL_RE.match(url):
        return "article"
    if QUESTION_URL_RE.match(url):
        return "question"
    return "unknown"


def collect_result_candidates(page) -> list[dict]:
    return page.eval_on_selector_all(
        "a[href], [data-za-detail-view-path-module], [data-za-detail-view-element_name]",
        """
        elements => {
          const out = [];
          for (const el of elements) {
            const a = el.tagName === 'A' ? el : (el.querySelector && el.querySelector('a[href]'));
            const href = (a && a.href) || "";
            if (!href) continue;
            if (!/^https?:\\/\\//.test(href)) continue;
            const card =
              (a && a.closest && (
                a.closest('[class*="SearchResult"]') ||
                a.closest('[class*="List-item"]') ||
                a.closest('[class*="ContentItem"]') ||
                a.closest('[class*="Card"]') ||
                a.closest('article') ||
                a.closest('section')
              )) ||
              (el.closest && (
                el.closest('[class*="SearchResult"]') ||
                el.closest('[class*="List-item"]') ||
                el.closest('[class*="ContentItem"]') ||
                el.closest('[class*="Card"]')
              )) ||
              a?.parentElement ||
              el.parentElement;
            const title = (((a && a.textContent) || el.textContent || "")).replace(/\\s+/g, " ").trim();
            const context = (card?.innerText || "").replace(/\\s+/g, " ").trim();
            out.push({ href, title, context });
          }
          return out;
        }
        """,
    )


def extract_candidates_from_json_blob(text: str) -> list[dict]:
    found: dict[str, dict] = {}

    def add_candidate(url: str, title: str = "", context: str = "") -> None:
        canonical = make_absolute_content_url(url)
        if not CONTENT_URL_RE.match(canonical):
            return
        item = found.get(canonical, {"href": canonical, "title": "", "context": ""})
        if title and len(title) > len(item["title"]):
            item["title"] = title[:240]
        if context and len(context) > len(item["context"]):
            item["context"] = context[:600]
        found[canonical] = item

    def walk(node) -> None:
        if isinstance(node, dict):
            url_fields = [
                node.get("url"),
                node.get("target"),
                node.get("target_url"),
                node.get("link"),
                node.get("shareUrl"),
                node.get("schema"),
            ]
            title = str(
                node.get("title")
                or node.get("name")
                or node.get("question_text")
                or node.get("headline")
                or ""
            ).strip()
            context = str(
                node.get("excerpt")
                or node.get("description")
                or node.get("content")
                or node.get("highlight")
                or ""
            ).strip()
            for url in url_fields:
                if url:
                    add_candidate(str(url), title, context)

            question_id = node.get("question_id") or node.get("questionId")
            answer_id = node.get("answer_id") or node.get("answerId")
            article_id = node.get("article_id") or node.get("articleId")
            item_id = node.get("id")
            item_type = str(node.get("type") or node.get("object_type") or "").lower()
            if question_id and answer_id:
                add_candidate(f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}", title, context)
            elif question_id:
                add_candidate(f"https://www.zhihu.com/question/{question_id}", title, context)
            elif article_id:
                add_candidate(f"https://zhuanlan.zhihu.com/p/{article_id}", title, context)
            elif item_id and item_type in {"question", "answer", "article"}:
                if item_type == "question":
                    add_candidate(f"https://www.zhihu.com/question/{item_id}", title, context)
                elif item_type == "article":
                    add_candidate(f"https://zhuanlan.zhihu.com/p/{item_id}", title, context)

            for value in node.values():
                walk(value)
            return

        if isinstance(node, list):
            for value in node:
                walk(value)
            return

        if isinstance(node, str):
            for match in re.finditer(
                r"(?:https?:)?//(?:www\.zhihu\.com/question/\d+(?:/answer/\d+)?|zhuanlan\.zhihu\.com/p/\d+)|/(?:question/\d+(?:/answer/\d+)?|p/\d+)",
                node,
            ):
                add_candidate(match.group(0))

    try:
        payload = json.loads(text)
    except Exception:
        return []
    walk(payload)
    return list(found.values())


def extract_candidates_from_html(page) -> list[dict]:
    html = page.content()
    found = []
    seen = set()
    for match in re.finditer(r"https?://(?:www\.zhihu\.com/question/\d+(?:/answer/\d+)?|zhuanlan\.zhihu\.com/p/\d+)", html):
        url = canonical_url(unescape(match.group(0)))
        if url in seen:
            continue
        seen.add(url)
        found.append(
            {
                "href": url,
                "title": "",
                "context": "",
            }
        )
    return found


def extract_embedded_state_candidates(page) -> list[dict]:
    found: dict[str, dict] = {}
    for selector in ['script[id="js-initialData"]', 'script[data-zop-usertoken]', 'script[type="application/json"]']:
        locator = page.locator(selector)
        count = min(locator.count(), 8)
        for idx in range(count):
            try:
                text = locator.nth(idx).inner_text(timeout=800)
            except Exception:
                continue
            if not text or "question" not in text and "zhuanlan.zhihu.com" not in text:
                continue
            for item in extract_candidates_from_json_blob(text):
                found[item["href"]] = item
    return list(found.values())


def trigger_more_loading(page, page_delay_ms: int) -> None:
    for selector in [
        'button:has-text("加载更多")',
        'button:has-text("更多")',
        'div[role="button"]:has-text("加载更多")',
    ]:
        locator = page.locator(selector)
        count = min(locator.count(), 3)
        for idx in range(count):
            try:
                locator.nth(idx).click(timeout=800)
                page.wait_for_timeout(300)
            except Exception:
                continue

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(page_delay_ms)
    page.keyboard.press("PageDown")
    page.wait_for_timeout(300)
    page.keyboard.press("End")
    page.wait_for_timeout(300)


def normalize_candidates(items: list[dict]) -> list[dict]:
    out: dict[str, dict] = {}
    for item in items:
        url = canonical_url(item.get("href", ""))
        if not CONTENT_URL_RE.match(url):
            continue
        existing = out.get(url, {"href": url, "title": "", "context": ""})
        title = str(item.get("title", "")).strip()
        context = str(item.get("context", "")).strip()
        if title and len(title) > len(existing["title"]):
            existing["title"] = title[:240]
        if context and len(context) > len(existing["context"]):
            existing["context"] = context[:600]
        out[url] = existing
    return list(out.values())


def extract_search_results(page, max_items: int, max_scrolls: int, no_new_stop: int, page_delay_ms: int, network_candidates: dict[str, dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    no_new_rounds = 0
    last_height = 0
    for round_no in range(1, max_scrolls + 1):
        click_expand_buttons(page)
        trigger_more_loading(page, page_delay_ms)
        candidates = normalize_candidates(
            collect_result_candidates(page)
            + extract_candidates_from_html(page)
            + extract_embedded_state_candidates(page)
            + list(network_candidates.values())
        )
        new_items = 0
        for item in candidates:
            url = canonical_url(item.get("href", ""))
            if not CONTENT_URL_RE.match(url):
                continue
            if url in seen:
                continue
            title = str(item.get("title", "")).strip()
            context = str(item.get("context", "")).strip()
            snippet = context
            if title and snippet.startswith(title):
                snippet = snippet[len(title):].strip(" -|")
            seen[url] = {
                "url": url,
                "title": title[:240],
                "snippet": snippet[:600],
                "content_type": detect_content_type(url),
            }
            new_items += 1
            if len(seen) >= max_items:
                break
        print(f"Page {round_no}: + {new_items} new, total {len(seen)}")
        if len(seen) >= max_items:
            break
        no_new_rounds = 0 if new_items else no_new_rounds + 1
        page.mouse.wheel(0, 3600)
        page.wait_for_timeout(page_delay_ms)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height and no_new_rounds >= no_new_stop:
            break
        last_height = new_height
    return list(seen.values())


def extract_detail(page, item: dict, detail_delay_ms: int) -> dict:
    url = item["url"]
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(detail_delay_ms)
    detect_risk_or_login(page)
    click_expand_buttons(page)
    page.wait_for_timeout(500)
    content_type = item.get("content_type") or detect_content_type(url)

    if content_type == "answer":
        title = first_text(page, ["h1.QuestionHeader-title", "h1"]) or item.get("title", "")
        author = first_text(page, [".AuthorInfo-content .UserLink-link", ".AuthorInfo-content", "a[href*='/people/']"])
        content = longest_text(page, [".RichContent-inner .RichText.ztext", ".RichText.ztext", ".RichContent-inner", "article", "main"])
    elif content_type == "article":
        title = first_text(page, ["h1.Post-Title", "h1.ArticleItem-Title", "h1"]) or item.get("title", "")
        author = first_text(page, [".AuthorInfo-name", ".Post-Author .UserLink-link", "a[href*='/people/']"])
        content = longest_text(page, [".Post-RichTextContainer", ".RichText.ztext", "article", "main"])
    else:
        title = first_text(page, ["h1.QuestionHeader-title", "h1"]) or item.get("title", "")
        author = first_text(page, [".AuthorInfo-content .UserLink-link", ".AuthorInfo-content", "a[href*='/people/']"])
        content = longest_text(page, [".RichText.ztext", ".QuestionRichText", "article", "main"])

    if not content:
        raise RuntimeError(f"详情页未提取到正文：{url}")
    return {
        **item,
        "detail_title": title,
        "author": author,
        "content": content,
        "content_length": len(content),
    }


def write_outputs(run_dir: Path, keyword: str, search_url: str, rows: list[dict], stage1_total: int) -> None:
    payload = {
        "keyword": keyword,
        "search_url": search_url,
        "hydrated_count": len(rows),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": rows,
    }
    write_json(run_dir / "results.json", payload)
    write_csv(run_dir / "results.csv", rows, ["content_type", "title", "detail_title", "author", "url", "content_length", "snippet", "content"])
    write_markdown_summary(
        run_dir / "summary.md",
        f"知乎搜索全文 - {keyword}",
        [f"- 搜索链接: {search_url}", f"- 已收集摘要数量: {stage1_total}", f"- 已补全文数量: {len(rows)}"],
        rows,
        "content",
    )
    (run_dir / "article.html").write_text(
        build_simple_html(f"知乎搜索全文 - {keyword}", [f"搜索链接: {search_url}", f"已补全文数量: {len(rows)}"], rows, "content"),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    output_base = Path(args.out_dir).expanduser().resolve()
    output_base.mkdir(parents=True, exist_ok=True)
    run_dir = output_base / f"zhihu_search_{safe_name(args.keyword)}_500_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    search_url = make_search_url(args.keyword)
    print(f"Run directory: {run_dir}")
    print(f"Search URL: {search_url}")
    print(f"目标: 收集前 {args.max_items} 条")

    cookies = parse_cookie_string(args.cookie)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless, args=get_browser_args())
        context = browser.new_context(
            user_agent=args.user_agent,
            viewport={"width": 1440, "height": 1100},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            ignore_https_errors=True,
            extra_http_headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", "Upgrade-Insecure-Requests": "1"},
        )
        context.add_cookies(cookies)
        page = context.new_page()
        network_candidates: dict[str, dict] = {}

        def on_response(response) -> None:
            try:
                content_type = response.headers.get("content-type", "")
            except Exception:
                content_type = ""
            if "zhihu.com" not in response.url:
                return
            if "json" not in content_type and not any(token in response.url for token in ["/api/", "/graphql", "search_v3"]):
                return
            try:
                text = response.text()
            except Exception:
                return
            if not text or ("question" not in text and "zhuanlan" not in text):
                return
            for item in extract_candidates_from_json_blob(text):
                network_candidates[item["href"]] = item

        page.on("response", on_response)
        page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(args.page_delay_ms)
        detect_risk_or_login(page)
        stage1_items = extract_search_results(
            page,
            args.max_items,
            args.max_scrolls,
            args.no_new_stop,
            args.page_delay_ms,
            network_candidates,
        )
        if not stage1_items:
            raise RuntimeError("没有抓到任何搜索结果，请检查 Cookie 是否有效")
        write_json(run_dir / "results_stage1.json", {"keyword": args.keyword, "search_url": search_url, "results": stage1_items})
        print(f"成功收集 {len(stage1_items)} 条搜索结果（目标: {args.max_items}条）")
        print("开始第二阶段：逐条补全知乎全文")
        hydrated: list[dict] = []
        failed: list[dict] = []
        detail_page = context.new_page()
        total = len(stage1_items)
        for index, item in enumerate(stage1_items, start=1):
            print(f"[DETAIL] {index}/{total} {item['url']}")
            try:
                hydrated.append(extract_detail(detail_page, item, args.detail_delay_ms))
            except TimeoutError as exc:
                failed.append({**item, "error": f"timeout: {exc}"})
            except Exception as exc:
                failed.append({**item, "error": str(exc)})
        detail_page.close()
        page.close()
        context.close()
        browser.close()

    write_outputs(run_dir, args.keyword, search_url, hydrated, len(stage1_items))
    write_json(run_dir / "failed_details.json", failed)
    print(f"补全文完成: 成功 {len(hydrated)} 条, 失败 {len(failed)} 条")
    print(f"Results JSON: {run_dir / 'results.json'}")
    print(f"Article HTML: {run_dir / 'article.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
