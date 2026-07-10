"""Adapter for DLUT School of Information and Communication Engineering faculty."""

import re
from pathlib import Path
from urllib.parse import urlparse

from core import (
    first_email,
    parse_tsites_profile_content,
    strip_html,
)

LIST_URL = "https://ice.dlut.edu.cn/szdw/szdw_azc.htm"

TITLE_KEYWORDS = (
    "正高级实验师",
    "高级工程师",
    "助理教授",
    "副研究员",
    "副教授",
    "研究员",
    "教授",
    "讲师",
    "工程师",
)


def normalize_url(href: str) -> str:
    href = href.strip()
    return "" if not href or href == "#" else href


def parse_title(text: str, category: str) -> str:
    for title in TITLE_KEYWORDS:
        if title in text:
            return title
    for title in TITLE_KEYWORDS:
        if title in category:
            return title
    return category


def parse_role(text: str, category: str) -> str:
    roles = []
    for role in ("博士生导师", "硕士生导师"):
        if role in text:
            roles.append(role)
    if category == "兼职导师":
        roles.append("兼职导师")
    return "、".join(dict.fromkeys(roles))


def parse_profile_from_list(*, category: str, raw_title: str, email: str, research: str) -> str:
    parts = [f"所属分类：{category}"]
    if raw_title:
        parts.append(f"职称/身份：{raw_title}")
    if email:
        parts.append(f"电子邮件：{email}")
    if research:
        parts.append(research)
    return "\n".join(parts)


def parse_dlut_profile_name(html: str, fallback: str) -> str:
    m = re.search(r"<title>大连理工大学主页平台管理系统\s+(.+?)\s+首页", html, re.I | re.S)
    if m:
        return strip_html(m.group(1)) or fallback
    m = re.search(r"<title>([^<]+)</title>", html, re.I | re.S)
    if m:
        title = strip_html(m.group(1))
        if title:
            return title.split("-")[0].replace("欢迎访问", "").replace("教授主页", "").strip() or fallback
    return fallback


def split_sections(html: str) -> list[tuple[str, str]]:
    markers = list(re.finditer(r"<h2>([^<]+)</h2><br\s*/?>", html, re.I))
    sections = []
    for i, marker in enumerate(markers):
        category = strip_html(marker.group(1))
        if not category or len(category) > 20:
            continue
        end = markers[i + 1].start() if i + 1 < len(markers) else len(html)
        sections.append((category, html[marker.end() : end]))
    return sections


def parse_items_from_section(category: str, html: str) -> list[dict]:
    teachers = []
    pattern = re.compile(
        r'<div\s+class=["\']item["\']>\s*'
        r'<a\s+href=["\']([^"\']*)["\'][^>]*>(.*?)'
        r'<div\s+class=["\']cb["\']></div>\s*</a>\s*</div>',
        re.I | re.S,
    )
    for m in pattern.finditer(html):
        href, block = m.group(1), m.group(2)
        name_m = re.search(r"<h2>\s*<span>(.*?)</span>\s*</h2>", block, re.I | re.S)
        if not name_m:
            continue
        name = strip_html(name_m.group(1))
        rows = [strip_html(row) for row in re.findall(r"<p>(.*?)</p>", block, re.I | re.S)]
        rows = [row for row in rows if row and row != "研究方向:"]
        raw_title = rows[0] if rows else ""
        email = first_email("\n".join(rows))
        research = ""
        for row in rows[1:]:
            if "@" not in row:
                research = row
                break
        teachers.append(
            {
                "url": normalize_url(href),
                "name": name,
                "title": parse_title(raw_title, category),
                "list_email": email,
                "email": email,
                "role": parse_role(raw_title, category),
                "categories": [category],
                "profile": parse_profile_from_list(
                    category=category,
                    raw_title=raw_title,
                    email=email,
                    research=research,
                ),
            }
        )
    return teachers


class DlutIceAdapter:
    school_name = "大连理工大学信息与通信工程学院"
    list_url = LIST_URL
    output_md = Path("outputs/md/dlut_ice_teachers.md")
    output_json = Path("outputs/json/dlut_ice_teachers.json")

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        teachers = []
        for category, section in split_sections(html):
            teachers.extend(parse_items_from_section(category, section))
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        url_host = urlparse(teacher.get("url", "")).netloc.lower()
        email = first_email(html) or teacher.get("email", "")

        if "faculty.dlut.edu.cn" not in url_host:
            teacher["email"] = teacher.get("email") or email
            return

        detail = parse_tsites_profile_content(html)
        parts = [teacher.get("profile", "")]
        if detail and detail not in parts[0]:
            parts.extend(["", "主页补充信息：", detail])

        teacher.update(
            {
                "name": parse_dlut_profile_name(html, teacher["name"]),
                "email": teacher.get("email") or email,
                "profile": "\n".join(part for part in parts if part is not None).strip(),
            }
        )
