"""Shared utilities for faculty scraping."""

import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def fetch(url: str) -> str:
    if url.startswith("http://faculty.nuaa.edu.cn"):
        url = "https://" + url[len("http://") :]
    url = quote_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def quote_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            quote(parts.path, safe="/%~"),
            quote(parts.query, safe="=&?/%~:+"),
            parts.fragment,
        )
    )


def strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"</div>", "\n", text, flags=re.I)
    text = re.sub(r"</tr>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    for src, dst in [
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&#8203;", ""),
        ("\u3000", " "),
        ("\xa0", " "),
    ]:
        text = text.replace(src, dst)
    text = unescape(text)
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def first_email(text: str, exclude=None) -> str:
    exclude = {e.lower() for e in (exclude or set())}
    for m in EMAIL_RE.finditer(text):
        email = m.group(0)
        if email.lower() not in exclude:
            return email
    return ""


def parse_meta_description(html: str) -> str:
    m = re.search(
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']',
        html,
        re.I,
    )
    if not m:
        m = re.search(
            r'<META\s+Name=["\']description["\']\s+Content=["\']([^"\']*)["\']',
            html,
        )
    return m.group(1).strip() if m else ""


def parse_profile_name(html: str) -> str:
    m = re.search(r"<title>([^<-]+)", html, re.I)
    return m.group(1).strip() if m else ""


def parse_vsb_profile_content(html: str) -> str:
    start_m = re.search(r'<p class="vsbcontent_start">(.*?)</p>', html, re.I | re.S)
    if start_m:
        text = strip_html(start_m.group(1))
        if text:
            return text

    content_m = re.search(
        r'<div[^>]*class=["\'][^"\']*v_news_content[^"\']*["\'][^>]*>(.*)',
        html,
        re.I | re.S,
    )
    if content_m:
        chunk = content_m.group(1)
        end = chunk.find('<div id="div_vote_id"')
        if end == -1:
            end = chunk.find("</div></div>")
        if end != -1:
            chunk = chunk[:end]
        text = strip_html(chunk)
        if text:
            return text

    detail_m = re.search(r'<div class="detail2_t_r">\s*(.*?)\s*</div>', html, re.I | re.S)
    detail_text = strip_html(detail_m.group(1)) if detail_m else ""
    if detail_text:
        return detail_text

    meta = parse_meta_description(html)
    if meta and not meta.startswith("通讯地址"):
        return meta
    return ""


def parse_vsb_profile_email(html: str, list_email: str, exclude_emails=None) -> str:
    exclude = exclude_emails or set()
    if list_email:
        return list_email

    meta = parse_meta_description(html)
    email = first_email(meta, exclude=exclude)
    if email:
        return email

    detail_m = re.search(r'<div class="detail2_t_r">\s*(.*?)\s*</div>', html, re.I | re.S)
    if detail_m:
        email = first_email(strip_html(detail_m.group(1)), exclude=exclude)
        if email:
            return email

    content_m = re.search(
        r'<div[^>]*class=["\'][^"\']*v_news_content[^"\']*["\'][^>]*>(.*)',
        html,
        re.I | re.S,
    )
    if content_m:
        email = first_email(strip_html(content_m.group(1)[:5000]), exclude=exclude)
        if email:
            return email

    return ""


def parse_webplus_auxiliary(html: str) -> dict[str, str]:
    """Parse Webplus/Sudy Article_AuxiliaryTitle fields (职称, 邮箱等)."""
    m = re.search(
        r"<span class=['\"]Article_AuxiliaryTitle['\"][^>]*>(.*?)</span>",
        html,
        re.I | re.S,
    )
    block = m.group(1) if m else html
    fields: dict[str, str] = {}
    for label in ("职称", "职务", "联系电话", "电子邮箱", "Email", "email"):
        fm = re.search(rf"{label}[：:]\s*([^<\n]+)", block, re.I)
        if fm:
            val = strip_html(fm.group(1)).strip()
            if val:
                fields[label] = val
    return fields


def parse_webplus_profile_content(html: str) -> str:
    footer_markers = (
        "版权所有",
        "技术支持",
        "联系电话：025",
        "欢迎第",
        "微信二维码",
    )

    def trim_footer(text: str) -> str:
        for marker in footer_markers:
            idx = text.find(marker)
            if idx != -1:
                text = text[:idx]
        return text.strip()

    for pattern in [
        r"<div class=['\"]Article_Content['\"][^>]*>(.*)",
        r"<div class=['\"]wp_articlecontent['\"][^>]*>(.*)",
    ]:
        m = re.search(pattern, html, re.I | re.S)
        if m:
            chunk = m.group(1)
            for stop in ("<div frag=", "<footer", "<div class=\"foot"):
                end = chunk.find(stop)
                if end != -1:
                    chunk = chunk[:end]
            text = trim_footer(strip_html(chunk))
            if text:
                return text
    meta = parse_meta_description(html)
    return trim_footer(meta) if meta else ""


def parse_tsites_profile_name(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    if m:
        title = m.group(1).strip()
        m2 = re.search(r"主页平台管理系统\s*([^\-<]+?)(?:--|$)", title)
        if m2:
            name = m2.group(1).strip()
            if name:
                return name
    m = re.search(r"<title>[^<]*?\s+([^<\s\-]+)--", html)
    if m:
        return m.group(1).strip()
    name = parse_profile_name(html)
    return re.sub(r"^南京航空航天大学主页平台管理系统\s*", "", name).strip()


def parse_tsites_profile_title(html: str) -> str:
    for pattern in [
        r"职称[：:]\s*([^<\n]+)",
        r"，(教授|副教授|讲师|研究员|副研究员|助理研究员|高级工程师)",
    ]:
        m = re.search(pattern, html)
        if m:
            return strip_html(m.group(1)).strip()
    return ""


def parse_tsites_info_fields(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    labels = (
        "招生学科专业",
        "所在单位",
        "办公地点",
        "毕业院校",
        "学历",
        "学位",
        "性别",
    )
    for label in labels:
        m = re.search(rf"<p>{label}[：:]\s*(.*?)</p>", html, re.I | re.S)
        if not m:
            m = re.search(rf"{label}[：:]\s*([^<\n]+)", html, re.I)
        if m:
            val = strip_html(m.group(1))
            if val and "暂无" not in val:
                fields[label] = val
    return fields


def parse_tsites_profile_content(html: str) -> str:
    parts = []
    info = parse_tsites_info_fields(html)
    for label in ("招生学科专业", "所在单位", "办公地点", "毕业院校", "学历", "学位"):
        if label in info:
            parts.append(f"{label}：{info[label]}")

    for pattern in [
        r'<div class="t_grjj_nr">\s*(.*?)\s*</div>',
        r'<div class="cont profile">\s*(.*?)\s*</div>',
    ]:
        m = re.search(pattern, html, re.I | re.S)
        if m:
            text = strip_html(m.group(1))
            if text and "暂无内容" not in text:
                parts.append(text)
                break

    meta = parse_meta_description(html)
    if meta and len(parts) <= 1:
        parts.append(meta)
    return "\n\n".join(parts)


def parse_tsites_profile_email(html: str, list_email: str) -> str:
    if list_email:
        return list_email
    # 邮箱常被 _tsites_encrypt_field 加密，无法直接解析
    m = re.search(r"电子邮箱[：:]\s*([^<\n]+)", html, re.I)
    if m:
        email = first_email(strip_html(m.group(1)))
        if email:
            return email
    return first_email(html[:10000])


def parse_webplus_profile_email(html: str, list_email: str, exclude_emails=None) -> str:
    exclude = exclude_emails or set()
    if list_email:
        return list_email
    aux = parse_webplus_auxiliary(html)
    for key in ("电子邮箱", "Email", "email"):
        if key in aux:
            email = first_email(aux[key], exclude=exclude)
            if email:
                return email
    return first_email(html[:8000], exclude=exclude)


def discover_reverse_pagination(list_url: str, html: str) -> list[str]:
    """VSB reverse-numbered pages: list.htm + list/N.htm … list/1.htm."""
    pages = [list_url]
    base_dir = list_url.rsplit("/", 1)[0] + "/"
    prefix = Path(urlparse(list_url).path).stem  # e.g. qtjs or zzjs
    nums = {int(n) for n in re.findall(rf'href=["\']{prefix}/(\d+)\.htm["\']', html, re.I)}
    for n in sorted(nums, reverse=True):
        pages.append(f"{base_dir}{prefix}/{n}.htm")
    return pages


def teacher_to_markdown(t: dict) -> str:
    lines = [
        f"## {t['name']}",
        "",
        f"- **网址**: {t['url']}",
        f"- **姓名**: {t['name']}",
        f"- **邮箱**: {t.get('email') or '（未提供）'}",
        f"- **职称**: {t.get('title') or '（未提供）'}",
    ]
    if t.get("role"):
        lines.append(f"- **导师类型**: {t['role']}")
    if t.get("disciplines"):
        lines.append(f"- **招生学科**: {t['disciplines']}")
    if t.get("categories"):
        lines.append(f"- **所属目录**: {'、'.join(t['categories'])}")
    lines.extend(
        [
            "",
            "### 个人信息",
            "",
            t.get("profile") or "（暂无详细介绍）",
            "",
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def save_results(
    *,
    school_name: str,
    list_url: str,
    teachers: list[dict],
    output_md: Path,
    output_json: Path,
) -> None:
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    md_parts = [
        f"# {school_name} — 教师信息",
        "",
        f"数据来源: [{list_url}]({list_url})",
        "",
        f"共 {len(teachers)} 位教师。",
        "",
        "---",
        "",
    ]
    for t in teachers:
        md_parts.append(teacher_to_markdown(t))

    output_md.write_text("\n".join(md_parts), encoding="utf-8")
    output_json.write_text(
        json.dumps(teachers, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_scraper(adapter, delay: float = 0.25) -> list[dict]:
    print(f"正在抓取: {adapter.school_name}")
    print("正在获取教师列表页...")
    list_pages = adapter.get_list_page_urls()
    print(f"共 {len(list_pages)} 个列表页")

    teachers: list[dict] = []
    index: dict[str, int] = {}
    key_fn = getattr(adapter, "dedup_key", None)
    for page_url in list_pages:
        print(f"  解析: {page_url}")
        html = fetch(page_url)
        for t in adapter.extract_teachers_from_list(html):
            key = key_fn(t) if key_fn else (t.get("url") or t.get("dsbh") or t["name"])
            if key in index:
                existing = teachers[index[key]]
                for cat in t.get("categories") or []:
                    cats = existing.setdefault("categories", [])
                    if cat not in cats:
                        cats.append(cat)
            else:
                index[key] = len(teachers)
                teachers.append(t)
        time.sleep(0.2)

    fetch_profiles = getattr(adapter, "fetch_profiles", True)
    if fetch_profiles:
        print(f"共发现 {len(teachers)} 位教师，开始抓取详情页...")
    else:
        print(f"共发现 {len(teachers)} 位教师，跳过详情页抓取...")

    def enrich_teacher(i: int, t: dict) -> None:
        print(f"  [{i}/{len(teachers)}] {t['name']}")
        try:
            if not fetch_profiles:
                t.setdefault("email", t.get("list_email", ""))
                t["profile"] = t.get("profile") or "（未抓取个人主页）"
            elif not t.get("url"):
                t.setdefault("email", t.get("list_email", ""))
                t["profile"] = t.get("profile") or "（无个人主页链接）"
            else:
                html = fetch(t["url"])
                adapter.parse_profile(html, t)
        except Exception as exc:
            print(f"    失败: {exc}")
            t.setdefault("email", t.get("list_email", ""))
            t["profile"] = t.get("profile") or f"（抓取失败: {exc}）"

    profile_workers = int(getattr(adapter, "profile_workers", 1))
    if fetch_profiles and profile_workers > 1:
        with ThreadPoolExecutor(max_workers=profile_workers) as executor:
            futures = [
                executor.submit(enrich_teacher, i, t)
                for i, t in enumerate(teachers, 1)
            ]
            for future in as_completed(futures):
                future.result()
    else:
        for i, t in enumerate(teachers, 1):
            enrich_teacher(i, t)
            if fetch_profiles:
                time.sleep(delay)

    save_results(
        school_name=adapter.school_name,
        list_url=adapter.list_url,
        teachers=teachers,
        output_md=adapter.output_md,
        output_json=adapter.output_json,
    )
    print(f"\n完成！已保存:")
    print(f"  - {adapter.output_md.resolve()}")
    print(f"  - {adapter.output_json.resolve()}")
    return teachers
