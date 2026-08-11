"""Adapter for Zhejiang University Ocean College faculty directory."""

import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core import first_email, parse_profile_name, strip_html

BASE = "http://oc.zju.edu.cn"
LIST_URL = "http://oc.zju.edu.cn/53722/list.htm"

LIST_PAGES = [
    ("海洋地质与资源研究所Marine Geology & Resources", "http://oc.zju.edu.cn/53722/list.htm"),
    ("海洋化学与环境研究所Marine Chemistry & Environment", "http://oc.zju.edu.cn/53723/list.htm"),
    ("物理海洋与遥感研究所Physical Oceanography & Remote Sensing", "http://oc.zju.edu.cn/53724/list.htm"),
    ("海洋生物与药物研究所Marine Biology & Pharmacy", "http://oc.zju.edu.cn/53725/list.htm"),
    ("海洋工程与技术研究所Ocean Engineering & Technology", "http://oc.zju.edu.cn/53726/list.htm"),
    ("海洋结构物与船舶工程研究所Marine Structures & Naval Architectures", "http://oc.zju.edu.cn/53727/list.htm"),
    ("港口海岸与近海工程研究所Port,Coastal & Offshore Engineering", "http://oc.zju.edu.cn/53728/list.htm"),
    ("海洋传感与网络研究所Ocean Sensing & Networking", "http://oc.zju.edu.cn/53729/list.htm"),
    ("海洋电子与智能系统研究所Ocean Electronics & Systems", "http://oc.zju.edu.cn/53730/list.htm"),
    ("港航物流与自由贸易岛研究中心Maritime Logistics & Free Trade Islands Research Center", "http://oc.zju.edu.cn/53731/list.htm"),
    ("海洋研究院Ocean Academy", "http://oc.zju.edu.cn/yjy/list.htm"),
    ("海洋研究院Ocean Academy", "http://oc.zju.edu.cn/fyjy/list.htm"),
    ("海洋研究院Ocean Academy", "http://oc.zju.edu.cn/zlyjy/list.htm"),
    ("海洋研究院Ocean Academy", "http://oc.zju.edu.cn/jrjs/list.htm"),
]

ROLE_TITLES = {
    "教授/研究员",
    "副教授/副研究员",
    "讲师",
    "学科博士后",
    "讲座教授",
    "兼任教师",
    "兼聘教师",
    "研究员",
    "副研究员",
    "助理研究员",
}


def clean_text(text: str) -> str:
    text = (text or "").replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def page_key(url: str) -> str:
    path = urlparse(url).path.strip("/").replace("/", "_")
    return path.replace(".htm", "") or "list"


def current_page_title(soup: BeautifulSoup) -> str:
    for node in soup.find_all("h1"):
        text = clean_text(node.get_text(" ", strip=True))
        if text and text not in {"师资队伍", "联系我们"}:
            return text
    title = soup.find("title")
    return clean_text(title.get_text(" ", strip=True)) if title else ""


def profile_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".wp_articlecontent")
    if node:
        text = strip_html(str(node))
        if text:
            return text
    return strip_html(html)


def field_from_profile(text: str, labels: tuple[str, ...]) -> str:
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    for i, line in enumerate(lines):
        for label in labels:
            if line.rstrip("：:") == label and i + 1 < len(lines):
                return lines[i + 1]
            m = re.match(rf"^{re.escape(label)}[：:]\s*(.+)$", line, re.I)
            if m:
                return clean_text(m.group(1))
    return ""


def extract_direction(text: str, fallback: str = "") -> str:
    return (
        field_from_profile(text, ("研究方向", "研究领域", "学科方向"))
        or field_from_profile(text, ("学科",))
        or fallback
    )


class ZjuOcAdapter:
    school_name = "浙江大学海洋学院师资队伍"
    list_url = LIST_URL
    output_md = Path("outputs/md/zju_oc_teachers.md")
    output_json = Path("outputs/json/zju_oc_teachers.json")
    output_html_dir = Path("outputs/html/zju_oc_lists")
    profile_html_dir = Path("outputs/html/zju_oc_profiles")
    profile_workers = 12

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or f"{'|'.join(teacher.get('categories', []))}|{teacher['name']}"

    def get_list_page_urls(self) -> list[str]:
        return [url for _, url in LIST_PAGES]

    def institute_for_url(self, url: str) -> str:
        for institute, page_url in LIST_PAGES:
            if page_url == url:
                return institute
        return ""

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        page_title = current_page_title(soup)
        institute = page_title if page_title and page_title not in ROLE_TITLES else ""

        # Ocean Academy role pages use role titles as page titles.
        if not institute:
            institute = "海洋研究院Ocean Academy"

        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        name = safe_filename(page_title or "list")
        self.output_html_dir.joinpath(f"{name}.html").write_text(html, encoding="utf-8")

        teachers: list[dict] = []
        categories = soup.select(".team_con .category")
        if not categories:
            categories = soup.select(".category")

        for category in categories:
            role_node = category.select_one(".institute")
            role = clean_text(role_node.get_text(" ", strip=True)) if role_node else page_title
            if not role or role not in ROLE_TITLES:
                role = page_title if page_title in ROLE_TITLES else role

            for li in category.find_all("li"):
                link = li.find("a", class_="photo", href=True) or li.find("a", href=True)
                name_node = li.select_one(".people_name")
                person_name = clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
                if not person_name and link:
                    person_name = clean_text(link.get_text(" ", strip=True)) or clean_text(link.get("title", ""))
                if not person_name or not link:
                    continue

                img = link.find("img")
                image_url = urljoin(BASE, img.get("src")) if img and img.get("src") else ""
                url = urljoin(BASE, link.get("href"))
                teachers.append(
                    {
                        "url": url,
                        "name": person_name,
                        "title": role,
                        "list_email": "",
                        "email": "",
                        "role": role,
                        "disciplines": "",
                        "categories": [x for x in (institute, role) if x],
                        "institute": institute,
                        "image_url": image_url,
                        "profile_source": "列表页",
                        "profile": "\n".join(
                            line
                            for line in (
                                f"研究所/中心：{institute}" if institute else "",
                                f"职称/类别：{role}" if role else "",
                                f"头像：{image_url}" if image_url else "",
                            )
                            if line
                        ),
                    }
                )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        self.profile_html_dir.joinpath(f"{safe_filename(teacher['name'])}.html").write_text(
            html, encoding="utf-8"
        )

        text = profile_content(html)
        title = field_from_profile(text, ("职称",)) or teacher.get("title", "")
        subject = field_from_profile(text, ("学科",))
        tel = field_from_profile(text, ("Tel", "电话"))
        office = field_from_profile(text, ("联系地址", "办公室"))
        email = first_email(text) or teacher.get("list_email", "")
        direction = extract_direction(text, teacher.get("disciplines", ""))
        profile_name = clean_text(parse_profile_name(html)) or teacher["name"]

        extra = []
        if tel:
            extra.append(f"电话：{tel}")
        if office:
            extra.append(f"联系地址：{office}")

        teacher.update(
            {
                "name": profile_name,
                "title": title,
                "role": teacher.get("role") or title,
                "email": email,
                "disciplines": direction,
                "subject": subject,
                "tel": tel,
                "office": office,
                "profile_source": "详情页",
                "profile": "\n".join([text, *extra]).strip() or teacher.get("profile", ""),
            }
        )
