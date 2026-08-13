"""Adapter for Beijing Jiaotong University CS faculty directory."""

import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core import first_email, strip_html

LIST_URL = "https://cs.bjtu.edu.cn/szll/index.htm"
IFRAME_URL = "https://welcome.bjtu.edu.cn/t_brief/0221/#/teacher/computer"
BROWSER_DATA = Path("outputs/html/bjtu_cs_browser_data.json")
PROFILE_BASE = "https://faculty.bjtu.edu.cn"
BASE_MEDIA = "https://welcome.bjtu.edu.cn/v5/"

TITLE_MAP = {
    "011": "教授",
    "012": "副教授",
    "013": "讲师",
    "014": "助教",
    "061": "研究员",
    "062": "副研究员",
    "063": "助理研究员",
    "064": "研究实习员",
    "072": "高级实验师",
    "073": "实验师",
    "074": "助理实验师",
    "082": "高级工程师",
    "083": "工程师",
    "154": "助理编辑",
}


def clean_text(text: str) -> str:
    text = (text or "").replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def clean_multiline(text: str) -> str:
    lines = [clean_text(line) for line in (text or "").splitlines()]
    text = "\n".join(line for line in lines if line)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def normalize_title(value: str) -> str:
    value = clean_text(value)
    return TITLE_MAP.get(value, value)


def section_texts(soup: BeautifulSoup) -> dict[str, str]:
    sections: dict[str, str] = {}
    for box in soup.select(".mainleft_box"):
        header = box.find(["h4", "h3"])
        if not header:
            continue
        title = clean_text(header.get_text(" ", strip=True))
        header.extract()
        text = clean_multiline(strip_html(str(box)))
        if title and text:
            sections[title] = text
    return sections


def direction_from_sections(sections: dict[str, str], fallback: str = "") -> str:
    for key in ("研究方向", "招生方向", "学科方向"):
        if sections.get(key):
            lines = [
                line
                for line in sections[key].splitlines()
                if not re.search(r"(欢迎|名额|联系|招生|硕士|博士)", line)
            ]
            return clean_text("；".join(lines[:3])) or clean_text(sections[key])
    return fallback


class BjtuCsAdapter:
    school_name = "北京交通大学计算机科学与技术学院（师资力量）"
    list_url = LIST_URL
    output_md = Path("outputs/md/bjtu_cs_teachers.md")
    output_json = Path("outputs/json/bjtu_cs_teachers.json")
    output_html = Path("outputs/html/bjtu_cs_index.html")
    profile_html_dir = Path("outputs/html/bjtu_cs_profiles")
    profile_workers = 10

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("username") or teacher.get("url") or teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")
        if not BROWSER_DATA.exists():
            raise RuntimeError(
                f"缺少浏览器渲染数据：{BROWSER_DATA}。先运行 scripts/dump_bjtu_cs_browser.py。"
            )

        payload = json.loads(BROWSER_DATA.read_text(encoding="utf-8"))
        source = ((payload.get("vue") or {}).get("sourceData") or [])
        teachers: list[dict] = []
        for item in source:
            username = clean_text(str(item.get("username") or ""))
            if not username:
                continue
            name = clean_text(item.get("name") or "")
            title = normalize_title(item.get("teacher__work_title") or "")
            mentor_type = clean_text(item.get("teacher__mentor_type") or "") or "无"
            dept = clean_text(item.get("dept__name") or "")
            degree = clean_text(item.get("teacher__academic_degree") or "")
            email = clean_text(item.get("email") or "")
            avatar = clean_text(item.get("avatar") or "")
            image_url = BASE_MEDIA + avatar if avatar else ""
            url = f"{PROFILE_BASE}/{username}/"
            profile_lines = [
                f"院系：{dept}" if dept else "",
                f"职称：{title}" if title else "",
                f"导师类型：{mentor_type}" if mentor_type else "",
                f"学位：{degree}" if degree else "",
                f"邮箱：{email}" if email else "",
                f"头像：{image_url}" if image_url else "",
                f"iframe页面：{IFRAME_URL}",
            ]
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": title,
                    "list_email": email,
                    "email": email,
                    "role": mentor_type,
                    "disciplines": "",
                    "categories": [dept] if dept else [],
                    "department": dept,
                    "degree": degree,
                    "username": username,
                    "image_url": image_url,
                    "profile_source": "列表页",
                    "profile": "\n".join(line for line in profile_lines if line),
                }
            )
        return teachers

    def profile_cache_path(self, teacher: dict) -> Path:
        return self.profile_html_dir / f"{safe_filename(teacher['name'])}_{teacher.get('username','')}.html"

    def fetch_profile_page(self, teacher: dict) -> str:
        cache_path = self.profile_cache_path(teacher)
        if cache_path.exists():
            return cache_path.read_text(encoding="utf-8", errors="replace")
        response = requests.get(
            teacher["url"],
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            timeout=10,
        )
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_cache_path(teacher).write_text(html, encoding="utf-8")

        soup = BeautifulSoup(html, "html.parser")
        sections = section_texts(soup)
        full_text = clean_multiline(strip_html(html))
        direction = direction_from_sections(sections, teacher.get("disciplines", ""))

        header_name = clean_text(soup.select_one("h1").get_text(" ", strip=True)) if soup.select_one("h1") else ""
        header_title = ""
        border = soup.select_one(".border_p")
        if border:
            parts = [clean_text(part) for part in border.get_text("，", strip=True).split("，")]
            for part in parts:
                if part and part not in {"博士", "硕士", "学士"}:
                    header_title = part
                    break

        profile_parts = []
        for key in ("基本信息", "研究方向", "教育背景", "工作经历", "科研项目", "论文/期刊", "专利"):
            if sections.get(key):
                profile_parts.append(f"【{key}】\n{sections[key]}")
        profile = "\n\n".join(profile_parts) or full_text or teacher.get("profile", "")

        teacher.update(
            {
                "name": header_name or teacher["name"],
                "title": header_title or teacher.get("title", ""),
                "email": (
                    first_email(profile)
                    or first_email(html)
                    or teacher.get("list_email", "")
                ),
                "disciplines": direction,
                "profile_source": "详情页",
                "profile": profile,
            }
        )
