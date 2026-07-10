"""Adapter for SIAT graduate supervisor list, limited to 集成所 and 医工所."""

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import strip_html

LIST_URL = "https://www.siat.ac.cn/jyjx/zsxx/dsdw/202508/t20250806_7901275.html"
TARGET_DEPARTMENTS = {"集成所", "医工所"}


def clean_text(text: str) -> str:
    text = text.replace("\u200b", "").replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def clean_multiline(text: str) -> str:
    text = text.replace("\u200b", "").replace("\xa0", " ").replace("\u3000", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def html_text(node) -> str:
    if not node:
        return ""
    html = str(node).replace("</br>", "<br/>")
    return clean_multiline(strip_html(html))


def cell_value(cell, base_url: str) -> dict[str, str]:
    link = cell.find("a")
    href = link.get("href") if link else ""
    return {
        "text": clean_text(cell.get_text("\n", strip=True)),
        "href": urljoin(base_url, href) if href else "",
    }


def expanded_table_rows(table, base_url: str) -> list[list[dict[str, str]]]:
    active: dict[int, tuple[dict[str, str], int]] = {}
    rows = []
    for tr in table.find_all("tr"):
        row = []
        col = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while col in active:
                value, remaining = active[col]
                row.append(value)
                remaining -= 1
                if remaining:
                    active[col] = (value, remaining)
                else:
                    del active[col]
                col += 1

            value = cell_value(cell, base_url)
            row.append(value)
            rowspan = int(cell.get("rowspan") or 1)
            if rowspan > 1:
                active[col] = (value, rowspan - 1)
            col += 1

        while col in active and col < 5:
            value, remaining = active[col]
            row.append(value)
            remaining -= 1
            if remaining:
                active[col] = (value, remaining)
            else:
                del active[col]
            col += 1

        if row:
            rows.append(row)
    return rows


def profile_text(department: str, unit: str, role: str, research: str) -> str:
    return "\n".join(
        part
        for part in (
            f"部门：{department}",
            f"单元：{unit}",
            f"导师类别：{role}",
            f"研究方向：{research}" if research else "",
        )
        if part
    )


class SiatDsdwAdapter:
    school_name = "中国科学院深圳先进技术研究院（集成所、医工所导师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/siat_jicheng_yigong_teachers.md")
    output_json = Path("outputs/json/siat_jicheng_yigong_teachers.json")
    profile_workers = 12

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return []

        teachers = []
        for row in expanded_table_rows(table, LIST_URL):
            if len(row) < 5:
                continue
            department, unit, name, role, research = [col["text"] for col in row[:5]]
            if department not in TARGET_DEPARTMENTS or name == "姓名":
                continue
            teachers.append(
                {
                    "url": row[2]["href"],
                    "name": name,
                    "title": "",
                    "list_email": "",
                    "email": "",
                    "role": role,
                    "department": department,
                    "unit": unit,
                    "research": research,
                    "categories": [department, unit],
                    "profile": profile_text(department, unit, role, research),
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        if "people.ucas." not in teacher.get("url", ""):
            return

        soup = BeautifulSoup(html, "html.parser")
        page_name = parse_ucas_name(soup) or teacher["name"]
        basic = parse_ucas_basic(soup)
        sections = parse_ucas_sections(soup)
        title = parse_ucas_title(sections)
        email = parse_ucas_email(basic) or teacher.get("email", "")
        role = parse_ucas_role(basic) or teacher.get("role", "")

        profile_parts = [
            profile_text(
                teacher.get("department", ""),
                teacher.get("unit", ""),
                teacher.get("role", ""),
                teacher.get("research", ""),
            )
        ]
        if basic:
            profile_parts.extend(["", "UCAS基本信息：", basic])
        for heading, content in sections:
            if content:
                profile_parts.extend(["", heading, content])

        teacher.update(
            {
                "name": page_name,
                "title": title or teacher.get("title", ""),
                "email": email,
                "role": role,
                "profile": "\n".join(profile_parts).strip(),
            }
        )


def parse_ucas_name(soup: BeautifulSoup) -> str:
    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    return title.split("-")[0].strip() if title else ""


def parse_ucas_basic(soup: BeautifulSoup) -> str:
    block = soup.select_one(".bp-enty")
    return html_text(block)


def parse_ucas_email(text: str) -> str:
    m = re.search(r"[\w.+-]+@[\w.-]+", text)
    return m.group(0) if m else ""


def parse_ucas_role(text: str) -> str:
    for role in ("博导", "硕导"):
        if role in text:
            return role
    return ""


def parse_ucas_title(sections: list[tuple[str, str]]) -> str:
    for heading, content in sections:
        if heading != "工作简历":
            continue
        for line in content.splitlines():
            if "现在" in line or "今" in line:
                parts = [part.strip(" ，,") for part in re.split(r"[,，]", line) if part.strip()]
                if parts:
                    return parts[-1]
    return ""


def parse_ucas_sections(soup: BeautifulSoup) -> list[tuple[str, str]]:
    sections = []
    for item in soup.select(".m-itme"):
        main_heading = clean_text(item.select_one(".mi-t").get_text(" ", strip=True)) if item.select_one(".mi-t") else ""
        direct_box = item.find("div", class_="mi-box", recursive=False)
        if direct_box:
            direct_text = html_text(direct_box)
            if direct_text:
                sections.append((main_heading, direct_text))

        for sub_box in item.find_all("div", class_="mi-box", recursive=False):
            sub_heading = sub_box.find("h5", class_="mib-t")
            if not sub_heading:
                continue
            heading = clean_text(sub_heading.get_text(" ", strip=True))
            content_box = sub_box.find("div", class_="mib-c")
            content = html_text(content_box)
            if heading and content:
                sections.append((heading, content))
    return dedupe_sections(sections)


def dedupe_sections(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    result = []
    for heading, content in sections:
        key = (heading, content)
        if key in seen:
            continue
        seen.add(key)
        result.append((heading, content))
    return result
