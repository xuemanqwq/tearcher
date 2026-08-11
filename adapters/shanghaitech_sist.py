"""Adapter for ShanghaiTech SIST faculty directory."""

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

from core import USER_AGENT, first_email, strip_html

BASE = "https://sist.shanghaitech.edu.cn"
LIST_URL = f"{BASE}/szdwx/list.htm"
QUERY_URL = f"{BASE}/_wp3services/generalQuery?queryObj=teacherHome"

LIST_CATEGORIES = [
    "常任教授",
    "特聘教授",
    "访问教授",
    "研究人员",
    "支撑人员",
    "行政人员",
]

RETURN_FIELDS = [
    "title",
    "graduateSchool",
    "degree",
    "phone",
    "email",
    "cnUrl",
    "headerPic",
    "exField1",
    "exField2",
    "exField3",
    "exField4",
    "exField5",
    "exField6",
    "exField7",
    "exField8",
    "exField9",
    "exField10",
]


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_filename(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", text).strip() or "profile"


def query_teacher_home(category: str) -> list[dict]:
    conditions = [
        {"field": "published", "value": "1", "judge": "="},
        {"field": "language", "value": "1", "judge": "="},
        {"field": "exField8", "value": category, "judge": "="},
    ]
    data = urllib.parse.urlencode(
        {
            "siteId": 43,
            "columnId": "",
            "conditions": json.dumps(conditions, ensure_ascii=False),
            "returnInfos": json.dumps(
                [{"field": field, "name": field} for field in RETURN_FIELDS],
                ensure_ascii=False,
            ),
            "pageIndex": 1,
            "orders": json.dumps([{"field": "siteSort", "type": "asc"}]),
            "rows": 999,
            "articleType": 1,
            "level": 1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        QUERY_URL,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    return payload.get("data") or []


def profile_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (".wp_articlecontent", ".wp_entry", ".entry", "main"):
        content = soup.select_one(selector)
        if content:
            text = strip_html(str(content))
            if len(text) > 80:
                return text
    return strip_html(html)


def parse_profile_direction(text: str) -> str:
    lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
    stop_words = {"招聘主页", "简介", "团队", "科研", "教学", "服务", "成果", "论文", "影集", "报道"}
    for line in lines:
        if line.startswith("研究方向"):
            value = clean_text(re.sub(r"^研究方向[：:]*", "", line))
            if value and value not in stop_words:
                return value.strip("：:；;，, ")
    for pattern in [
        r"主要研究方向[为是：: ]*([^\n。]+)",
        r"研究领域[为是：: ]*([^\n。]+)",
    ]:
        match = re.search(pattern, text)
        if match:
            value = clean_text(match.group(1)).strip("：:；;，, ")
            if value and value not in stop_words:
                return value
    return ""


class ShanghaitechSistAdapter:
    school_name = "上海科技大学信息科学与技术学院（师资队伍）"
    list_url = LIST_URL
    output_md = Path("outputs/md/shanghaitech_sist_teachers.md")
    output_json = Path("outputs/json/shanghaitech_sist_teachers.json")
    output_html = Path("outputs/html/shanghaitech_sist_teachers.html")
    profile_html_dir = Path("outputs/html/shanghaitech_sist_profiles")
    profile_workers = 8

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or f"{teacher['name']}|{teacher.get('category', '')}"

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        teachers: list[dict] = []
        for category in LIST_CATEGORIES:
            for item in query_teacher_home(category):
                name = clean_text(item.get("title") or "")
                if not name:
                    continue
                title = clean_text(item.get("exField1") or "")
                center = clean_text(item.get("exField5") or "")
                direction = clean_text(item.get("exField4") or "")
                url = clean_text(item.get("cnUrl") or "")
                teachers.append(
                    {
                        "url": url,
                        "name": name,
                        "title": title,
                        "list_email": clean_text(item.get("email") or ""),
                        "email": clean_text(item.get("email") or ""),
                        "role": title,
                        "disciplines": direction,
                        "category": category,
                        "center": center,
                        "phone": clean_text(item.get("phone") or ""),
                        "graduate_school": clean_text(item.get("graduateSchool") or ""),
                        "degree": clean_text(item.get("degree") or ""),
                        "categories": [part for part in [category, center, title] if part],
                        "profile_source": "接口列表",
                        "profile": "\n".join(
                            part
                            for part in [
                                f"栏目：{category}",
                                f"职称：{title}" if title else "",
                                f"研究中心：{center}" if center else "",
                                f"博士毕业院校：{clean_text(item.get('graduateSchool') or '')}"
                                if item.get("graduateSchool")
                                else "",
                                f"研究方向：{direction}" if direction else "",
                                f"电话：{clean_text(item.get('phone') or '')}" if item.get("phone") else "",
                            ]
                            if part
                        ),
                    }
                )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        cache_name = f"{safe_filename(teacher['category'])}-{safe_filename(teacher['name'])}.html"
        self.profile_html_dir.joinpath(cache_name).write_text(
            html, encoding="utf-8"
        )

        profile = profile_content(html)
        teacher.update(
            {
                "email": teacher.get("email", "") or first_email(profile) or first_email(html),
                "disciplines": parse_profile_direction(profile) or teacher.get("disciplines", ""),
                "profile_source": "详情页",
                "profile": profile,
            }
        )
