"""Adapter for CSU School of Artificial Intelligence graduate advisors."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import first_email, parse_meta_description, strip_html

LIST_URL = "https://ai.csu.edu.cn/szdw.htm"


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_name(text: str) -> str:
    text = clean_text(text).replace("　", "")
    if re.fullmatch(r"[\u4e00-\u9fff ]+", text):
        return text.replace(" ", "")
    return text


def graduate_advisor_section(html: str) -> str:
    start = html.find("研究生导师")
    if start == -1:
        return ""
    end = html.find("_showDynClickBatch", start)
    return html[start:end] if end != -1 else html[start:]


def profile_title(text: str, name: str) -> str:
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for i, line in enumerate(lines[:20]):
        if line == name:
            for candidate in lines[i + 1 : i + 6]:
                if any(title in candidate for title in ("教授", "研究员", "讲师", "工程师")):
                    return candidate
    for title in ("教授", "副教授", "研究员", "副研究员", "讲师", "高级工程师"):
        if title in text:
            return title
    return ""


def profile_disciplines(text: str, html: str) -> str:
    def split_direction_items(value: str) -> list[str]:
        value = re.sub(r"（[^）]*）", "", value)
        value = re.sub(r"\([^)]*\)", "", value)
        value = value.replace("等", "")
        parts = re.split(r"[、，,；;。]\s*|※|\n", value)
        cleaned = []
        for part in parts:
            part = re.sub(r"^\[\d+\]\s*", "", clean_text(part)).strip("：: ")
            if not part or len(part) > 40:
                continue
            if any(
                marker in part
                for marker in (
                    "招生",
                    "联系方式",
                    "版权所有",
                    "信息与网络中心",
                    "手机版",
                    "不限于",
                    "欢迎",
                    "主持",
                    "发表",
                    "获得",
                    "编著",
                    "合作单位",
                )
            ):
                continue
            cleaned.append(part)
        return cleaned

    for pattern in [
        r"【研究方向】(.*?)(?:。|【招生信息】|【组内优势】|教育经历|工作经历|论文成果|$)",
        r"研究方向包括(.*?)(?:。|；|;|\n)",
        r"主要研究方向为(.*?)(?:，|,|。|；|;|\n)",
        r"研究兴趣[:：](.*?)(?:。|；|;|\n)",
    ]:
        m = re.search(pattern, text, re.S)
        if m:
            items = split_direction_items(m.group(1))
            if items:
                return "、".join(dict.fromkeys(items))

    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    directions: list[str] = []
    for i, line in enumerate(lines):
        if line == "研究方向" or line.startswith("研究方向：") or line.startswith("研究方向:"):
            inline = re.sub(r"^研究方向[：:]?", "", line).strip()
            if inline:
                directions.append(inline)
            for nxt in lines[i + 1 : i + 12]:
                if nxt in {"教育经历", "工作经历", "论文成果", "个人简介", "招生信息"}:
                    break
                if any(marker in nxt for marker in ("版权所有", "信息与网络中心", "手机版", "其他联系方式", "招生信息", "合作单位")):
                    break
                if nxt.startswith("[") or len(nxt) <= 40:
                    directions.append(re.sub(r"^\[\d+\]\s*", "", nxt).strip())
            break

    if directions:
        items: list[str] = []
        for direction in directions:
            items.extend(split_direction_items(direction))
        return "、".join(dict.fromkeys(d for d in items if d))

    meta = parse_meta_description(html)
    if meta:
        meta = re.sub(r"中南大学|个人主页|首页", "", meta)
        meta = re.sub(r"[A-Za-z]+|[a-z]+[0-9]*", "", meta)
        bits = [b for b in re.split(r"[，,；;]", meta) if b and len(b) <= 30]
        return "、".join(dict.fromkeys(b for bit in bits for b in split_direction_items(bit)))
    return ""


class CsuAiAdapter:
    school_name = "中南大学人工智能学院（研究生导师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/csu_ai_graduate_advisors.md")
    output_json = Path("outputs/json/csu_ai_graduate_advisors.json")
    output_html = Path("outputs/html/csu_ai_szdw.html")
    profile_html_dir = Path("outputs/html/csu_ai_profiles")
    profile_workers = 8

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        section = graduate_advisor_section(html)
        teachers: list[dict] = []
        for href, raw_name in re.findall(
            r'<a\s+href=["\']([^"\']+)["\'][^>]*class=["\']fnt18["\'][^>]*>(.*?)</a>',
            section,
            re.I | re.S,
        ):
            name = normalize_name(strip_html(raw_name))
            if not name:
                continue
            url = "" if "javascript:" in href.lower() else urljoin(LIST_URL, href)
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": "",
                    "list_email": "",
                    "email": "",
                    "role": "研究生导师",
                    "disciplines": "",
                    "categories": ["研究生导师（含兼聘）"],
                    "profile_source": "列表页",
                    "profile": "（暂无个人主页链接）" if not url else "",
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", teacher["name"])
        self.profile_html_dir.joinpath(f"{safe_name}.html").write_text(html, encoding="utf-8")

        profile = strip_html(html)
        email = first_email(profile) or first_email(html)
        title = profile_title(profile, teacher["name"])
        disciplines = profile_disciplines(profile, html)
        teacher.update(
            {
                "title": title,
                "email": email,
                "disciplines": disciplines,
                "profile_source": "详情页",
                "profile": profile,
            }
        )
