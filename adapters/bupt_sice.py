"""Adapter for BUPT School of Information and Communication Engineering."""

from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
import urllib.request

from bs4 import BeautifulSoup

from core import first_email, strip_html


OFFICIAL_LIST_URL = "https://sice.bupt.edu.cn/szdw1.htm"
MIRROR_LIST_URL = "https://m.southhoodye.com/sice/szdw1.htm"
OFFICIAL_BASE = "https://sice.bupt.edu.cn"
MIRROR_BASE = "https://m.southhoodye.com"
BROWSER_HTML = Path("outputs/html/bupt_sice_lists/szdw1_browser.html")


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\ufeff", "").replace("\u200b", "").split())


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://sice.bupt.edu.cn/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def to_official_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if parsed.netloc == "m.southhoodye.com" and parsed.path.startswith("/sice/"):
        return OFFICIAL_BASE + parsed.path[len("/sice") :]
    if parsed.netloc == "m.southhoodye.com" and parsed.path.startswith("/teacher/"):
        return "https://teacher.bupt.edu.cn" + parsed.path[len("/teacher") :]
    return url


def to_mirror_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("https://sice.bupt.edu.cn/"):
        return url.replace("https://sice.bupt.edu.cn/", MIRROR_BASE + "/sice/", 1)
    if url.startswith("https://teacher.bupt.edu.cn/"):
        return url.replace("https://teacher.bupt.edu.cn/", MIRROR_BASE + "/teacher/", 1)
    return url


def parse_inline_fields(text: str) -> dict[str, str]:
    labels = ["姓名", "性别", "职务", "老师类型", "所属中心", "职称", "研究方向", "个人介绍"]
    fields: dict[str, str] = {}
    for i, label in enumerate(labels):
        start = text.find(label)
        if start == -1:
            continue
        value_start = start + len(label)
        end = len(text)
        for next_label in labels[i + 1 :]:
            pos = text.find(next_label, value_start)
            if pos != -1:
                end = min(end, pos)
        value = clean_text(text[value_start:end])
        if value:
            fields[label] = value
    return fields


class BuptSiceAdapter:
    school_name = "北京邮电大学信息与通信工程学院"
    list_url = OFFICIAL_LIST_URL
    output_md = Path("outputs/md/bupt_sice_teachers.md")
    output_json = Path("outputs/json/bupt_sice_teachers.json")
    output_html_dir = Path("outputs/html/bupt_sice_lists")
    output_profile_html_dir = Path("outputs/html/bupt_sice_profiles")
    fetch_profiles = False

    def get_list_page_urls(self) -> list[str]:
        return [MIRROR_LIST_URL]

    def fetch_list_page(self, url: str) -> str:
        # The official page has a browser-side security challenge. If a browser
        # dump exists, prefer it because it contains the real rendered list.
        if BROWSER_HTML.exists():
            return BROWSER_HTML.read_text(encoding="utf-8")
        try:
            html = fetch_html(url)
            if len(html) > 1000 and "502 Bad Gateway" not in html:
                return html
        except Exception as exc:
            mirror_error = exc
        else:
            mirror_error = RuntimeError("mirror returned empty or bad gateway")
        try:
            return fetch_html(OFFICIAL_LIST_URL)
        except Exception as exc:
            return (
                "<html><body>"
                "<!-- BUPT SICE list unavailable: "
                f"mirror={mirror_error!r}; official={exc!r}"
                " -->"
                "</body></html>"
            )

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        self.output_html_dir.joinpath("szdw1.html").write_text(html or "", encoding="utf-8")

        soup = BeautifulSoup(html or "", "html.parser")
        teachers: list[dict] = []
        seen = set()

        for center_block in soup.select(".jxxb-c"):
            center_node = center_block.select_one(".article-tt, .title_ h3, h3, .title_")
            center = clean_text(center_node.get_text(" ", strip=True)) if center_node else ""
            for group_block in center_block.select(".list_li"):
                title_node = group_block.select_one(".btt, .fl")
                title = clean_text(title_node.get_text(" ", strip=True)).rstrip("：:") if title_node else ""
                for link_node in group_block.select("ul.ul_list a[href], a[href]"):
                    raw_name = clean_text(link_node.get_text(" ", strip=True))
                    name = re.sub(r"[（(].*?[）)]", "", raw_name).strip()
                    if not name or len(name) > 8:
                        continue
                    href = link_node.get("href", "")
                    url = to_official_url(urljoin(OFFICIAL_BASE + "/", href))
                    key = url or f"{center}:{title}:{name}"
                    if key in seen:
                        continue
                    seen.add(key)
                    teachers.append(
                        {
                            "url": url,
                            "mirror_url": to_mirror_url(url),
                            "name": name,
                            "raw_name": raw_name,
                            "title": title,
                            "list_email": "",
                            "email": "",
                            "role": "",
                            "disciplines": "",
                            "categories": [c for c in [center, title] if c],
                            "center": center,
                            "research_direction": "",
                            "profile_source": "列表页",
                            "profile": "\n".join(
                                part
                                for part in [
                                    f"所属教研中心：{center}" if center else "",
                                    f"职称/类别：{title}" if title else "",
                                ]
                                if part
                            ),
                        }
                    )

        if teachers:
            return teachers

        for item in soup.select("li"):
            link_node = item.select_one("a[href]")
            name_node = item.select_one("h4") or link_node
            if not name_node:
                continue
            raw_name = clean_text(name_node.get_text(" ", strip=True))
            name = re.sub(r"[（(].*?[）)]", "", raw_name).strip()
            if not name or len(name) > 8 or name in {"首页", "师资队伍", "更多"}:
                continue
            href = link_node.get("href", "") if link_node else ""
            url = to_official_url(urljoin(OFFICIAL_BASE + "/", href))
            key = url or name
            if key in seen:
                continue
            seen.add(key)

            summary = clean_text(item.get_text(" ", strip=True))
            fields = parse_inline_fields(summary)
            teachers.append(
                {
                    "url": url,
                    "mirror_url": to_mirror_url(url),
                    "name": name,
                    "raw_name": raw_name,
                    "title": fields.get("职称", ""),
                    "list_email": "",
                    "email": first_email(summary),
                    "role": fields.get("老师类型", ""),
                    "disciplines": "",
                    "categories": ["师资队伍"],
                    "research_direction": fields.get("研究方向", ""),
                    "profile_source": "列表页",
                    "profile": summary,
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        profile_url = to_mirror_url(teacher.get("mirror_url") or teacher.get("url", ""))
        if profile_url:
            try:
                html = fetch_html(profile_url)
            except Exception:
                pass

        self.output_profile_html_dir.mkdir(parents=True, exist_ok=True)
        safe_name = teacher["name"].replace("/", "_").replace("\\", "_")
        self.output_profile_html_dir.joinpath(f"{safe_name}.html").write_text(html, encoding="utf-8")

        text = strip_html(html)
        email = first_email(text)
        if email:
            teacher["email"] = email
        teacher["profile"] = "\n\n".join(part for part in [teacher.get("profile", ""), text] if part).strip()
        teacher["profile_source"] = "详情页"
