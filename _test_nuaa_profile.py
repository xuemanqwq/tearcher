import re
import urllib.request

url = "https://faculty.nuaa.edu.cn/hejijun/zh_CN/index.htm"
html = urllib.request.urlopen(
    urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
).read().decode("utf-8")
print("emails", re.findall(r"[\w.+-]+@[\w.-]+", html))
m = re.search(r'class="cont profile">(.*?)</div>', html, re.S)
print("profile", m.group(1)[:500] if m else "none")
idx = html.find("infoCont")
print(html[idx : idx + 800])
