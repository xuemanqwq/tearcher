"""Adapter for CAS Shenyang Institute of Automation graduate advisors."""

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import first_email, parse_profile_name, strip_html

BASE = "https://sia.cas.cn"
LIST_PAGES = [
    ("博士导师", f"{BASE}/zpjy/yjsjy/dsjj/bsds/"),
    ("硕士导师", f"{BASE}/zpjy/yjsjy/dsjj/ssds/"),
]
LIST_URL = LIST_PAGES[0][1]


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_name(text: str) -> str:
    text = clean_text(text)
    if re.fullmatch(r"[\u4e00-\u9fff·]+", text):
        return text.replace(" ", "")
    return text


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def list_role(page_url: str) -> str:
    for role, url in LIST_PAGES:
        if page_url.rstrip("/") == url.rstrip("/"):
            return role
    return ""


def extract_table_rows(html: str, page_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    role = list_role(page_url)
    teachers: list[dict] = []

    for table in soup.find_all("table"):
        headers = [clean_text(cell.get_text(" ", strip=True)) for cell in table.find_all("td")[:5]]
        if headers != ["序号", "姓名", "部门名称", "性别", "招生专业"]:
            continue

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue
            values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells[:5]]
            if values[0] == "序号" or not values[1]:
                continue

            link = cells[1].find("a", href=True)
            url = urljoin(page_url, link["href"]) if link else ""
            name = normalize_name(values[1])
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": "",
                    "list_email": "",
                    "email": "",
                    "role": role,
                    "disciplines": values[4],
                    "department": values[2],
                    "gender": values[3],
                    "categories": [role, values[4]],
                    "profile_source": "列表页",
                    "profile": "",
                }
            )
    if teachers:
        return teachers

    current_department = ""
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if not cells:
                continue

            colspan = int(cells[0].get("colspan") or "1")
            if len(cells) == 1 or colspan > 1:
                current_department = clean_text(cells[0].get_text(" ", strip=True))
                continue

            for cell in cells:
                link = None
                for candidate in cell.find_all("a", href=True):
                    if clean_text(candidate.get_text(" ", strip=True)):
                        link = candidate
                        break
                name = normalize_name(
                    link.get_text(" ", strip=True) if link else cell.get_text(" ", strip=True)
                )
                if not name:
                    continue
                url = urljoin(page_url, link["href"]) if link else ""
                teachers.append(
                    {
                        "url": url,
                        "name": name,
                        "title": "",
                        "list_email": "",
                        "email": "",
                        "role": role,
                        "disciplines": "",
                        "department": current_department,
                        "gender": "",
                        "categories": [item for item in [role, current_department] if item],
                        "profile_source": "列表页",
                        "profile": "",
                    }
                )
    return teachers


def parse_profile_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    labels = [
        "职称",
        "电子邮件",
        "通信地址",
        "研究领域",
        "招生专业",
        "招生方向",
        "教育背景",
        "学历",
        "学位",
    ]
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for idx, line in enumerate(lines):
        for label in labels:
            if line == label and idx + 1 < len(lines):
                fields[label] = lines[idx + 1]
            elif line.startswith(label + "：") or line.startswith(label + ":"):
                fields[label] = clean_text(re.split(r"[:：]", line, 1)[1])
    return fields


def parse_direction(text: str, fallback: str) -> str:
    fields = parse_profile_fields(text)
    for label in ("研究领域", "招生方向", "招生专业"):
        if fields.get(label):
            return fields[label]
    for pattern in [
        r"研究方向[:：]\s*([^\n]+)",
        r"研究领域[:：]\s*([^\n]+)",
        r"主要研究方向[:：]\s*([^\n]+)",
    ]:
        m = re.search(pattern, text)
        if m:
            return clean_text(m.group(1))
    return fallback


class SiaCasAdapter:
    school_name = "中国科学院沈阳自动化研究所（硕博导师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/sia_cas_advisors.md")
    output_json = Path("outputs/json/sia_cas_advisors.json")
    output_html_dir = Path("outputs/html/sia_cas_lists")
    profile_html_dir = Path("outputs/html/sia_cas_profiles")
    profile_workers = 8

    def get_list_page_urls(self) -> list[str]:
        return [url for _, url in LIST_PAGES]

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or teacher["name"]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        title = parse_profile_name(html)
        role = "博士导师" if "博士导师" in title else "硕士导师" if "硕士导师" in title else ""
        page_url = dict(LIST_PAGES).get(role, LIST_URL)

        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        if role:
            self.output_html_dir.joinpath(f"{role}.html").write_text(html, encoding="utf-8")

        return extract_table_rows(html, page_url)

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_html_dir.joinpath(f"{safe_filename(teacher['name'])}.html").write_text(
            html, encoding="utf-8"
        )

        profile = strip_html(html)
        fields = parse_profile_fields(profile)
        title = fields.get("职称", "") or teacher.get("title", "")
        email = first_email(fields.get("电子邮件", "")) or first_email(profile) or first_email(html)
        disciplines = parse_direction(profile, teacher.get("disciplines", ""))
        roles = [item for item in teacher.get("categories", []) if item in {"博士导师", "硕士导师"}]
        role = "、".join(dict.fromkeys(roles)) or teacher.get("role", "")

        teacher.update(
            {
                "title": title,
                "email": email,
                "role": role,
                "disciplines": disciplines,
                "profile_source": "详情页",
                "profile": profile,
            }
        )
