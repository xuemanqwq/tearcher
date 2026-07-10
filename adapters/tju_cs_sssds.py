"""Adapter for TJU CS master's supervisor list."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import (
    parse_meta_description,
    parse_profile_name,
    parse_vsb_profile_content,
    parse_vsb_profile_email,
    strip_html,
)

LIST_URL = "https://cs.tju.edu.cn/jyjx/yjsjy/sssds.htm"


def parse_tju_cs_profile_content(html: str) -> str:
    """Extract the teacher body from both old cic.tju.edu.cn and new cs.tju.edu.cn templates."""
    m = re.search(
        r'<div[^>]*class=["\']v_news_content["\'][^>]*>(.*?)</div>\s*</div>',
        html,
        re.I | re.S,
    )
    if m:
        text = strip_html(m.group(1))
        if text:
            return text

    text = parse_vsb_profile_content(html)
    if text:
        return text

    return parse_meta_description(html)


def parse_labeled_value(text: str, label: str) -> str:
    m = re.search(rf"{re.escape(label)}\s*[:：]\s*([^\n]+)", text)
    return m.group(1).strip() if m else ""


def parse_title(profile: str, html: str) -> str:
    for text in (profile, parse_meta_description(html)):
        title = parse_labeled_value(text, "职称")
        if title:
            return title
    return ""


def parse_role(profile: str, html: str) -> str:
    for text in (profile, parse_meta_description(html)):
        role = parse_labeled_value(text, "导师类型")
        if role:
            return role
    return "硕士生导师"


class TjuCsSssdsAdapter:
    school_name = "天津大学计算机科学与技术学院（硕士生导师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/tju_cs_sssds_teachers.md")
    output_json = Path("outputs/json/tju_cs_sssds_teachers.json")
    exclude_emails = {"cs_tju@tju.edu.cn", "coic@tju.edu.cn"}

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        teachers = []
        pattern = re.compile(
            r'<div\s+class=["\']name-item["\']>\s*'
            r'<a\s+href=["\']([^"\']*)["\'][^>]*>(.*?)</a>\s*</div>',
            re.I | re.S,
        )
        for m in pattern.finditer(html):
            href, name = m.group(1).strip(), strip_html(m.group(2))
            if not name:
                continue
            url = "" if not href or href == "#" else urljoin(LIST_URL, href)
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": "",
                    "list_email": "",
                    "role": "硕士生导师",
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        profile = parse_tju_cs_profile_content(html)
        teacher.update(
            {
                "name": parse_profile_name(html) or teacher["name"],
                "title": parse_title(profile, html),
                "email": parse_vsb_profile_email(
                    html, teacher["list_email"], self.exclude_emails
                ),
                "role": parse_role(profile, html),
                "profile": profile or "（主页暂无详细介绍）",
            }
        )
