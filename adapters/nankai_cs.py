"""Adapter for Nankai University Software College professor lists."""

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import first_email, parse_profile_name, strip_html

LIST_URL = "https://cs.nankai.edu.cn/szdw/js.htm"

LIST_PAGES = [
    ("教授", "https://cs.nankai.edu.cn/szdw/js.htm"),
    ("教授", "https://cs.nankai.edu.cn/szdw/js/1.htm"),
    ("副教授", "https://cs.nankai.edu.cn/szdw/fjs.htm"),
    ("副教授", "https://cs.nankai.edu.cn/szdw/fjs/1.htm"),
]


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_label(text: str) -> str:
    return clean_text(text).replace(" ", "")


def field_value(line: str) -> tuple[str, str]:
    line = clean_text(line)
    if ":" in line:
        label, value = line.split(":", 1)
    elif "：" in line:
        label, value = line.split("：", 1)
    else:
        return normalize_label(line), ""
    return normalize_label(label), clean_text(value)


def title_category(title: str) -> str:
    if "副教授" in title:
        return "副教授"
    if "教授" in title:
        return "教授"
    return ""


def extract_profile_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".v_news_content")
    if content:
        text = strip_html(str(content))
        if text:
            return text
    return strip_html(html)


def title_from_profile(profile: str) -> str:
    for line in profile.splitlines():
        label, value = field_value(line)
        if label == "职称" and value:
            return value
    for title in ("讲席教授", "英才教授", "副教授", "教授"):
        if title in profile:
            return title
    return ""


def direction_from_profile(profile: str) -> str:
    for line in profile.splitlines():
        label, value = field_value(line)
        if label == "研究方向" and value:
            return value
    return ""


class NankaiCsAdapter:
    school_name = "南开大学软件学院（教授、副教授）"
    list_url = LIST_URL
    output_md = Path("outputs/md/nankai_cs_professors.md")
    output_json = Path("outputs/json/nankai_cs_professors.json")
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

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        title_text = soup.title.get_text(" ", strip=True) if soup.title else ""
        page_category = "副教授" if "副教授" in title_text else "教授"
        teachers: list[dict] = []

        for item in soup.select(".teacher a.item"):
            name_el = item.select_one(".name")
            name = clean_text(name_el.get_text(" ", strip=True)) if name_el else ""
            if not name:
                name = clean_text(item.get("title", ""))

            fields: dict[str, str] = {}
            for div in item.select(".des div"):
                label, value = field_value(div.get_text(" ", strip=True))
                fields[label] = value

            title = fields.get("职称", "")
            category = title_category(title)
            if category not in {"教授", "副教授"}:
                continue
            if page_category == "副教授" and category != "副教授":
                continue

            direction = fields.get("研究方向", "")
            department = fields.get("所属部门", "")
            email = fields.get("电子邮件", "")
            profile_lines = []
            if department:
                profile_lines.append(f"所属部门：{department}")
            if title:
                profile_lines.append(f"职称：{title}")
            if direction:
                profile_lines.append(f"研究方向：{direction}")

            teachers.append(
                {
                    "url": urljoin(LIST_URL, item.get("href", "")),
                    "name": name,
                    "title": title,
                    "list_email": email,
                    "email": email,
                    "role": category,
                    "disciplines": direction,
                    "categories": [category],
                    "department": department,
                    "profile_source": "列表页",
                    "profile": "\n".join(profile_lines),
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        profile = extract_profile_content(html)
        if not profile:
            return

        title = title_from_profile(profile) or teacher.get("title", "")
        direction = direction_from_profile(profile) or teacher.get("disciplines", "")
        email = first_email(profile) or teacher.get("list_email", "")
        name = clean_text(parse_profile_name(html).split("-")[0]) or teacher["name"]

        teacher.update(
            {
                "name": name,
                "title": title,
                "email": email,
                "role": title_category(title) or teacher.get("role", ""),
                "disciplines": direction,
                "profile_source": "详情页",
                "profile": profile,
            }
        )
