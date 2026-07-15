"""Adapter for ZUEL XAGX computer technology master's supervisors."""

import base64
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core import first_email, strip_html

LIST_URL = "https://xagx.zuel.edu.cn/4082/list.htm"
SECTION_TITLE = "计算机技术专业硕士点导师"
NEXT_SECTION_TITLE = "人工智能专业硕士点导师"

TITLE_KEYWORDS = (
    "副教授",
    "教授",
    "副研究员",
    "研究员",
    "高级工程师",
    "工程师",
    "讲师",
)


def clean_text(text: str) -> str:
    text = text.replace("\u200b", "").replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def decrypt_html(html: str) -> str:
    """Decrypt the WebPlus anti-bot shell when present."""
    if "content_container" not in html or "AES-GCM" not in html:
        return html

    key_match = re.search(
        r'var\s+i="[^"]*"\s*;\s*j="[^"]*"\s*;\s*k="([^"]*)"',
        html,
    )
    data_match = re.search(
        r'var\s+\w+\s*=\s*k\s*,\s*\w+\s*=\s*"([A-Za-z0-9+/=]+)"',
        html,
    )
    if not key_match or not data_match:
        return html

    key_bytes = key_match.group(1).encode("utf-8")
    folded_key = bytearray(16)
    for idx, byte in enumerate(key_bytes):
        folded_key[idx % 16] ^= byte

    encrypted = base64.b64decode(data_match.group(1))
    return AESGCM(bytes(folded_key)).decrypt(
        encrypted[:12],
        encrypted[12:],
        None,
    ).decode("utf-8", errors="replace")


def normalize_profile_url(href: str) -> str:
    href = (href or "").strip()
    embedded = re.search(r"https?://xagx\.zuel\.edu\.cn/[^\"'<> ]+", href)
    if embedded:
        return embedded.group(0)
    return urljoin(LIST_URL, href)


def article_content(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one(".wp_articlecontent") or soup.select_one(".Article_Content")


def target_section_html(html: str) -> str:
    article = article_content(html)
    if not article:
        return ""
    raw = str(article)
    start = raw.find(SECTION_TITLE)
    if start == -1:
        return ""
    end = raw.find(NEXT_SECTION_TITLE, start + len(SECTION_TITLE))
    return raw[start:end] if end != -1 else raw[start:]


def field_from_profile(profile: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}[：:]\s*([^\n]+)", profile)
    return clean_text(match.group(1)) if match else ""


def title_from_profile(profile: str) -> str:
    labeled = field_from_profile(profile, "职称")
    if labeled:
        return labeled
    for title in TITLE_KEYWORDS:
        if title in profile:
            return title
    return ""


def name_from_profile(profile: str) -> str:
    return field_from_profile(profile, "姓名")


def profile_from_html(html: str) -> str:
    article = article_content(html)
    if article:
        text = strip_html(str(article))
        if text:
            return text
    return strip_html(html)


class ZuelXagxAdapter:
    school_name = "中南财经政法大学信息工程学院（计算机技术专业硕士点导师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/zuel_xagx_computer_tech_teachers.md")
    output_json = Path("outputs/json/zuel_xagx_computer_tech_teachers.json")
    output_html = Path("outputs/html/zuel_xagx_4082_decrypted.html")
    profile_workers = 8

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        html = decrypt_html(html)
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        section = target_section_html(html)
        soup = BeautifulSoup(section, "html.parser")
        teachers: list[dict] = []
        seen: set[str] = set()

        for link in soup.find_all("a"):
            name = clean_text(link.get_text(" ", strip=True))
            if not name:
                continue
            url = normalize_profile_url(link.get("href", ""))
            key = url or name
            is_leader = name == "屈振新" and not teachers
            if key in seen:
                continue
            seen.add(key)
            role = "导师组长、专业硕士点导师" if is_leader else "专业硕士点导师"
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "list_name": name,
                    "title": "",
                    "list_email": "",
                    "email": "",
                    "role": role,
                    "disciplines": "计算机技术",
                    "categories": [SECTION_TITLE],
                    "profile_source": "列表页",
                    "profile": "\n".join(
                        [
                            "招生方向/学科：计算机技术",
                            f"导师类别：{role}",
                        ]
                    ),
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        html = decrypt_html(html)
        profile = profile_from_html(html)
        if not profile:
            return

        teacher.update(
            {
                "name": name_from_profile(profile) or teacher["name"],
                "title": title_from_profile(profile),
                "email": first_email(profile),
                "profile_source": "详情页",
                "profile": profile,
            }
        )
