"""Adapter for Shandong University CS faculty lists."""

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core import first_email, strip_html

LIST_URL = "https://www.cs.sdu.edu.cn/szdw1/js.htm"

LIST_PAGES = [
    "https://www.cs.sdu.edu.cn/szdw1/js.htm",
    "https://www.cs.sdu.edu.cn/szdw1/yjy.htm",
    "https://www.cs.sdu.edu.cn/szdw1/fjs.htm",
    "https://www.cs.sdu.edu.cn/szdw1/fyjy.htm",
    "https://www.cs.sdu.edu.cn/szdw1/zljs.htm",
]


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_external_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return bool(host and not host.endswith("cs.sdu.edu.cn"))


def obfuscated_email(text: str) -> str:
    normalized = re.sub(r"\s*(?:\[at\]|\(at\)| at )\s*", "@", text, flags=re.I)
    normalized = re.sub(r"\s*(?:\[dot\]|\(dot\)| dot )\s*", ".", normalized, flags=re.I)
    email = first_email(normalized)
    if email:
        return email
    return ""


def profile_content(html: str, url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    if "cs.sdu.edu.cn" in urlparse(url).netloc.lower():
        content = soup.select_one(".v_news_content")
        if content:
            text = strip_html(str(content))
            if text:
                return text

    for selector in ("main", "article", ".post", ".page-content", ".content", ".container"):
        content = soup.select_one(selector)
        if content:
            text = strip_html(str(content))
            if len(text) > 80:
                return text

    return strip_html(html)


class SduCsAdapter:
    school_name = "山东大学计算机科学与技术学院（师资队伍）"
    list_url = LIST_URL
    output_md = Path("outputs/md/sdu_cs_teachers.md")
    output_json = Path("outputs/json/sdu_cs_teachers.json")
    profile_workers = 8

    def dedup_key(self, teacher: dict) -> str:
        return teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return LIST_PAGES

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table")
        if not table:
            return []
        page_category = ""
        if soup.title:
            page_category = clean_text(soup.title.get_text(" ", strip=True).split("-", 1)[0])

        teachers: list[dict] = []
        for row in table.select("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) < 3 or cells[0].name == "th":
                continue

            name = clean_text(cells[0].get_text(" ", strip=True))
            title = clean_text(cells[1].get_text(" ", strip=True))
            direction = clean_text(cells[2].get_text(" ", strip=True))
            if not name:
                continue

            link = cells[0].find("a") or row.find("a")
            url = urljoin(LIST_URL, link.get("href", "")) if link else ""
            profile_lines = [
                f"职称：{title}" if title else "",
                f"研究方向：{direction}" if direction else "",
            ]
            profile_lines = [line for line in profile_lines if line]

            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": title,
                    "list_email": "",
                    "email": "",
                    "role": title,
                    "disciplines": direction,
                    "categories": [page_category or title],
                    "profile_source": "列表页",
                    "homepage_type": "外部主页" if is_external_url(url) else "学院主页",
                    "profile": "\n".join(profile_lines),
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        url = teacher.get("url", "")
        profile = profile_content(html, url)
        if not profile:
            return

        email = first_email(profile) or obfuscated_email(profile)
        teacher.update(
            {
                "email": email or teacher.get("email", ""),
                "profile_source": "详情页",
                "profile": profile,
            }
        )
