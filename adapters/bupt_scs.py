"""Adapter for BUPT School of Computer Science faculty list."""

from pathlib import Path
from urllib.parse import urljoin, urlparse
import re
import urllib.request

from bs4 import BeautifulSoup

from core import first_email, strip_html


OFFICIAL_LIST_URL = "https://scs.bupt.edu.cn/szjs1/jsyl.htm"
MIRROR_LIST_URL = "https://m.southhoodye.com/scs/szjs1/jsyl.htm"
OFFICIAL_BASE = "https://scs.bupt.edu.cn"
MIRROR_BASE = "https://m.southhoodye.com"
BROWSER_HTML = Path("outputs/html/bupt_scs_lists/jsyl_browser.html")


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\ufeff", "").replace("\u200b", "").split())


def fetch_mirror(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
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
    if parsed.netloc == "m.southhoodye.com" and parsed.path.startswith("/scs/"):
        return OFFICIAL_BASE + parsed.path[len("/scs") :]
    if parsed.netloc == "m.southhoodye.com" and parsed.path.startswith("/teacher/"):
        return "https://teacher.bupt.edu.cn" + parsed.path[len("/teacher") :]
    return url


def to_mirror_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("https://scs.bupt.edu.cn/"):
        return url.replace("https://scs.bupt.edu.cn/", MIRROR_BASE + "/scs/", 1)
    if url.startswith("https://teacher.bupt.edu.cn/"):
        return url.replace("https://teacher.bupt.edu.cn/", MIRROR_BASE + "/teacher/", 1)
    return url


class BuptScsAdapter:
    school_name = "北京邮电大学计算机学院（国家示范性软件学院）"
    list_url = OFFICIAL_LIST_URL
    output_md = Path("outputs/md/bupt_scs_teachers.md")
    output_json = Path("outputs/json/bupt_scs_teachers.json")
    output_html_dir = Path("outputs/html/bupt_scs_lists")
    output_profile_html_dir = Path("outputs/html/bupt_scs_profiles")
    fetch_profiles = False
    profile_workers = 8

    def get_list_page_urls(self) -> list[str]:
        return [MIRROR_LIST_URL]

    def fetch_list_page(self, url: str) -> str:
        if BROWSER_HTML.exists():
            return BROWSER_HTML.read_text(encoding="utf-8")
        return fetch_mirror(url)

    def fetch_profile_page(self, teacher: dict) -> str:
        profile_url = to_mirror_url(teacher.get("mirror_url") or teacher.get("url", ""))
        return fetch_mirror(profile_url) if profile_url else ""

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        self.output_html_dir.joinpath("jsyl.html").write_text(html or "", encoding="utf-8")

        soup = BeautifulSoup(html or "", "html.parser")
        teachers: list[dict] = []
        seen = set()

        for table in soup.select("table.teacher_table"):
            center_node = table.find_previous("h3")
            center = clean_text(center_node.get_text(" ", strip=True)) if center_node else ""
            for link_node in table.select("a[href]"):
                raw_name = clean_text(link_node.get_text(" ", strip=True))
                name = re.sub(r"[（(].*?[）)]", "", raw_name).strip()
                if not name or len(name) > 8:
                    continue
                url = to_official_url(urljoin(OFFICIAL_BASE + "/", link_node.get("href", "")))
                key = url or f"{center}:{name}"
                if key in seen:
                    continue
                seen.add(key)
                teachers.append(
                    {
                        "url": url,
                        "mirror_url": to_mirror_url(url),
                        "name": name,
                        "raw_name": raw_name,
                        "title": "",
                        "list_email": "",
                        "email": "",
                        "role": "",
                        "disciplines": "",
                        "categories": [center] if center else [],
                        "center": center,
                        "research_direction": "",
                        "profile_source": "教师一览页",
                        "profile": f"所属中心：{center}" if center else "",
                    }
                )

        if teachers:
            return teachers

        for link_node in soup.select("a[href]"):
            href = link_node.get("href", "")
            if "teacher.bupt.edu.cn" not in href:
                continue
            raw_name = clean_text(link_node.get_text(" ", strip=True))
            name = re.sub(r"[（(].*?[）)]", "", raw_name).strip()
            if not name or len(name) > 8:
                continue
            url = to_official_url(urljoin(OFFICIAL_BASE + "/", href))
            if url in seen:
                continue
            seen.add(url)
            teachers.append(
                {
                    "url": url,
                    "mirror_url": to_mirror_url(url),
                    "name": name,
                    "raw_name": raw_name,
                    "title": "",
                    "list_email": "",
                    "email": "",
                    "role": "",
                    "disciplines": "",
                    "categories": [],
                    "center": "",
                    "research_direction": "",
                    "profile_source": "教师一览页",
                    "profile": "",
                }
            )
        return teachers

    def parse_profile(self, html: str, teacher: dict) -> None:
        profile_url = to_mirror_url(teacher.get("mirror_url") or teacher.get("url", ""))
        if profile_url:
            try:
                html = fetch_mirror(profile_url)
            except Exception:
                pass

        self.output_profile_html_dir.mkdir(parents=True, exist_ok=True)
        safe_name = teacher["name"].replace("/", "_").replace("\\", "_")
        self.output_profile_html_dir.joinpath(f"{safe_name}.html").write_text(html, encoding="utf-8")

        soup = BeautifulSoup(html, "html.parser")
        text = ""
        for selector in [".v_news_content", ".wp_articlecontent", ".teacherInfo", ".main", ".content", "body"]:
            node = soup.select_one(selector)
            if node:
                candidate = strip_html(str(node))
                if len(candidate) > len(text):
                    text = candidate

        email = first_email(text) or first_email(html[:20000])
        if email:
            teacher["email"] = email

        if not teacher.get("title"):
            m = re.search(r"职称[：:]\s*([^\n ]+)", text)
            if m:
                teacher["title"] = clean_text(m.group(1))

        if not teacher.get("research_direction"):
            m = re.search(r"研究方向[：:]\s*([^\n]+)", text)
            if m:
                teacher["research_direction"] = clean_text(m.group(1))

        parts = [teacher.get("profile", "")]
        if text and "米兰体育" not in text:
            parts.append(text)
        teacher["profile"] = "\n\n".join(part for part in parts if part).strip()
        teacher["profile_source"] = "详情页" if text else teacher.get("profile_source", "教师一览页")
