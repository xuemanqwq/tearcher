"""Adapter for HFUT Computer and Information College faculty lists."""

import re
from pathlib import Path
from urllib.parse import urljoin

from core import first_email, parse_profile_name, strip_html

BASE = "https://ci.hfut.edu.cn"
LIST_PAGES = [
    ("教授", f"{BASE}/szdw/js.htm"),
    ("副教授", f"{BASE}/szdw/fjs.htm"),
    ("讲师", f"{BASE}/szdw/js1.htm"),
]
LIST_URL = LIST_PAGES[0][1]


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = text.replace("\xa0", " ").replace("\u3000", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_name(text: str) -> str:
    text = clean_text(text).replace("　", "")
    text = re.sub(r"^合肥工业大学主页平台管理系统\s*", "", text)
    if re.fullmatch(r"[\u4e00-\u9fff（）()兼 ]+", text):
        return text.replace(" ", "")
    return text


def page_category(page_url: str) -> str:
    for category, url in LIST_PAGES:
        if page_url == url:
            return category
    return ""


def extract_cards(html: str) -> list[tuple[str, str]]:
    cards: list[tuple[str, str]] = []
    for match in re.finditer(r'<span\s+class=["\']name["\']>\s*(.*?)\s*</span>', html, re.I | re.S):
        role = clean_text(strip_html(match.group(1)))
        start = match.end()
        next_card = re.search(r'<span\s+class=["\']name["\']>', html[start:], re.I)
        next_script = html.find("<script>_showDynClickBatch", start)
        footer = html.find('<div class="footer"', start)
        candidates = []
        if next_card:
            candidates.append(start + next_card.start())
        if next_script != -1:
            candidates.append(next_script)
        if footer != -1:
            candidates.append(footer)
        end = min(candidates) if candidates else len(html)
        cards.append((role, html[start:end]))
    return cards


def parse_article_field(profile: str, label: str) -> str:
    lines = [clean_text(line) for line in profile.splitlines() if clean_text(line)]
    normalized = label.replace(" ", "")
    for idx, line in enumerate(lines):
        if line.replace(" ", "") == normalized and idx + 1 < len(lines):
            return lines[idx + 1]
    return ""


def parse_title(profile: str, fallback: str) -> str:
    field_title = parse_article_field(profile, "职称")
    if field_title:
        return field_title

    lines = [clean_text(line) for line in profile.splitlines() if clean_text(line)]
    for line in lines[:40]:
        if any(title in line for title in ("教授", "副教授", "讲师", "研究员", "工程师")):
            if len(line) <= 30:
                return line
    return fallback


def parse_direction(profile: str) -> str:
    lines = [clean_text(line) for line in profile.splitlines() if clean_text(line)]
    stop_labels = {
        "教学工作",
        "获奖情况",
        "主要论著",
        "社会兼职",
        "教育经历",
        "工作经历",
        "团队成员",
        "其他联系方式",
        "招生信息",
        "科研项目",
        "论文成果",
        "专利成果",
        "著作成果",
        "教学研究",
    }

    chunks: list[str] = []
    for idx, line in enumerate(lines):
        if line in {"研究方向", "研究领域"} or line.startswith(("研究方向：", "研究方向:", "研究领域：", "研究领域:")):
            inline = re.sub(r"^研究[方向领域]+[：:]?", "", line).strip()
            if inline:
                chunks.append(inline)
            for nxt in lines[idx + 1 : idx + 12]:
                if nxt in stop_labels or any(marker in nxt for marker in ("Copyright", "联系我们", "手机版", "您是第")):
                    break
                if len(nxt) <= 80:
                    chunks.append(nxt)
            break

    if not chunks:
        for pattern in [
            r"主要研究领域[为是]?(.*?)(?:。|；|;|\n)",
            r"主要研究方向[为是]?(.*?)(?:。|；|;|\n)",
            r"研究方向包括(.*?)(?:。|；|;|\n)",
        ]:
            m = re.search(pattern, profile, re.S)
            if m:
                chunks.append(m.group(1))
                break

    items: list[str] = []
    for chunk in chunks:
        chunk = re.sub(r"（[^）]*）", "", chunk)
        chunk = re.sub(r"\([^)]*\)", "", chunk)
        for item in re.split(r"[、，,；;。]\s*|\n", chunk):
            item = clean_text(item).strip("：: ")
            if not item or len(item) > 60:
                continue
            if any(marker in item for marker in ("暂无内容", "欢迎", "报考", "联系", "Copyright", "TOP")):
                continue
            items.append(item)
    return "、".join(dict.fromkeys(items))


class HfutCiAdapter:
    school_name = "合肥工业大学计算机与信息学院（人工智能学院，全体教师）"
    list_url = LIST_URL
    output_md = Path("outputs/md/hfut_ci_teachers.md")
    output_json = Path("outputs/json/hfut_ci_teachers.json")
    output_html_dir = Path("outputs/html/hfut_ci_lists")
    profile_html_dir = Path("outputs/html/hfut_ci_profiles")
    profile_workers = 4

    def dedup_key(self, teacher: dict) -> str:
        return teacher.get("url") or teacher["name"]

    def get_list_page_urls(self) -> list[str]:
        return [url for _, url in LIST_PAGES]

    def extract_teachers_from_list(self, html: str) -> list[dict]:
        category = ""
        title = re.search(r"<title>([^<]+)</title>", html, re.I)
        if title:
            category = title.group(1).split("-")[0].strip()

        self.output_html_dir.mkdir(parents=True, exist_ok=True)
        if category:
            self.output_html_dir.joinpath(f"{category}.html").write_text(html, encoding="utf-8")

        teachers: list[dict] = []
        for role, card_html in extract_cards(html):
            if role not in {"博士生导师", "硕士生导师", "其他"}:
                continue
            for href, raw_name in re.findall(
                r'<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                card_html,
                re.I | re.S,
            ):
                name = normalize_name(strip_html(raw_name))
                if not name:
                    continue
                url = "" if "javascript:" in href.lower() else urljoin(LIST_URL, href)
                teachers.append(
                    {
                        "url": url,
                        "name": name,
                        "title": category,
                        "list_email": "",
                        "email": "",
                        "role": role,
                        "disciplines": "",
                        "categories": [category, role],
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
        name = parse_article_field(profile, "姓名") or parse_article_field(profile, "姓 名")
        if not name:
            name = clean_text(parse_profile_name(html).split("--")[0].split("-")[0])
            name = re.sub(r"^合肥工业大学主页平台管理系统\s*", "", name)
        name = normalize_name(name)
        if not name or name.lower() in {"error", "404", "not found"}:
            name = teacher["name"]

        teacher.update(
            {
                "name": name,
                "title": parse_title(profile, teacher.get("title", "")),
                "email": first_email(profile) or first_email(html) or teacher.get("list_email", ""),
                "disciplines": parse_direction(profile),
                "profile_source": "详情页",
                "profile": profile,
            }
        )
