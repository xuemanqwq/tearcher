"""Adapter for ECNU IEEIC full-time faculty directory."""

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from core import USER_AGENT

LIST_URL = "https://ieeic.ecnu.edu.cn/zrjs/list.htm"
API_URL = "https://ieeic.ecnu.edu.cn/_wp3services/generalQuery?queryObj=articles"
SITE_ID = 157
COLUMN_ID = 48889

RETURN_INFOS = [
    {"field": "title", "name": "title"},
    {"field": "f1", "name": "f1"},
    {"field": "f3", "name": "f3"},
    {"field": "f4", "name": "f4"},
    {"field": "f5", "name": "f5"},
    {"field": "f6", "name": "f6"},
    {"field": "f7", "name": "f7"},
    {"field": "f8", "name": "f8"},
    {"field": "f9", "name": "f9"},
    {"field": "publishTime", "name": "publishTime"},
    {"field": "imgPath", "name": "imgPath"},
]


def clean_text(text: str) -> str:
    text = (text or "").replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_email(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"\s*(?:\[AT\]|\[at\]|\(AT\)|\(at\)|＠)\s*", "@", text)
    text = re.sub(r"\s*(?:\[DOT\]|\[dot\]|\(DOT\)|\(dot\))\s*", ".", text)
    return text


def fetch_api(page_index: int = 1, rows: int = 300) -> dict:
    payload = {
        "siteId": SITE_ID,
        "columnId": COLUMN_ID,
        "pageIndex": page_index,
        "rows": rows,
        "orders": json.dumps([], ensure_ascii=False),
        "returnInfos": json.dumps(RETURN_INFOS, ensure_ascii=False),
        "conditions": json.dumps([{"field": "scope", "value": 0, "judge": "="}], ensure_ascii=False),
    }
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


class EcnuIeeicAdapter:
    school_name = "华东师范大学信息与电子工程学院（集成电路科学与工程学院）专任教师"
    list_url = LIST_URL
    output_md = Path("outputs/md/ecnu_ieeic_teachers.md")
    output_json = Path("outputs/json/ecnu_ieeic_teachers.json")
    output_html = Path("outputs/html/ecnu_ieeic_zrjs.html")
    output_api_json = Path("outputs/html/ecnu_ieeic_zrjs_api.json")
    fetch_profiles = False

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("id") or teacher.get("url") or teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        result = fetch_api()
        self.output_api_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        teachers: list[dict] = []
        for item in result.get("data", []):
            name = clean_text(item.get("title", ""))
            if not name:
                continue
            title = clean_text(item.get("f1", "")) or clean_text(item.get("f8", ""))
            email = normalize_email(item.get("f5", ""))
            direction = clean_text(item.get("f3", ""))
            office = clean_text(item.get("f6", ""))
            talent = clean_text(item.get("f7", ""))
            rank = clean_text(item.get("f8", ""))
            department = clean_text(item.get("f9", ""))
            url = clean_text(item.get("url", "")) or clean_text(item.get("wapUrl", ""))
            image_url = urljoin(LIST_URL, item.get("imgPath") or item.get("mircImgPath") or "")

            categories = [x for x in (rank, department, talent) if x]
            profile_lines = [
                f"职称/称号：{title}" if title else "",
                f"职称类别：{rank}" if rank else "",
                f"系所：{department}" if department else "",
                f"高层次人才：{talent}" if talent else "",
                f"研究方向：{direction}" if direction else "",
                f"办公室：{office}" if office else "",
                f"邮箱：{email}" if email else "",
                f"头像：{image_url}" if image_url else "",
            ]

            teachers.append(
                {
                    "id": str(item.get("id", "")),
                    "url": url,
                    "name": name,
                    "title": title,
                    "list_email": email,
                    "email": email,
                    "role": rank,
                    "disciplines": direction,
                    "categories": categories,
                    "department": department,
                    "talent": talent,
                    "office": office,
                    "image_url": image_url,
                    "publish_time": clean_text(item.get("publishTime", "")),
                    "profile_source": "接口列表",
                    "profile": "\n".join(line for line in profile_lines if line)
                    or "（接口未提供更多信息）",
                }
            )
        return teachers
