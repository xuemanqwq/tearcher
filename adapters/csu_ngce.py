"""Adapter for CSU National Graduate College of Engineers master advisors."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core import first_email, parse_meta_description, strip_html


MASTER_LIST_URL = "https://ngce.csu.edu.cn/dsdw/sssds.htm"
DOCTORAL_LIST_URL = "https://ngce.csu.edu.cn/dsdw/bssds.htm"
LIST_URL = MASTER_LIST_URL


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_name(text: str) -> str:
    text = clean_text(text)
    text = text.replace("　", "").replace(" ", "")
    return text


def extract_title(profile: str, name: str) -> str:
    lines = [clean_text(line) for line in profile.splitlines() if clean_text(line)]
    for i, line in enumerate(lines[:30]):
        if normalize_name(line) == normalize_name(name):
            for candidate in lines[i + 1 : i + 8]:
                if any(title in candidate for title in ("教授", "副教授", "研究员", "讲师", "工程师")):
                    return candidate
    for line in lines[:60]:
        if any(title in line for title in ("教授", "副教授", "研究员", "讲师", "工程师")) and len(line) <= 30:
            return line
    return ""


def extract_unit(profile: str) -> str:
    for label in ("所在单位", "学科", "办公地点"):
        m = re.search(rf"{label}[:：]\s*([^\n]+)", profile)
        if m:
            return clean_text(m.group(1))
    return ""


def extract_research_directions(profile: str, html: str, name: str) -> str:
    lines = [clean_text(line) for line in profile.splitlines() if clean_text(line)]
    directions: list[str] = []
    for i, line in enumerate(lines):
        if line in {"研究方向", "研究领域", "科研方向"}:
            local: list[str] = []
            for nxt in lines[i + 1 : i + 12]:
                if nxt in {
                    "其他联系方式",
                    "教育经历",
                    "工作经历",
                    "社会兼职",
                    "论文成果",
                    "科研项目",
                    "招生招聘",
                    "招生计划",
                    "主讲课程",
                    "学术成果",
                    "论文成果",
                    "个人简介",
                }:
                    break
                if nxt in {"其他栏目", "English", "首页", "信息与网络中心", "手机版", "中南大学"}:
                    continue
                if re.match(r"^\[\d+\]", nxt):
                    local.append(re.sub(r"^\[\d+\]\s*", "", nxt))
                elif len(nxt) <= 60 and not any(
                    stop in nxt
                    for stop in ("访问量", "版权所有", "同专业", "信息与网络中心", "手机版", "中南大学")
                ):
                    local.append(nxt)
            local = [
                d
                for d in local
                if normalize_name(d) != normalize_name(name)
                and normalize_name(name) not in normalize_name(d)
                and d not in {"教授", "副教授", "讲师", "研究员", "副研究员"}
                and not re.fullmatch(r"[A-Za-z0-9_\\-]+", d)
                and not any(
                    menu in d
                    for menu in (
                        "其他栏目",
                        "个人简介",
                        "首页",
                        "团队成员",
                        "团队名称",
                        "语种切换",
                        "已经得到",
                        "更多",
                        "博士生导师",
                        "硕士生导师",
                        "所在单位",
                        "职称",
                        "学位",
                        "学历",
                        "学科",
                        "性别",
                        "入职时间",
                        "在职信息",
                    )
                )
            ]
            if local:
                directions = local
                break

    if directions:
        cleaned = [
            d
            for d in dict.fromkeys(directions)
            if normalize_name(d) != normalize_name(name) and not re.fullmatch(r"[A-Za-z0-9_\\-]+", d)
        ]
        return "；".join(cleaned)

    meta = parse_meta_description(html)
    if meta:
        meta = clean_text(meta)
        parts = re.split(r"[，,；;]\s*", meta)
        picked = [
            p
            for p in parts
            if 2 <= len(p) <= 40
            and "中南大学" not in p
            and "团队成员" not in p
            and "团队名称" not in p
            and "信息与网络中心" not in p
            and "手机版" not in p
            and "语种切换" not in p
            and "已经得到" not in p
            and p != "更多"
            and "博士生导师" not in p
            and "硕士生导师" not in p
            and "所在单位" not in p
            and "职称" not in p
            and "学位" not in p
            and "学科" not in p
            and "性别" not in p
            and normalize_name(p) != normalize_name(name)
            and normalize_name(name) not in normalize_name(p)
            and p not in {"教授", "副教授", "讲师", "研究员", "副研究员"}
            and not re.fullmatch(r"[A-Za-z0-9_\\-]+", p)
        ]
        if picked:
            return "；".join(dict.fromkeys(picked[:8]))
    return ""


class CsuNgceAdapter:
    school_name = "中南大学国家卓越工程师学院（硕士生导师）"
    list_url = MASTER_LIST_URL
    output_md = Path("outputs/md/csu_ngce_master_advisors.md")
    output_json = Path("outputs/json/csu_ngce_master_advisors.json")
    output_html = Path("outputs/html/csu_ngce_sssds.html")
    profile_html_dir = Path("outputs/html/csu_ngce_profiles")
    profile_workers = 8
    role_label = "硕士生导师"

    def get_list_page_urls(self) -> list[str]:
        return [self.list_url]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html.parent.mkdir(parents=True, exist_ok=True)
        self.output_html.write_text(html, encoding="utf-8")

        soup = BeautifulSoup(html, "html.parser")
        teachers: list[dict] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            name = normalize_name(a.get_text(" ", strip=True))
            if not name or not re.fullmatch(r"[\u4e00-\u9fff·]{2,6}", name):
                continue
            if "faculty.csu.edu.cn" not in href and "faculty.csu.edu.cn" not in urljoin(self.list_url, href):
                continue
            url = urljoin(self.list_url, href)
            key = url.lower()
            if key in seen:
                continue
            seen.add(key)
            teachers.append(
                {
                    "url": url,
                    "name": name,
                    "title": "",
                    "list_email": "",
                    "email": "",
                    "role": self.role_label,
                    "disciplines": "",
                    "categories": [self.role_label],
                    "profile_source": "列表页",
                    "profile": "",
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        self.profile_html_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", teacher["name"])
        self.profile_html_dir.joinpath(f"{safe_name}.html").write_text(html, encoding="utf-8")

        profile = strip_html(html)
        directions = extract_research_directions(profile, html, teacher["name"])
        teacher.update(
            {
                "title": extract_title(profile, teacher["name"]),
                "email": first_email(profile) or first_email(html),
                "disciplines": directions,
                "department": extract_unit(profile),
                "profile_source": "详情页",
                "profile": profile,
            }
        )


class CsuNgcePhdAdapter(CsuNgceAdapter):
    school_name = "中南大学国家卓越工程师学院（博士生导师）"
    list_url = DOCTORAL_LIST_URL
    output_md = Path("outputs/md/csu_ngce_doctoral_advisors.md")
    output_json = Path("outputs/json/csu_ngce_doctoral_advisors.json")
    output_html = Path("outputs/html/csu_ngce_bssds.html")
    profile_html_dir = Path("outputs/html/csu_ngce_phd_profiles")
    role_label = "博士生导师"
