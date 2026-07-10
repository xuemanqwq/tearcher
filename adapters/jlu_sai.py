"""Adapter for JLU School of Artificial Intelligence faculty list."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import (
    discover_reverse_pagination,
    fetch,
    parse_profile_name,
    parse_vsb_profile_content,
    parse_vsb_profile_email,
    strip_html,
)

BASE = "https://sai.jlu.edu.cn"
LIST_URL = f"{BASE}/szdu/zzjs.htm"


def _info_value(block: str, label: str) -> str:
    m = re.search(
        rf'<p class="info[^"]*">\s*<span>{label}[：:]\s*</span>(.*?)</p>',
        block,
        re.I | re.S,
    )
    return strip_html(m.group(1)) if m else ""


class JluSaiAdapter:
    school_name = "吉林大学人工智能学院"
    list_url = LIST_URL
    output_md = Path("outputs/md/jlu_sai_teachers.md")
    output_json = Path("outputs/json/jlu_sai_teachers.json")
    exclude_emails = {"sai@jlu.edu.cn"}

    def get_list_page_urls(self) -> list[str]:
        html = fetch(LIST_URL)
        return discover_reverse_pagination(LIST_URL, html)

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        teachers = []
        li_pattern = re.compile(r"<li>(.*?)</li>", re.I | re.S)
        for m in li_pattern.finditer(html):
            block = m.group(1)
            if 'class="name"' not in block or "/info/" not in block:
                continue
            name_m = re.search(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*class=["\']name["\'][^>]*>([^<]+)</a>',
                block,
                re.I,
            )
            if not name_m:
                continue
            href, name = name_m.group(1), name_m.group(2).strip()
            url = urljoin(f"{BASE}/szdu/", href)
            title = _info_value(block, "职称")
            email = _info_value(block, "email")
            if not email:
                email = _info_value(block, "Email")
            research = _info_value(block, "研究方向")
            phd_school = _info_value(block, "博士毕业院校")

            list_profile_parts = []
            if research:
                list_profile_parts.append(f"研究方向：{research}")
            if phd_school:
                list_profile_parts.append(f"博士毕业院校：{phd_school}")

            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": title,
                    "list_email": email,
                    "list_profile": "\n".join(list_profile_parts),
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        detail = parse_vsb_profile_content(html)
        parts = []
        if teacher.get("list_profile"):
            parts.append(teacher["list_profile"])
        if detail and detail not in teacher.get("list_profile", ""):
            parts.append(detail)

        teacher.update(
            {
                "name": parse_profile_name(html) or teacher["name"],
                "title": teacher["title"],
                "email": parse_vsb_profile_email(
                    html, teacher["list_email"], self.exclude_emails
                ),
                "profile": "\n\n".join(parts) if parts else "",
            }
        )
