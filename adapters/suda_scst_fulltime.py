"""Adapter for Soochow University SCST full-time faculty list."""

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import first_email, parse_webplus_profile_content, strip_html


LIST_URL = "https://scst.suda.edu.cn/11249/list.htm"
BASE = "https://scst.suda.edu.cn"


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\ufeff", "").replace("\u200b", "").split())


class SudaScstFulltimeAdapter:
    school_name = "苏州大学计算机科学与技术学院（软件学院）专任教师"
    list_url = LIST_URL
    output_md = Path("outputs/md/suda_scst_fulltime_teachers.md")
    output_json = Path("outputs/json/suda_scst_fulltime_teachers.json")
    output_html_dir = Path("outputs/html/suda_scst_fulltime_lists")
    output_profile_html_dir = Path("outputs/html/suda_scst_fulltime_profiles")
    fetch_profiles = True
    profile_workers = 8

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        self.output_html_dir.joinpath("11249_list.html").write_text(html, encoding="utf-8")

        teachers: list[dict] = []
        for item in soup.select(".column-teacher"):
            name_node = item.select_one("h3")
            if not name_node:
                continue
            name = clean_text(name_node.get_text(" ", strip=True))
            letter = clean_text(item.get("data-letter", ""))

            link_node = item.select_one("a[href]")
            url = urljoin(BASE, link_node["href"]) if link_node and link_node.get("href") else ""

            img = item.select_one("img")
            image_url = urljoin(BASE, img["src"]) if img and img.get("src") else ""

            profile_lines = ["教师类别：专任教师"]
            if letter:
                profile_lines.append(f"拼音首字母：{letter}")
            if image_url:
                profile_lines.append(f"头像：{image_url}")

            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": "",
                    "list_email": "",
                    "email": "",
                    "role": "专任教师",
                    "disciplines": "",
                    "categories": ["专任教师"],
                    "letter": letter,
                    "image_url": image_url,
                    "profile_source": "列表页",
                    "profile": "\n".join(profile_lines),
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.output_profile_html_dir.mkdir(parents=True, exist_ok=True)
        safe_name = teacher["name"].replace("/", "_").replace("\\", "_")
        self.output_profile_html_dir.joinpath(f"{safe_name}.html").write_text(html, encoding="utf-8")

        soup = BeautifulSoup(html, "html.parser")
        title_node = soup.select_one(".post-title")
        page_title = clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
        if page_title and not teacher.get("name"):
            teacher["name"] = page_title

        content = parse_webplus_profile_content(html)
        if not content:
            content_node = soup.select_one(".wp_articlecontent")
            content = strip_html(str(content_node)) if content_node else ""

        email = first_email(content) or first_email(html[:12000])
        if email:
            teacher["email"] = email

        profile_parts = [teacher.get("profile", "")]
        if content and content not in profile_parts:
            profile_parts.append(content)
        teacher["profile"] = "\n\n".join(part for part in profile_parts if part).strip()
        teacher["profile_source"] = "详情页"
