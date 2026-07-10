#!/usr/bin/env python3
"""Scrape university faculty lists via site-specific adapters.

Usage:
    python scrape_teachers.py buaa    # 北航计算机学院
    python scrape_teachers.py jlu     # 吉大人工智能学院
    python scrape_teachers.py hhu     # 河海大学计算机与软件学院
    python scrape_teachers.py dlmu_ist # 大连海事大学信息科学技术学院
    python scrape_teachers.py dlut_ice # 大连理工大学信息与通信工程学院
    python scrape_teachers.py siat   # 深圳先进院集成所、医工所导师
    python scrape_teachers.py buaa_soft  # 北航软件学院（全部师资目录）
    python scrape_teachers.py tju    # 天津大学通信工程系
    python scrape_teachers.py tju_cs # 天津大学计算机学院硕导
    python scrape_teachers.py --list  # 列出可用站点
"""

import argparse
import sys

from adapters import ADAPTERS
from core import run_scraper


def main():
    parser = argparse.ArgumentParser(description="高校教师信息爬虫")
    parser.add_argument(
        "school",
        nargs="?",
        help=f"学校代号: {', '.join(ADAPTERS)}",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用学校",
    )
    args = parser.parse_args()

    if args.list or not args.school:
        print("可用学校:")
        for key, cls in ADAPTERS.items():
            adapter = cls()
            print(f"  {key:6}  {adapter.school_name}")
            print(f"         {adapter.list_url}")
        if not args.school:
            sys.exit(0 if args.list else 1)
        return

    key = args.school.lower()
    if key not in ADAPTERS:
        print(f"未知学校: {args.school}")
        print(f"可用: {', '.join(ADAPTERS)}")
        sys.exit(1)

    run_scraper(ADAPTERS[key]())


if __name__ == "__main__":
    main()
