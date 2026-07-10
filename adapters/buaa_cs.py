"""Adapter for BUAA Computer Science faculty list."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import (
    discover_reverse_pagination,
    fetch,
    parse_profile_name,
    parse_vsb_profile_content,
    parse_vsb_profile_email,
)

BASE = "https://scse.buaa.edu.cn"
LIST_URL = f"{BASE}/szdw/qtjs.htm"


class BuaaCsAdapter:
    school_name = "北京航空航天大学计算机学院"
    list_url = LIST_URL
    output_md = Path("outputs/md/buaa_cs_teachers.md")
    output_json = Path("outputs/json/buaa_cs_teachers.json")
    exclude_emails = {"scse@buaa.edu.cn"}

    def get_list_page_urls(self) -> list[str]:
        html = fetch(LIST_URL)
        return discover_reverse_pagination(LIST_URL, html)

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        teachers = []
        li_pattern = re.compile(
            r'<li>\s*<a\s+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\'][^>]*>(.*?)</a>\s*</li>',
            re.I | re.S,
        )
        for m in li_pattern.finditer(html):
            href, name, block = m.group(1), m.group(2).strip(), m.group(3)
            if "/info/" not in href:
                continue
            url = urljoin(f"{BASE}/szdw/", href)
            title_m = re.search(r"<span>([^<]+)</span>", block)
            title = title_m.group(1).strip() if title_m else ""
            email_m = re.search(r'<p class="yx">([^<]*)</p>', block, re.I)
            email = email_m.group(1).strip() if email_m else ""
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": title,
                    "list_email": email,
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        title_m = re.search(r"<h2>\s*([^<]+?)\s*</h2>", html, re.I | re.S)
        profile_title = teacher["title"]
        if title_m:
            t = title_m.group(1).strip()
            if t and t not in ("全体教师", "师资队伍"):
                profile_title = t

        teacher.update(
            {
                "name": parse_profile_name(html) or teacher["name"],
                "title": profile_title,
                "email": parse_vsb_profile_email(
                    html, teacher["list_email"], self.exclude_emails
                ),
                "profile": parse_vsb_profile_content(html),
            }
        )
