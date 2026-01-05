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

REVERSE_ORDER = True  # True表示按时间倒序排序

# 获取脚本所在目录（项目根目录）
script_dir = os.path.dirname(os.path.abspath(__file__))

# 从项目根目录的 html 文件夹读取模板文件（不是 base_folder/html）
TEMPLATE_FILE = os.path.join(script_dir, "html", "template.html")
if not os.path.exists(TEMPLATE_FILE):
    raise FileNotFoundError(f"模板文件不存在: {TEMPLATE_FILE}")

with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
    TEMPLATE = f.read()

WEEKDAY_MAP = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 输入输出路径（base_folder 是 myself 或 partner）
input_folder = os.path.join(script_dir, base_folder, "markdown")
output_dir = os.path.join(script_dir, base_folder, "html")  # 输出到 myself/html
pictures_folder = os.path.join(output_dir, "Pictures")

# 创建输出目录
os.makedirs(output_dir, exist_ok=True)
os.makedirs(pictures_folder, exist_ok=True)

diaries_html = []

# 获取所有 markdown 文件
filepaths = sorted(glob.glob(os.path.join(
    input_folder, "**/*.md"), recursive=True))

if REVERSE_ORDER:
    filepaths = list(reversed(filepaths))

# 处理每个日记文件
for filepath in filepaths:
    filename = os.path.basename(filepath)
    name, _ = os.path.splitext(filename)

    with open(filepath, "r", encoding="utf-8") as f:
        diary_md = f.read()

    # 移除第一行（日期标题）
    diary_md = re.sub(r'^\s*.*\n', '', diary_md, count=1)

    # 处理图片引用
    for md_img_match in re.findall(r'!\[.*?\]\((.*?)\)', diary_md):
        img_name = os.path.basename(md_img_match)
        original_img_path = os.path.join(
            os.path.dirname(filepath), md_img_match)

        # 复制图片到输出目录
        if os.path.exists(original_img_path):
            target_img_path = os.path.join(pictures_folder, img_name)
            # 避免重复复制
            if not os.path.exists(target_img_path):
                shutil.copy2(original_img_path, target_img_path)

        # 更新 markdown 中的图片路径
        diary_md = diary_md.replace(md_img_match, f"./Pictures/{img_name}")

    # 将 Markdown 转换为 HTML
    diary_html = markdown.markdown(
        diary_md, extensions=["fenced_code", "tables", "nl2br"])

    # 解析日期
    try:
        date = datetime.datetime.strptime(name, "%Y-%m-%d").date()
    except:
        date = datetime.date.today()

    weekday = WEEKDAY_MAP[date.weekday()]

    # 生成日记 HTML 片段
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

# 生成最终的 HTML 文件
output_file = os.path.join(output_dir, "diaries.html")
with open(output_file, "w", encoding="utf-8") as f:
    f.write(TEMPLATE.replace("{{CONTENT_HTML}}", "\n".join(diaries_html)))

# 复制 logo 和背景图到输出目录（从项目根目录/html/ 复制到 myself/html/）
for fname in ["logo.png", "background.png"]:
    src = os.path.join(script_dir, "html", fname)
    dst = os.path.join(output_dir, fname)
    if os.path.exists(src):
        shutil.copy2(src, dst)

print(f"[INFO] 已生成 {output_file}")
