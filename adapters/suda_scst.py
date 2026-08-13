"""Adapter for Soochow University SCST supervisor directory."""

from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import first_email, strip_html


LIST_URL = "https://scst.suda.edu.cn/11250/list.htm"
BASE = "https://scst.suda.edu.cn"


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\ufeff", "").replace("\u200b", "").split())


def article_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".wp_articlecontent")
    if node:
        return strip_html(str(node))
    node = soup.select_one(".read-content")
    if node:
        return strip_html(str(node))
    return ""


def extract_discipline(profile: str) -> str:
    labels = ("主要研究方向", "研究方向", "研究领域")
    stop_labels = {"获奖", "代表作", "个人简介", "教育经历", "工作经历", "联系方式"}
    lines = [clean_text(line) for line in profile.splitlines()]
    lines = [line for line in lines if line]
    for i, line in enumerate(lines):
        if line in labels or any(line.startswith(label + "：") for label in labels):
            inline = line.split("：", 1)[1].strip() if "：" in line else ""
            collected = [inline] if inline else []
            for nxt in lines[i + 1 : i + 10]:
                if nxt in stop_labels:
                    break
                if nxt in labels:
                    continue
                if nxt.startswith(("获奖", "代表作", "个人简介", "联系方式")):
                    break
                collected.append(nxt.lstrip(". "))
            return "；".join(x for x in collected if x)
    return ""


class SudaScstAdapter:
    school_name = "苏州大学计算机科学与技术学院（软件学院）导师简介"
    list_url = LIST_URL
    output_md = Path("outputs/md/suda_scst_supervisors.md")
    output_json = Path("outputs/json/suda_scst_supervisors.json")
    output_html_dir = Path("outputs/html/suda_scst_lists")
    output_profile_html_dir = Path("outputs/html/suda_scst_profiles")
    fetch_profiles = True
    profile_workers = 8

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        self.output_html_dir.joinpath("11250_list.html").write_text(html, encoding="utf-8")

        teachers: list[dict] = []
        for item in soup.select(".column-teacher"):
            name_node = item.select_one("h3")
            if not name_node:
                continue
            name = clean_text(name_node.get_text(" ", strip=True))
            title_node = item.select_one("p")
            title = clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
            letter = clean_text(item.get("data-letter", ""))

            link_node = item.select_one("a[href]")
            url = urljoin(BASE, link_node["href"]) if link_node and link_node.get("href") else ""

            img = item.select_one("img")
            image_url = urljoin(BASE, img["src"]) if img and img.get("src") else ""

            profile_lines = ["导师栏目：导师简介"]
            if title:
                profile_lines.append(f"职称/称号：{title}")
            if letter:
                profile_lines.append(f"拼音首字母：{letter}")
            if image_url:
                profile_lines.append(f"头像：{image_url}")

            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": title,
                    "list_email": "",
                    "email": "",
                    "role": title,
                    "disciplines": "",
                    "categories": ["导师简介"],
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

        profile = article_content(html)
        email = first_email(profile) or first_email(html[:15000])
        if email:
            teacher["email"] = email

        discipline = extract_discipline(profile)
        if discipline:
            teacher["disciplines"] = discipline

        parts = [teacher.get("profile", "")]
        if profile:
            parts.append(profile)
        teacher["profile"] = "\n\n".join(part for part in parts if part).strip()
        teacher["profile_source"] = "详情页"
