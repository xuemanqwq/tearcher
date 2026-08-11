"""Adapter for Minzu University of China Information Engineering faculty."""

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import first_email, parse_profile_name, parse_vsb_profile_content, strip_html

LIST_URL = "https://xingong.muc.edu.cn/szdw/xyjs.htm"
BASE_URL = "https://xingong.muc.edu.cn/szdw/xyjs.htm"


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def href_from_onclick(value: str) -> str:
    m = re.search(r"opennews\(['\"]([^'\"]+)['\"]\)", value or "")
    return m.group(1) if m else ""


def extract_direction(text: str) -> str:
    for pattern in (
        r"研究方向[:：]\s*([^\n]+)",
        r"主要研究方向[:：]\s*([^\n]+)",
        r"研究领域[:：]\s*([^\n]+)",
    ):
        m = re.search(pattern, text)
        if m:
            return clean_text(m.group(1)).rstrip("。；;")
    return ""


def extract_header_text(soup: BeautifulSoup) -> str:
    pieces: list[str] = []
    for selector in (
        ".detail-info",
        ".detail-pannel",
        ".teacher__detail__top",
        ".teacher-detail",
        ".teacher-info",
        ".Article_Title",
    ):
        node = soup.select_one(selector)
        if node:
            text = strip_html(str(node))
            if text:
                pieces.append(text)
    return "\n".join(pieces)


def profile_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    header = extract_header_text(soup)
    content = parse_vsb_profile_content(html)
    if not content:
        node = soup.select_one(".v_news_content")
        content = strip_html(str(node)) if node else strip_html(html)
    parts = [part for part in (header, content) if part]
    text = "\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def title_from_soup(soup: BeautifulSoup, fallback: str) -> str:
    desc = soup.select_one(".detail-desc")
    if desc:
        for span in desc.find_all("span"):
            text = clean_text(span.get_text(" ", strip=True))
            if text in {"男", "女"}:
                continue
            if text and "研究方向" not in text:
                return text
    return fallback


class MucXingongAdapter:
    school_name = "中央民族大学信息工程学院（学院教师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/muc_xingong_teachers.md")
    output_json = Path("outputs/json/muc_xingong_teachers.json")
    output_html = Path("outputs/html/muc_xingong_teachers.html")
    profile_html_dir = Path("outputs/html/muc_xingong_profiles")
    profile_workers = 16

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or f"{'|'.join(teacher.get('categories', []))}|{teacher['name']}"

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        soup = BeautifulSoup(html, "html.parser")
        teachers: list[dict] = []
        for box in soup.select(".teacher-box"):
            header = box.find_previous(class_="title-box")
            category = clean_text(header.get_text(" ", strip=True)) if header else ""
            for item in box.select("li"):
                name_node = item.find("h4")
                if not name_node:
                    continue
                name = clean_text(name_node.get_text(" ", strip=True))
                title = clean_text(item.find("h5").get_text(" ", strip=True)) if item.find("h5") else ""
                span = item.find("span")
                disciplines = clean_text(span.get_text(" ", strip=True)) if span else ""
                disciplines = re.sub(r"^研究方向[:：]\s*", "", disciplines)

                href = ""
                for node in item.find_all(True):
                    href = href_from_onclick(node.get("onclick", ""))
                    if href:
                        break
                url = urljoin(BASE_URL, href) if href else ""
                teachers.append(
                    {
                        "url": url,
                        "name": name,
                        "title": title,
                        "list_email": "",
                        "email": "",
                        "role": title,
                        "disciplines": disciplines,
                        "categories": [category] if category else [],
                        "profile_source": "列表页",
                        "profile": "\n".join(
                            part
                            for part in (
                                f"所属部门：{category}" if category else "",
                                f"职称/导师类型：{title}" if title else "",
                                f"研究方向：{disciplines}" if disciplines else "",
                            )
                            if part
                        ),
                    }
                )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_html_dir.joinpath(f"{safe_filename(teacher['name'])}.html").write_text(
            html, encoding="utf-8"
        )

        soup = BeautifulSoup(html, "html.parser")
        text = profile_text(html)
        profile_name = clean_text(parse_profile_name(html).split("-")[0])
        direction = extract_direction(strip_html(html)) or teacher.get("disciplines", "")
        title = title_from_soup(soup, teacher.get("title", ""))
        teacher.update(
            {
                "name": profile_name or teacher["name"],
                "title": title,
                "role": title or teacher.get("role", ""),
                "email": first_email(text) or first_email(html) or teacher.get("list_email", ""),
                "disciplines": direction,
                "profile_source": "详情页",
                "profile": text or teacher.get("profile", ""),
            }
        )
