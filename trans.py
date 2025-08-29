import markdown
import datetime
import os
import glob
import re
import shutil

TEMPLATE_FILE = os.path.join("html", "template.html")
with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
    TEMPLATE = f.read()

WEEKDAY_MAP = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

input_folder = "markdown"
output_dir = os.path.join("html", "output")
output_file = os.path.join(output_dir, "diaries.html")
pictures_folder = os.path.join(output_dir, "Pictures")

os.makedirs(pictures_folder, exist_ok=True)

diaries_html = []

for filepath in sorted(glob.glob(os.path.join(input_folder, "**/*.md"), recursive=True)):
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
with open(output_file, "w", encoding="utf-8") as f:
    content_html = "\n".join(diaries_html)
    f.write(TEMPLATE.replace("{{CONTENT_HTML}}", content_html))

logo_src = os.path.join("html", "logo.png")
logo_dst = os.path.join(output_dir, "logo.png")
if os.path.exists(logo_src):
    shutil.copy2(logo_src, logo_dst)

background_src = os.path.join("html", "background.png")
background_dst = os.path.join(output_dir, "background.png")
if os.path.exists(background_src):
    shutil.copy2(background_src, background_dst)
else:
    print(f"[WARNING] 背景图片 {background_src} 不存在")

print(f"[INFO] 已生成 {output_file}")
