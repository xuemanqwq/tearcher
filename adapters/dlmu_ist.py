"""Adapter for DLMU Information Science and Technology faculty list."""

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import (
    first_email,
    parse_profile_name,
    parse_vsb_profile_content,
    parse_vsb_profile_email,
    strip_html,
)

LIST_URL = "https://ist.dlmu.edu.cn/info/1099/1131.htm"

TITLE_KEYWORDS = (
    "副研究员",
    "副教授",
    "高级工程师",
    "研究员",
    "教授",
    "工程师",
    "实验师",
    "讲师",
)


def clean_text(text: str) -> str:
    text = text.replace("\u200b", "").replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def title_from_text(text: str) -> str:
    for title in TITLE_KEYWORDS:
        if title in text:
            return title
    return ""


def list_profile(category: str, url: str) -> str:
    lines = [f"所属教学部门：{category}"]
    if url.lower().endswith(".pdf"):
        lines.append("详情页类型：PDF")
    return "\n".join(lines)


def choose_link(cell, name: str) -> str:
    links = cell.find_all("a")
    for link in links:
        if clean_text(link.get_text(" ", strip=True)) == name and link.get("href"):
            return link.get("href")
    for link in links:
        if link.get("href"):
            return link.get("href")
    return ""


def parse_static_professor_content(html: str) -> str:
    m = re.search(r'<div\s+class=["\']passage["\'][^>]*>(.*)</div>\s*</body>', html, re.I | re.S)
    if m:
        text = strip_html(m.group(1))
        text = text.replace(">-->", "")
        text = re.sub(r"(?m)^\s*-->\s*$", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        if text:
            return text.strip()
    return strip_html(html)


def parse_static_professor_name(html: str, fallback: str) -> str:
    title = parse_profile_name(html)
    if title:
        return clean_text(title.split("-")[0]) or fallback
    return fallback


class DlmuIstAdapter:
    school_name = "大连海事大学信息科学技术学院"
    list_url = LIST_URL
    output_md = Path("outputs/md/dlmu_ist_teachers.md")
    output_json = Path("outputs/json/dlmu_ist_teachers.json")
    profile_workers = 8

    def dedup_key(self, teacher: dict) -> str:
        return f"{teacher.get('categories', [''])[0]}|{teacher.get('url') or teacher['name']}"

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        teachers = []
        current_category = ""
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            if len(cells) == 1 and cells[0].get("colspan"):
                current_category = clean_text(cells[0].get_text(" ", strip=True))
                continue

            for cell in cells:
                name = clean_text(cell.get_text(" ", strip=True))
                if not name:
                    continue
                href = choose_link(cell, name)
                url = urljoin(LIST_URL, href) if href else ""
                teachers.append(
                    {
                        "url": url,
                        "name": clean_text(name),
                        "title": "",
                        "list_email": "",
                        "email": "",
                        "categories": [current_category] if current_category else [],
                        "profile": list_profile(current_category, url),
                    }
                )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        if teacher.get("url", "").lower().endswith(".pdf"):
            return

        if "v_news_content" in html:
            profile = parse_vsb_profile_content(html)
            teacher.update(
                {
                    "name": clean_text(parse_profile_name(html)) or teacher["name"],
                    "title": title_from_text(profile),
                    "email": parse_vsb_profile_email(html, teacher.get("list_email", "")),
                    "profile": profile or teacher.get("profile", ""),
                }
            )
            return

        profile = parse_static_professor_content(html)
        teacher.update(
            {
                "name": parse_static_professor_name(html, teacher["name"]),
                "title": title_from_text(profile),
                "email": first_email(profile),
                "profile": profile or teacher.get("profile", ""),
            }
        )
