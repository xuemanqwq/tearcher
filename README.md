# Tearcher

高校教师/导师信息抓取工具。项目通过站点适配器抓取不同学校或机构的教师列表，并导出 Markdown 与 JSON。

## 目录结构

- `scrape_teachers.py`: 命令行入口。
- `core.py`: 通用抓取、解析和导出逻辑。
- `adapters/`: 各学校/机构的站点适配器。
- `outputs/md/`: Markdown 导出结果。
- `outputs/json/`: JSON 导出结果。
- `outputs/html/`: 调试或留存用的 HTML 页面样本。
- `analyse/`: 院校名单分析脚本及其数据产物。

## 使用

列出可用站点：

```bash
python scrape_teachers.py --list
```

抓取指定站点：

```bash
python scrape_teachers.py siat
```

结果会写入：

- `outputs/md/`
- `outputs/json/`

