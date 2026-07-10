"""Adapter for TJU SEEA — 通信工程系."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import (
    fetch,
    parse_meta_description,
    parse_profile_name,
    parse_vsb_profile_content,
    parse_vsb_profile_email,
)

BASE = "https://seea.tju.edu.cn"
LIST_URL = f"{BASE}/szdw/txgcx.htm"


def parse_tju_title(html: str, profile: str) -> str:
    for text in (profile, parse_meta_description(html)):
        if not text:
            continue
        m = re.search(r"职称[：:]\s*([^\n学通]+)", text)
        if m:
            title = m.group(1).strip()
            if title:
                return title
    return ""


class TjuTxgcxAdapter:
    school_name = "天津大学电气自动化与信息工程学院（通信工程系）"
    list_url = LIST_URL
    output_md = Path("outputs/md/tju_txgcx_teachers.md")
    output_json = Path("outputs/json/tju_txgcx_teachers.json")
    exclude_emails = {"auto@tju.edu.cn"}

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        teachers = []
        pattern = re.compile(
            r"<li>\s*<a\s+href=['\"]([^'\"]+)['\"][^>]*title=['\"]([^'\"]+)['\"][^>]*>"
            r"([^<]+)</a>\s*</li>",
            re.I | re.S,
        )
        for m in pattern.finditer(html):
            href, name = m.group(1), m.group(2).strip()
            if "/info/" not in href:
                continue
            url = urljoin(LIST_URL, href)
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": "",
                    "list_email": "",
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        profile = parse_vsb_profile_content(html)
        page_title = parse_profile_name(html)
        name = page_title.split("-")[0].strip() if page_title else teacher["name"]

        teacher.update(
            {
                "name": name or teacher["name"],
                "title": parse_tju_title(html, profile),
                "email": parse_vsb_profile_email(
                    html, teacher["list_email"], self.exclude_emails
                ),
                "profile": profile or "（主页暂无详细介绍）",
            }
        )
