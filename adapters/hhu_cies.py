"""Adapter for HHU Computer & Software College — 硕士生导师."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import (
    fetch,
    parse_profile_name,
    parse_webplus_auxiliary,
    parse_webplus_profile_content,
    parse_webplus_profile_email,
)

BASE = "https://cies.hhu.edu.cn"
LIST_URL = f"{BASE}/sssds/list.htm"


class HhuCiesAdapter:
    school_name = "河海大学计算机与软件学院（硕士生导师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/hhu_cies_teachers.md")
    output_json = Path("outputs/json/hhu_cies_teachers.json")
    exclude_emails: set[str] = set()

    def get_list_page_urls(self) -> list[str]:
        html = fetch(LIST_URL)
        pages = [LIST_URL]
        prefix = "sssds"
        base_dir = f"{BASE}/{prefix}/"
        nums = {int(n) for n in re.findall(rf"/{prefix}/list(\d+)\.htm", html)}
        for n in sorted(nums):
            pages.append(f"{base_dir}list{n}.htm")
        return pages

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        teachers = []
        pattern = re.compile(
            r"<span class=['\"]Article_Title['\"]>"
            r"<a href=['\"]([^'\"]+)['\"][^>]*title=['\"]([^'\"]+)['\"][^>]*>"
            r"([^<]+)</a></span>",
            re.I,
        )
        for m in pattern.finditer(html):
            href, name = m.group(1), m.group(2).strip()
            if not name or "page.htm" not in href:
                continue
            url = urljoin(BASE, href)
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": "硕士生导师",
                    "list_email": "",
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        aux = parse_webplus_auxiliary(html)
        title = aux.get("职称") or teacher.get("title", "")

        name_m = re.search(
            r"<span class=['\"]Article_Title['\"]>([^<]+)</span>", html, re.I
        )
        name = name_m.group(1).strip() if name_m else parse_profile_name(html)

        teacher.update(
            {
                "name": name or teacher["name"],
                "title": title,
                "email": parse_webplus_profile_email(
                    html, teacher["list_email"], self.exclude_emails
                ),
                "profile": parse_webplus_profile_content(html),
            }
        )
