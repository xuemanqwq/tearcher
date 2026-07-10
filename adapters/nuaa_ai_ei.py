"""Adapter for NUAA Graduate School — 人工智能学院 0854电子信息 招生导师."""

import json
import urllib.parse
import urllib.request
from pathlib import Path

from core import (
    USER_AGENT,
    parse_tsites_profile_content,
    parse_tsites_profile_email,
    parse_tsites_profile_name,
    parse_tsites_profile_title,
)

BASE = "https://graduate.nuaa.edu.cn/gmis5/dsfc"
LIST_URL = "https://graduate.nuaa.edu.cn/gmis5/dsfc/dsfc_yx_new"
COLLEGE_ID = "024"  # 人工智能学院
DISCIPLINE_KEY = "0854"  # 0854电子信息
API_URL = f"{BASE}/getdsxxpage"

ROLE_MAP = {"bdList": "博导", "sdList": "硕导", "jzbdList": "兼职博导"}


def fetch_college_teachers(xsbh: str = COLLEGE_ID) -> dict:
    data = urllib.parse.urlencode({"xsbh": xsbh}).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": LIST_URL,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _discipline_matches(block: dict) -> bool:
    name = block.get("zymc") or block.get("xkmc") or ""
    return DISCIPLINE_KEY in name


def _add_teacher(bucket: dict, item: dict, discipline: str, role: str) -> None:
    dsbh = item.get("dsbh")
    if not dsbh:
        return
    url = (item.get("dsfcurl") or "").strip()
    if dsbh not in bucket:
        bucket[dsbh] = {
            "dsbh": dsbh,
            "name": item.get("dsxm", "").strip(),
            "url": url,
            "roles": set(),
            "disciplines": set(),
            "list_email": "",
        }
    rec = bucket[dsbh]
    if item.get("dsxm"):
        rec["name"] = item["dsxm"].strip()
    if url:
        rec["url"] = url
    if discipline:
        rec["disciplines"].add(discipline)
    if role:
        rec["roles"].add(role)


def _collect_from_block(bucket: dict, block: dict) -> None:
    discipline = block.get("zymc") or block.get("xkmc") or ""
    for key, role in ROLE_MAP.items():
        for item in block.get(key) or []:
            _add_teacher(bucket, item, discipline, role)


def parse_api_teachers(data: dict, *, discipline_only: bool = True) -> list[dict]:
    bucket: dict[str, dict] = {}
    for yjxk in data.get("yjxk") or []:
        blocks = []
        if not discipline_only or _discipline_matches(yjxk):
            blocks.append(yjxk)
        for zy in yjxk.get("zy") or []:
            if not discipline_only or _discipline_matches(zy):
                blocks.append(zy)
        for block in blocks:
            _collect_from_block(bucket, block)
    teachers = []
    for rec in bucket.values():
        roles = "、".join(
            sorted(
                rec["roles"],
                key=lambda r: ("博导", "硕导", "兼职博导").index(r)
                if r in ("博导", "硕导", "兼职博导")
                else 9,
            )
        )
        disciplines = "；".join(sorted(rec["disciplines"]))
        teachers.append(
            {
                "url": rec["url"],
                "name": rec["name"],
                "title": "",
                "list_email": "",
                "role": roles,
                "disciplines": disciplines,
                "dsbh": rec["dsbh"],
            }
        )
    teachers.sort(key=lambda t: t["name"])
    return teachers


class NuaaAiEiAdapter:
    school_name = "南京航空航天大学人工智能学院（0854电子信息，2026招生导师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/nuaa_ai_ei_teachers.md")
    output_json = Path("outputs/json/nuaa_ai_ei_teachers.json")

    def get_list_page_urls(self) -> list[str]:
        return [LIST_URL]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        data = fetch_college_teachers(COLLEGE_ID)
        return parse_api_teachers(data, discipline_only=True)

    def parse_profile(self, html: str, teacher: dict) -> None:
        title = parse_tsites_profile_title(html)
        profile = parse_tsites_profile_content(html)

        list_name = teacher["name"]
        profile_name = parse_tsites_profile_name(html)
        if profile_name and (not list_name or len(profile_name) >= len(list_name)):
            name = profile_name
        else:
            name = list_name or profile_name

        teacher.update(
            {
                "name": name,
                "title": title,
                "email": parse_tsites_profile_email(html, teacher["list_email"]),
                "profile": profile or "（主页暂无详细介绍）",
            }
        )
