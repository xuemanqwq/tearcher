"""Adapter for Nankai University College of Computer Science all faculty lists."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import first_email, parse_meta_description, parse_profile_name, strip_html

LIST_URL = "https://cc.nankai.edu.cn/13250/list.htm"

LIST_PAGES = [
    ("教授/研究员", "https://cc.nankai.edu.cn/jswyjy/list.htm"),
    ("副教授/副研究员", "https://cc.nankai.edu.cn/fjswfyjy/list.htm"),
    ("讲师", "https://cc.nankai.edu.cn/js/list.htm"),
    ("实验教学队伍", "https://cc.nankai.edu.cn/syjxdw/list.htm"),
    ("博士后", "https://cc.nankai.edu.cn/bsh/list.htm"),
    ("兼职教授", "https://cc.nankai.edu.cn/jzjs/list.htm"),
    ("退休人员", "https://cc.nankai.edu.cn/txry/list.htm"),
]


def clean_text(text: str) -> str:
    text = (text or "").replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def normalize_name_title(text: str) -> tuple[str, str]:
    text = clean_text(strip_html(text))
    text = re.sub(r"\s+", " ", text.replace("&nbsp;", " "))
    for title in (
        "讲座教授",
        "副教授",
        "副研究员",
        "高级实验师",
        "实验师",
        "工程师",
        "博士后",
        "教授",
        "研究员",
        "讲师",
    ):
        if title in text:
            name = clean_text(text.split(title, 1)[0])
            return name, title
    parts = text.split()
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return text, ""


def field_value_from_label(html: str, label: str) -> str:
    pattern = (
        rf"{label}\s*[：:]?\s*</span>\s*</div>\s*"
        rf"<div[^>]*class=[\"'][^\"']*col-sm-10[^\"']*[\"'][^>]*>\s*"
        rf"<span[^>]*>(.*?)</span>"
    )
    m = re.search(pattern, html, re.I | re.S)
    return clean_text(strip_html(m.group(1))) if m else ""


def extract_article_content(html: str) -> str:
    chunks = []
    for m in re.finditer(
        r"<div[^>]+class=['\"][^'\"]*wp_articlecontent[^'\"]*['\"][^>]*>(.*?)</div>\s*</div>",
        html,
        re.I | re.S,
    ):
        text = strip_html(m.group(1))
        if text:
            chunks.append(text)
    if chunks:
        return "\n\n".join(chunks)
    meta = parse_meta_description(html)
    if meta:
        return meta
    return strip_html(html)


def extract_direction_from_text(text: str) -> str:
    text = clean_text(text)
    patterns = [
        r"主要研究方向[为是：: ]*([^。；;\n]+)",
        r"研究方向[为是：: ]*([^。；;\n]+)",
        r"长期从事([^。；;\n]+?)研究",
        r"从事([^。；;\n]+?)研究",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        value = clean_text(m.group(1)).strip("：:，, ")
        value = re.sub(r"^(为|是)", "", value).strip("：:，, ")
        if any(bad in value for bad in ("博士后", "教师工作", "我国", "方向教学")):
            continue
        if 2 <= len(value) <= 80:
            return value
    return ""


class NankaiCcAdapter:
    school_name = "南开大学计算机学院（师资队伍全部栏目）"
    list_url = LIST_URL
    output_md = Path("outputs/md/nankai_cc_teachers.md")
    output_json = Path("outputs/json/nankai_cc_teachers.json")
    output_html_dir = Path("outputs/html/nankai_cc_lists")
    profile_html_dir = Path("outputs/html/nankai_cc_profiles")
    profile_workers = 8

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return [url for _, url in LIST_PAGES]

    def fetch_list_page(self, page_url: str) -> str:
        from core import fetch

        html = fetch(page_url)
        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        key = page_url.strip("/").split("/")[-2]
        self.output_html_dir.joinpath(f"{key}.html").write_text(html, encoding="utf-8")
        return html

    def page_category_from_html(self, html: str) -> str:
        m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        return clean_text(strip_html(m.group(1))) if m else ""

    def extract_static_table_rows(self, html: str, page_category: str) -> list[dict]:
        teachers: list[dict] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            if 'data-label="姓名"' not in tr:
                continue
            fields = {}
            for label, value in re.findall(
                r'<td[^>]+data-label=["\']([^"\']+)["\'][^>]*>(.*?)</td>',
                tr,
                re.I | re.S,
            ):
                fields[clean_text(label)] = clean_text(strip_html(value))
            name = fields.get("姓名", "")
            title = fields.get("职务", "") or page_category
            unit = fields.get("本人工作单位", "")
            if not name:
                continue
            profile = "\n".join(
                line
                for line in [
                    f"职务：{title}" if title else "",
                    f"工作单位：{unit}" if unit else "",
                ]
                if line
            )
            teachers.append(
                {
                    "url": "",
                    "name": name,
                    "title": title,
                    "list_email": "",
                    "email": "",
                    "role": title or page_category,
                    "disciplines": "",
                    "categories": [page_category, title] if title and title != page_category else [page_category],
                    "profile_source": "列表页",
                    "profile": profile or "（列表页未提供更多信息）",
                }
            )
        return teachers

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        page_category = self.page_category_from_html(html)
        teachers: list[dict] = []
        for href, text in re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            re.I | re.S,
        ):
            name, title = normalize_name_title(text)
            if not name:
                continue
            if name in {"教授", "副教授", "讲师", "实验", "兼职", "退休", "博士后"}:
                continue
            if len(name) <= 1 or "/" in name or " " in name.strip():
                continue
            if not title or not any(
                key in title
                for key in ("教授", "研究员", "讲师", "实验师", "工程师", "博士后")
            ):
                continue
            if href.startswith("#") or href.lower().startswith("javascript:"):
                continue
            role = title or "教授/研究员"
            teachers.append(
                {
                    "url": urljoin(LIST_URL, href),
                    "name": name,
                    "title": title,
                    "list_email": "",
                    "email": "",
                    "role": role,
                    "disciplines": "",
                    "categories": [page_category, title] if title and page_category != title else ([page_category] if page_category else [role]),
                    "profile_source": "列表页",
                    "profile": f"职称：{title}" if title else "",
                }
            )
        teachers.extend(self.extract_static_table_rows(html, page_category))
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_html_dir.joinpath(f"{safe_filename(teacher['name'])}.html").write_text(
            html, encoding="utf-8"
        )

        name = clean_text(parse_profile_name(html)) or teacher["name"]
        title = field_value_from_label(html, "职称") or teacher.get("title", "")
        email = field_value_from_label(html, "电子邮件")
        direction = field_value_from_label(html, "研究方向")
        content = extract_article_content(html)
        if not direction:
            direction = extract_direction_from_text(content)

        profile_lines = []
        if title:
            profile_lines.append(f"职称：{title}")
        if email:
            profile_lines.append(f"电子邮件：{email}")
        if direction:
            profile_lines.append(f"研究方向：{direction}")
        if content:
            profile_lines.append(content)

        teacher.update(
            {
                "name": name,
                "title": title,
                "email": first_email(email) or first_email(content) or teacher.get("list_email", ""),
                "role": title or teacher.get("role", ""),
                "disciplines": direction,
                "categories": teacher.get("categories") or ([title] if title else []),
                "profile_source": "详情页",
                "profile": "\n".join(profile_lines) or content,
            }
        )
