"""Adapter for Soochow University SCST supervisor directory."""

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

LIST_URL = "https://scst.suda.edu.cn/11250/list.htm"
BASE = "https://scst.suda.edu.cn"

CATEGORY_URLS = [
    ("教授", "https://scst.suda.edu.cn/30767/list.htm"),
    ("副教授", "https://scst.suda.edu.cn/30768/list.htm"),
    ("讲师", "https://scst.suda.edu.cn/30769/list.htm"),
]


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def category_from_page(soup: BeautifulSoup) -> str:
    selected = soup.select_one("#subnavMenu li.selected")
    if selected:
        text = clean_text(selected.get_text(" ", strip=True))
        if text:
            return text
    title = soup.find("title")
    return clean_text(title.get_text(" ", strip=True)) if title else ""


class SudaScstAdapter:
    school_name = "苏州大学计算机科学与技术学院（软件学院）导师简介"
    list_url = LIST_URL
    output_md = Path("outputs/md/suda_scst_supervisors.md")
    output_json = Path("outputs/json/suda_scst_supervisors.json")
    output_html_dir = Path("outputs/html/suda_scst_lists")
    fetch_profiles = False

    def dedup_key(self, teacher: dict) -> str:
        return f"{'|'.join(teacher.get('categories', []))}|{teacher['name']}"

    def get_list_page_urls(self) -> list[str]:
        return [url for _, url in CATEGORY_URLS]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        category = category_from_page(soup)

        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        if category:
            self.output_html_dir.joinpath(f"{category}.html").write_text(html, encoding="utf-8")

        teachers: list[dict] = []
        for item in soup.select(".column-teacher-item"):
            name_node = item.find("h3")
            if not name_node:
                continue
            name = clean_text(name_node.get_text(" ", strip=True))
            title = clean_text(item.find("p").get_text(" ", strip=True)) if item.find("p") else ""
            img = item.find("img")
            image_url = urljoin(BASE, img.get("src")) if img and img.get("src") else ""

            profile_lines = []
            if category:
                profile_lines.append(f"导师栏目：{category}")
            if title:
                profile_lines.append(f"职称/称号：{title}")
            if image_url:
                profile_lines.append(f"头像：{image_url}")

            teachers.append(
                {
                    "url": "",
                    "name": name,
                    "title": title or category,
                    "list_email": "",
                    "email": "",
                    "role": category,
                    "disciplines": "",
                    "categories": [category] if category else [],
                    "image_url": image_url,
                    "profile_source": "列表页",
                    "profile": "\n".join(profile_lines) or "（列表页未提供更多信息）",
                }
            )
        return teachers
