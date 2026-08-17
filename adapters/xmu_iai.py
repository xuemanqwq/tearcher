"""Adapter for Xiamen University Institute of Artificial Intelligence PI team."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import first_email, strip_html

LIST_URL = "https://iai.xmu.edu.cn/team/PI/PI2027.htm"


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def split_title(raw_title: str, name: str) -> str:
    value = clean_text(raw_title).replace(name, "", 1).strip()
    return value


def profile_content(html: str) -> str:
    m = re.search(
        r'<div[^>]+class=["\'][^"\']*class-person[^"\']*["\'][^>]*>(.*?)(?:<footer|<div[^>]+class=["\'][^"\']*(?:web-footer|footer))',
        html,
        re.I | re.S,
    )
    if m:
        text = strip_html(m.group(1))
        if len(text) > 80:
            return text

    for pattern in (
        r'<div[^>]+class=["\'][^"\']*(?:teacher-detail|teacher-info|wp_articlecontent|v_news_content|main-content|content)[^"\']*["\'][^>]*>(.*?)</div>',
        r"<main[^>]*>(.*?)</main>",
        r'<section[^>]*class=["\'][^"\']*sub-page-main[^"\']*["\'][^>]*>(.*?)</section>',
    ):
        m = re.search(pattern, html, re.I | re.S)
        if m:
            text = strip_html(m.group(1))
            if len(text) > 80:
                return text
    text = strip_html(html)
    markers = ("当前位置", "首页", "师资队伍", "PI团队")
    lines = [line for line in text.splitlines() if clean_text(line) not in markers]
    return "\n".join(lines).strip()


def extract_direction_from_profile(text: str) -> str:
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for i, line in enumerate(lines):
        if line.startswith(("研究方向", "研究领域", "主要研究方向")):
            inline = re.sub(r"^(主要)?研究(方向|领域)[：:]*", "", line).strip()
            candidates = [inline] if inline else []
            for nxt in lines[i + 1 : i + 8]:
                if any(
                    nxt.startswith(prefix)
                    for prefix in (
                        "个人简介",
                        "教育经历",
                        "工作经历",
                        "科研项目",
                        "代表论文",
                        "联系方式",
                        "邮箱",
                    )
                ):
                    break
                candidates.append(nxt)
            value = "；".join(x for x in candidates if x)
            if value:
                return value
    return ""


class XmuIaiAdapter:
    school_name = "厦门大学人工智能研究院PI团队（2027年）"
    list_url = LIST_URL
    output_md = Path("outputs/md/xmu_iai_pi2027_teachers.md")
    output_json = Path("outputs/json/xmu_iai_pi2027_teachers.json")
    output_html = Path("outputs/html/xmu_iai_pi2027_list.html")
    profile_html_dir = Path("outputs/html/xmu_iai_pi2027_profiles")
    profile_workers = 6

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        teachers: list[dict] = []
        for card_m in re.finditer(
            r'<div[^>]+class=["\'][^"\']*class-card[^"\']*["\'][^>]*>(.*?)</div>\s*</div>',
            html,
            re.I | re.S,
        ):
            card = card_m.group(1)
            title_m = re.search(
                r'<p[^>]+class=["\'][^"\']*class-card__title[^"\']*["\'][^>]*>(.*?)</p>',
                card,
                re.I | re.S,
            )
            desc_m = re.search(
                r'<p[^>]+class=["\'][^"\']*class-card__desc[^"\']*["\'][^>]*>(.*?)</p>',
                card,
                re.I | re.S,
            )
            link_m = re.search(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*class-card__link[^"\']*["\']',
                card,
                re.I | re.S,
            )
            raw_title = clean_text(strip_html(title_m.group(1)) if title_m else "")
            if not raw_title:
                continue
            match = re.match(r"([\u4e00-\u9fff·]{2,5})\s*(.*)", raw_title)
            name = clean_text(match.group(1)) if match else raw_title
            title = clean_text(match.group(2)) if match else ""
            url = urljoin(LIST_URL, link_m.group(1)) if link_m else ""
            direction = clean_text(strip_html(desc_m.group(1)) if desc_m else "")
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": title,
                    "list_email": "",
                    "email": "",
                    "role": "PI团队（2027年）",
                    "disciplines": direction,
                    "categories": ["PI团队（2027年）", title] if title else ["PI团队（2027年）"],
                    "profile_source": "列表页",
                    "profile": f"研究方向：{direction}" if direction else "",
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_html_dir.joinpath(f"{safe_filename(teacher['name'])}.html").write_text(
            html, encoding="utf-8"
        )

        text = profile_content(html)
        profile_direction = extract_direction_from_profile(text)
        direction = teacher.get("disciplines", "")
        if profile_direction and len(profile_direction) <= 80:
            direction = profile_direction
        teacher.update(
            {
                "email": first_email(text) or first_email(html),
                "disciplines": direction,
                "profile_source": "详情页",
                "profile": text or teacher.get("profile", ""),
            }
        )
