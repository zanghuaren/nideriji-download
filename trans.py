import markdown
import datetime
import os
import glob
import re
import shutil
import sys

# 接受 base_folder 参数
if len(sys.argv) > 1:
    base_folder = sys.argv[1]
else:
    base_folder = "myself"

REVERSE_ORDER = True
# True表示按时间倒序排序

TEMPLATE_FILE = os.path.join(base_folder, "html", "template.html")
if not os.path.exists(TEMPLATE_FILE):
    raise FileNotFoundError(f"{TEMPLATE_FILE} 不存在！")
with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
    TEMPLATE = f.read()

WEEKDAY_MAP = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

input_folder = os.path.join(base_folder, "markdown")
output_dir = os.path.join(base_folder, "html", "output")
pictures_folder = os.path.join(output_dir, "Pictures")
os.makedirs(pictures_folder, exist_ok=True)

diaries_html = []

filepaths = sorted(glob.glob(os.path.join(
    input_folder, "**/*.md"), recursive=True))
if REVERSE_ORDER:
    filepaths = list(reversed(filepaths))

for filepath in filepaths:
    filename = os.path.basename(filepath)
    name, _ = os.path.splitext(filename)

    with open(filepath, "r", encoding="utf-8") as f:
        diary_md = f.read()

    diary_md = re.sub(r'^\s*.*\n', '', diary_md, count=1)

    for md_img_match in re.findall(r'!\[.*?\]\((.*?)\)', diary_md):
        img_name = os.path.basename(md_img_match)
        original_img_path = os.path.join(
            os.path.dirname(filepath), md_img_match)
        if os.path.exists(original_img_path):
            shutil.copy2(original_img_path, os.path.join(
                pictures_folder, img_name))
        diary_md = diary_md.replace(md_img_match, f"./Pictures/{img_name}")

    diary_html = markdown.markdown(
        diary_md, extensions=["fenced_code", "tables", "nl2br"])

    try:
        date = datetime.datetime.strptime(name, "%Y-%m-%d").date()
    except:
        date = datetime.date.today()
    weekday = WEEKDAY_MAP[date.weekday()]

    article = f"""
<article class="diary">
  <header class="meta">
    <div class="date">{date}</div>
    <div class="weekday">{weekday}</div>
  </header>
  <h1 class="title"></h1>
  <section class="content">{diary_html}</section>
</article>
"""
    diaries_html.append(article)

os.makedirs(output_dir, exist_ok=True)
with open(os.path.join(output_dir, "diaries.html"), "w", encoding="utf-8") as f:
    f.write(TEMPLATE.replace("{{CONTENT_HTML}}", "\n".join(diaries_html)))

# 拷贝 logo 和背景
for fname in ["logo.png", "background.png"]:
    src = os.path.join(base_folder, "html", fname)
    dst = os.path.join(output_dir, fname)
    if os.path.exists(src):
        shutil.copy2(src, dst)

print(f"[INFO] 已生成 {os.path.join(output_dir, 'diaries.html')}")
