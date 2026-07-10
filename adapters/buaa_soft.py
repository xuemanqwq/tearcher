"""Adapter for BUAA School of Software faculty — all 师资队伍 categories."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import (
    fetch,
    first_email,
    parse_meta_description,
    parse_profile_name,
    strip_html,
)

BASE = "https://soft.buaa.edu.cn"
LIST_URL = f"{BASE}/tu-list.jsp?urltype=tree.TreeTempUrl&wbtreeid=1323"

# Right sidebar categories (all must be scraped)
CATEGORIES = [
    ("杰出人才", "tu-list.jsp", 1323),
    ("教授(研究员)", "tu-list-1.jsp", 1224),
    ("副教授(副研究员)", "tu-list-1.jsp", 1262),
    ("助理教授(讲师)", "tu-list-1.jsp", 1263),
    ("博士生导师", "tu-list-bodao.jsp", 1329),
    ("硕士生导师", "tu-list-1.jsp", 1330),
    ("博士后", "tu-list-1.jsp", 1292),
    ("党政管理人员", "tu-list-1.jsp", 1306),
    ("返聘/退休", "tu-list-1.jsp", 1302),
]

PROFILE_LINK = re.compile(
    r'<a href="((?:teachershouw|ldjsxqy_wzc)\.jsp\?[^"]+)"[^>]*title="([^"]+)"',
    re.I,
)


def category_url(jsp: str, wbtreeid: int) -> str:
    return f"{BASE}/{jsp}?urltype=tree.TreeTempUrl&wbtreeid={wbtreeid}"


def parse_list_category(html: str) -> str:
    m = re.search(r"<title>([^<-]+)", html, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'<h1 class="margin_auto_1">\s*([^<]+)', html, re.I | re.S)
    return m.group(1).strip() if m else ""


def extract_teachers_from_list(html: str, category: str = "") -> list[dict]:
    category = category or parse_list_category(html)
    teachers = []
    for href, name in PROFILE_LINK.findall(html):
        name = name.strip()
        if not name:
            continue
        url = urljoin(BASE + "/", href)
        teachers.append(
            {
                "url": url,
                "name": name,
                "title": "",
                "list_email": "",
                "categories": [category],
            }
        )
    return teachers


def parse_buaa_soft_fields(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in re.finditer(r"<dd><font>([^<]*)</font>\s*([^<]*)</dd>", html, re.I | re.S):
        label = re.sub(r"\s+", "", strip_html(m.group(1))).strip("：:")
        val = strip_html(m.group(2)).strip()
        if label and val:
            fields[label] = val
    return fields


def parse_buaa_soft_name(html: str, fallback: str) -> str:
    m = re.search(r'<div class="ll"[^>]*>([^<]+)', html, re.I)
    if m:
        name = m.group(1).strip()
        if name:
            return name
    m = re.search(r'<meta name="pageTitle" content="([^"]+)"', html, re.I)
    if m:
        return m.group(1).strip()
    title = parse_profile_name(html)
    if title:
        return title.split("-")[0].strip()
    return fallback


def parse_buaa_soft_profile_content(html: str) -> str:
    footer_markers = ("Copyright©", "招生信箱", "IT咨询", "xinxihua@buaa.edu.cn")
    for pattern in [
        r"<div class=['\"]fl02['\"][^>]*>(.*?)</form>",
        r"id=['\"]vsb_content[^'\"]*['\"][^>]*>(.*)",
        r"<div class=['\"]ar_article['\"][^>]*>(.*?)</div>\s*<section",
    ]:
        m = re.search(pattern, html, re.I | re.S)
        if not m:
            continue
        text = strip_html(m.group(1))
        for marker in footer_markers:
            idx = text.find(marker)
            if idx != -1:
                text = text[:idx]
        text = text.strip()
        if text and len(text) > 20:
            return text
    meta = parse_meta_description(html)
    return meta.strip() if meta else ""


class BuaaSoftAdapter:
    school_name = "北京航空航天大学软件学院"
    list_url = LIST_URL
    output_md = Path("outputs/md/buaa_soft_teachers.md")
    output_json = Path("outputs/json/buaa_soft_teachers.json")
    exclude_emails = {
        "softzhaosheng@buaa.edu.cn",
        "xinxihua@buaa.edu.cn",
        "auto@buaa.edu.cn",
    }

    def dedup_key(self, teacher: dict) -> str:
        name = re.sub(r"（[^）]*）", "", teacher["name"]).strip()
        return name or teacher.get("url", "")

    def get_list_page_urls(self) -> list[str]:
        return [category_url(jsp, wid) for _, jsp, wid in CATEGORIES]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        category = parse_list_category(html)
        return extract_teachers_from_list(html, category)

    def parse_profile(self, html: str, teacher: dict) -> None:
        fields = parse_buaa_soft_fields(html)
        profile = parse_buaa_soft_profile_content(html)
        email = fields.get("电子信箱") or teacher.get("list_email", "")
        if not email:
            email = first_email(profile, exclude=self.exclude_emails)

        teacher.update(
            {
                "name": parse_buaa_soft_name(html, teacher["name"]),
                "title": fields.get("职称", teacher.get("title", "")),
                "email": email,
                "profile": profile or "（主页暂无详细介绍）",
            }
        )
