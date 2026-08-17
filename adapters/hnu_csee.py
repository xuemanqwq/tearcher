"""Adapter for all HNU CSEE teacher category lists."""

import re
import time
from pathlib import Path
from urllib.parse import urljoin

from core import first_email, parse_profile_name, strip_html

BASE = "https://csee.hnu.edu.cn"
LIST_URL = f"{BASE}/xygk/szll.htm"

LIST_PAGES = [
    ("教授", f"{BASE}/teacher/syjs/10"),
    ("副教授", f"{BASE}/teacher/syjs/25"),
    ("助理教授", f"{BASE}/teacher/syjs/40"),
    ("教授", f"{BASE}/teacher/syjs/15"),
    ("副教授", f"{BASE}/teacher/syjs/30"),
    ("讲师", f"{BASE}/teacher/syjs/45"),
    ("正高", f"{BASE}/teacher/syjs/20"),
    ("副高", f"{BASE}/teacher/syjs/35"),
    ("中级", f"{BASE}/teacher/syjs/50"),
    ("特聘研究员", f"{BASE}/teacher/syjs/60"),
    ("特聘副研究员", f"{BASE}/teacher/syjs/65"),
    ("特聘助理研究员", f"{BASE}/teacher/syjs/70"),
]


def clean_text(text: str) -> str:
    text = (text or "").replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def normalize_contact(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\s*(?:\[AT\]|\[at\]|\(AT\)|\(at\)|＠)\s*", "@", text)
    text = re.sub(r"\s*(?:\[DOT\]|\[dot\]|\(DOT\)|\(dot\))\s*", ".", text)
    return text


def split_name_title(cell_html: str) -> tuple[str, str]:
    text = strip_html(cell_html).replace("\r", "\n")
    parts = [clean_text(part) for part in re.split(r"\s+", text) if clean_text(part)]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if parts:
        return parts[0], ""
    return "", ""


def extract_list_table_rows(html: str) -> list[tuple[str, str, str, str, str]]:
    rows: list[tuple[str, str, str, str, str]] = []
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S)
    for tr in trs:
        if "/people/" not in tr:
            continue
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.I | re.S)
        if len(cells) < 4:
            continue
        link_m = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']*)["\']', cells[0], re.I | re.S)
        if not link_m:
            link_m = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', cells[0], re.I | re.S)
        if not link_m:
            continue
        href = link_m.group(1)
        link_title = link_m.group(2) if link_m.lastindex and link_m.lastindex >= 2 else ""
        name, title = split_name_title(cells[1])
        direction = clean_text(strip_html(cells[2]))
        contact = normalize_contact(strip_html(cells[3]))
        if not direction and link_title:
            direction = clean_text(link_title)
        if name:
            rows.append((href, name, title, direction, contact))
    return rows


def extract_vsb_content(html: str) -> str:
    m = re.search(r'<div[^>]+id=["\']vsb_content["\'][^>]*>(.*?)(?:</div>\s*<DIV class=["\']fw-mt)', html, re.I | re.S)
    if not m:
        m = re.search(r'<div[^>]+id=["\']vsb_content["\'][^>]*>(.*?)</div>\s*</div>', html, re.I | re.S)
    if m:
        text = strip_html(m.group(1))
        if text:
            return text
    return strip_html(html)


def field_from_profile(text: str, label: str) -> str:
    patterns = [
        rf"{label}[：:]\s*([^\n]+)",
        rf"{label}\s*([^\n]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return clean_text(m.group(1))
    return ""


def direction_from_profile(text: str) -> str:
    value = field_from_profile(text, "研究方向")
    if value:
        return value
    for pattern in [
        r"主要从事([^。；;\n]+?)研究",
        r"研究领域涉及([^。；;\n]+)",
        r"研究方向为([^。；;\n]+)",
    ]:
        m = re.search(pattern, clean_text(text))
        if m:
            value = clean_text(m.group(1)).strip("：:，, ")
            if 2 <= len(value) <= 100:
                return value
    return ""


class HnuCseeAdapter:
    school_name = "湖南大学信息科学与工程学院（全部教师分类）"
    list_url = LIST_URL
    output_md = Path("outputs/md/hnu_csee_teachers.md")
    output_json = Path("outputs/json/hnu_csee_teachers.json")
    output_html_dir = Path("outputs/html/hnu_csee_lists")
    profile_html_dir = Path("outputs/html/hnu_csee_profiles")
    profile_workers = 8

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return [url for _, url in LIST_PAGES]

    def page_category(self, page_url: str) -> str:
        for category, url in LIST_PAGES:
            if page_url == url:
                return category
        return ""

    def fetch_list_page(self, page_url: str) -> str:
        from core import fetch

        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        key = page_url.rstrip("/").rsplit("/", 1)[-1]
        cache_path = self.output_html_dir / f"{key}.html"
        last_error = None
        for _ in range(3):
            try:
                html = fetch(page_url)
                cache_path.write_text(html, encoding="utf-8")
                return html
            except Exception as exc:
                last_error = exc
                time.sleep(1.5)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8")
        raise last_error

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        page_category = ""
        m = re.search(r'<div[^>]+class=["\']tea_title["\'][^>]*>(.*?)</div>', html, re.I | re.S)
        if m:
            page_category = clean_text(strip_html(m.group(1))).split()[0]

        teachers = []
        for href, name, title, direction, contact in extract_list_table_rows(html):
            title = title or page_category
            email = first_email(contact)
            teachers.append(
                {
                    "url": urljoin(LIST_URL, href),
                    "name": name,
                    "title": title,
                    "list_email": email,
                    "email": email,
                    "role": title or "教师",
                    "disciplines": direction,
                    "categories": [page_category, title] if page_category and page_category != title else ([title] if title else ["教师"]),
                    "contact": contact,
                    "profile_source": "列表页",
                    "profile": "\n".join(
                        line
                        for line in [
                            f"职称：{title}" if title else "",
                            f"研究方向：{direction}" if direction else "",
                            f"联系方式：{contact}" if contact else "",
                        ]
                        if line
                    ),
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_html_dir.joinpath(f"{safe_filename(teacher['name'])}.html").write_text(
            html, encoding="utf-8"
        )

        profile = extract_vsb_content(html)
        name = clean_text(parse_profile_name(html).split("-")[0]) or teacher["name"]
        direction = teacher.get("disciplines") or direction_from_profile(profile)
        email = teacher.get("list_email") or first_email(normalize_contact(profile))
        contact = teacher.get("contact") or field_from_profile(profile, "联系方式")

        lines = []
        if teacher.get("title"):
            lines.append(f"职称：{teacher['title']}")
        if direction:
            lines.append(f"研究方向：{direction}")
        if contact:
            lines.append(f"联系方式：{contact}")
        if profile:
            lines.append(profile)

        teacher.update(
            {
                "name": name,
                "email": email,
                "disciplines": direction,
                "profile_source": "详情页",
                "profile": "\n".join(lines) or profile,
            }
        )
