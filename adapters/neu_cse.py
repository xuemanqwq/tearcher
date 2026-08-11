"""Adapter for Northeastern University CSE faculty directory."""

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import first_email, strip_html

LIST_URL = "https://www.cse.neu.edu.cn/6314/list.htm"
BASE = "https://www.cse.neu.edu.cn"
FOOTER_EMAILS = {"neucse@cse.neu.edu.cn"}


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_name(text: str) -> str:
    text = clean_text(text)
    if re.fullmatch(r"[\u4e00-\u9fff·]+", text):
        return text.replace(" ", "")
    return text


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def profile_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".wp_articlecontent")
    if content:
        text = strip_html(str(content))
        if text:
            return text
    content = soup.select_one(".entry")
    if content:
        text = strip_html(str(content))
        if text:
            return text
    return strip_html(html)


def parse_direction(text: str) -> str:
    patterns = [
        r"主要研究领域包括[:：]?\s*([^。\n]+)",
        r"主要研究方向[:：]?\s*([^。\n]+)",
        r"研究方向[:：]\s*([^。\n]+)",
        r"研究领域[:：]\s*([^。\n]+)",
        r"从事([^。\n]{4,80}?研究)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return clean_text(m.group(1)).strip("：:；;，, ")
    return ""


class NeuCseAdapter:
    school_name = "东北大学计算机科学与工程学院（教师名录）"
    list_url = LIST_URL
    output_md = Path("outputs/md/neu_cse_teachers.md")
    output_json = Path("outputs/json/neu_cse_teachers.json")
    output_html = Path("outputs/html/neu_cse_teachers.html")
    profile_html_dir = Path("outputs/html/neu_cse_profiles")
    profile_workers = 8

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        soup = BeautifulSoup(html, "html.parser")
        teachers: list[dict] = []
        for group in soup.select(".teacher_list ul"):
            header = group.find(["strong", "b"])
            title = clean_text(header.get_text(" ", strip=True)) if header else ""
            if title not in {"教授", "副教授", "讲师"}:
                continue

            for link in group.find_all("a", href=True):
                name = normalize_name(link.get_text(" ", strip=True))
                if not name:
                    continue
                url = urljoin(BASE, link["href"])
                teachers.append(
                    {
                        "url": url,
                        "name": name,
                        "title": title,
                        "list_email": "",
                        "email": "",
                        "role": title,
                        "disciplines": "",
                        "categories": [title],
                        "profile_source": "列表页",
                        "profile": f"职称：{title}",
                    }
                )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_html_dir.joinpath(f"{safe_filename(teacher['name'])}.html").write_text(
            html, encoding="utf-8"
        )

        profile = profile_content(html)
        teacher.update(
            {
                "email": (
                    first_email(profile, exclude=FOOTER_EMAILS)
                    or first_email(html, exclude=FOOTER_EMAILS)
                    or teacher.get("list_email", "")
                ),
                "disciplines": parse_direction(profile) or teacher.get("disciplines", ""),
                "profile_source": "详情页",
                "profile": profile,
            }
        )
