import requests
import os
import re
import base64
from Crypto.Cipher import AES
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import subprocess
import sys
import shutil

EMAIL = ""
PASSWORD = ""
ORDER_OLD_TO_NEW = True
MAX_WORKERS = 5

# ========== 设置 ==========
# True 表示只有选择默认日期范围时才会下载图片
DOWNLOAD_IMAGES_ONLY_DEFAULT = True
# =========================


def login(email, password):
    url = "https://nideriji.cn/api/login/"
    headers = {'User-Agent': 'OhApp/3.6.12 Platform/Android'}
    data = {'email': email, 'password': password}
    r = requests.post(url, headers=headers, data=data)
    r.raise_for_status()
    token = r.json().get('token')
    if not token:
        raise ValueError("登录失败，未获取到 token")
    print("[INFO] 登录成功")
    return token


def clean_unicode(text):
    for prefix in ["\\ud83c", "\\ud83d", "\\ud83e"]:
        text = text.replace(prefix, "")
    return text


def decrypt_privacy(content, user_id):
    def decrypt_block(match):
        cipher_text = match.group(1)
        key = str(user_id).encode('utf-8')
        aes = AES.new(key.ljust(16, b'\0'), AES.MODE_ECB)
        try:
            decrypted = aes.decrypt(bytes.fromhex(cipher_text))
            return "[隐私区域开始]" + decrypted.decode('utf-8', errors='ignore') + "[隐私区域结束]"
        except:
            try:
                decrypted = aes.decrypt(base64.b64decode(cipher_text))
                return "[隐私区域开始]" + decrypted.decode('utf-8', errors='ignore') + "[隐私区域结束]"
            except:
                return match.group(0)
    pattern = re.compile(
        r"\[以下是隐私区域密文，请不要做任何编辑，否则可能导致解密失败\]([\s\S]+?)\[以上是隐私日记，请不要编辑密文\]")
    return pattern.sub(decrypt_block, content)


def get_diaries_overview(token, partner=False):
    headers = {'auth': f'token {token}',
               'User-Agent': 'OhApp/3.6.12 Platform/Android'}
    r = requests.post("https://nideriji.cn/api/v2/sync/",
                      headers=headers,
                      data={'user_config_ts': '0', 'diaries_ts': '0',
                            'readmark_ts': '0', 'images_ts': '0'})
    r.raise_for_status()
    data = r.json()

    if partner:
        diaries = data.get('diaries_paired', [])
        all_image_ids = [img['image_id']
                         for img in data.get('images_paired', [])]
        user_id = data['user_config']['paired_user_config']['userid']
    else:
        diaries = data.get('diaries', [])
        all_image_ids = [img['image_id'] for img in data.get('images', [])]
        user_id = data['user_config']['userid']

    print(f"[INFO] 获取到 {len(all_image_ids)} 张图片 ID")
    if diaries:
        print(
            f"[INFO] 获取日记总数: {len(diaries)} 篇，日期范围: {diaries[-1]['createddate']} - {diaries[0]['createddate']}")
    return diaries, user_id, all_image_ids


def get_diary_full(token, user_id, diary_id):
    headers = {'auth': f'token {token}',
               'User-Agent': 'OhApp/3.6.12 Platform/Android'}
    r = requests.post(f"https://nideriji.cn/api/diary/all_by_ids/{user_id}/",
                      headers=headers,
                      data={'diary_ids': diary_id})
    r.raise_for_status()
    data = r.json()
    if 'diaries' in data and data['diaries']:
        d = data['diaries'][0]
        d['content'] = clean_unicode(d.get('content', ''))
        d['content'] = decrypt_privacy(d['content'], user_id)
        return d
    return None


def filter_diaries_by_date(diaries, start_date, end_date):
    filtered = [d for d in diaries if start_date <= datetime.datetime.strptime(
        d['createddate'], "%Y-%m-%d").date() <= end_date]
    filtered.sort(key=lambda x: x['createddate'], reverse=not ORDER_OLD_TO_NEW)
    print(f"[INFO] {len(filtered)} 篇日记在指定范围内")
    return filtered


def save_diary(diary, markdown_folder):
    diary_date = datetime.datetime.strptime(
        diary['createddate'], "%Y-%m-%d").date()
    folder_name = os.path.join(
        markdown_folder, f"{diary_date.year}-{diary_date.month:02d}")
    os.makedirs(folder_name, exist_ok=True)
    filename = os.path.join(folder_name, f"{diary_date}.md")
    with open(filename, 'w', encoding='utf-8') as f:
        weekday = diary.get('weekday', '')
        f.write(f"=={diary['createddate']} {weekday}==\n")
        f.write(diary.get('title', '') + '\n')
        f.write(diary.get('content', ''))


def download_all_images(image_ids, user_id, headers, pictures_folder):
    os.makedirs(pictures_folder, exist_ok=True)
    print(f"[INFO] 开始下载 {len(image_ids)} 张图片")
    for image_id in tqdm(image_ids, desc="下载图片", unit="img"):
        url = f"https://f.nideriji.cn/api/image/{user_id}/{image_id}/"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            with open(os.path.join(pictures_folder, f"{image_id}.jpg"), 'wb') as f:
                f.write(r.content)
        except Exception as e:
            print(f"[WARN] 下载图片 {image_id} 失败: {e}")


def replace_images_in_markdown(diaries, markdown_folder, pictures_folder):
    md_files = []
    for d in diaries:
        diary_date = datetime.datetime.strptime(
            d['createddate'], "%Y-%m-%d").date()
        folder_name = os.path.join(
            markdown_folder, f"{diary_date.year}-{diary_date.month:02d}")
        md_files.append(os.path.join(folder_name, f"{diary_date}.md"))
    for md_file in tqdm(md_files, desc="替换图片路径", unit="篇"):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        content = re.sub(
            r'\[图(\d+)\]', lambda m: f"![img]({os.path.join(pictures_folder, f'{m.group(1)}.jpg')})", content)
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(content)


def run_trans_script(base_folder):
    try:
        result = subprocess.run([sys.executable, "trans.py", base_folder],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print("[INFO] HTML文件生成成功！")
            print(result.stdout)
            return True
        else:
            print("[ERROR] HTML文件生成失败")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"[ERROR] 运行 trans.py 时出错: {e}")
        return False


if __name__ == "__main__":
    email = input(f"请输入邮箱：") or EMAIL
    password = input(f"请输入密码: ") or PASSWORD
    token = login(email, password)

    choice = input("输入1保存自己的日记，输入2保存搭档的日记：") or "1"
    partner = choice == "2"

    # ---------------- 用户基准目录 ----------------
    base_folder = "partner" if partner else "myself"
    markdown_folder = os.path.join(base_folder, "markdown")
    html_folder = os.path.join(base_folder, "html")
    pictures_folder = os.path.join(html_folder, "output", "Pictures")
    os.makedirs(markdown_folder, exist_ok=True)
    os.makedirs(html_folder, exist_ok=True)
    os.makedirs(os.path.join(html_folder, "output"), exist_ok=True)

    # ---------------- 拷贝模板、logo、背景 ----------------
    src_html_dir = "html"  # 原始模板存放位置
    for fname in ["template.html", "logo.png", "background.png"]:
        src = os.path.join(src_html_dir, fname)
        dst = os.path.join(html_folder, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    diaries_overview, user_id, all_image_ids = get_diaries_overview(
        token, partner)

    first_date = datetime.datetime.strptime(
        diaries_overview[-1]['createddate'], "%Y-%m-%d").year
    now = datetime.datetime.now()
    start_year = int(input(f"请输入起始年份 [{first_date}]: ") or first_date)
    start_month = int(input("请输入起始月份 [1]: ") or 1)
    end_year = int(input(f"请输入结束年份 [{now.year}]: ") or now.year)
    end_month = int(input(f"请输入结束月份 [{now.month}]: ") or now.month)
    start_date = datetime.date(start_year, start_month, 1)
    end_day = (datetime.date(end_year, end_month + 1, 1) -
               datetime.timedelta(days=1)).day if end_month < 12 else 31
    end_date = datetime.date(end_year, end_month, end_day)

    filtered_diaries = filter_diaries_by_date(
        diaries_overview, start_date, end_date)

    headers = {'auth': f'token {token}',
               'User-Agent': 'OhApp/3.6.12 Platform/Android'}

    print("[INFO] 下载并保存日记...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(
            get_diary_full, token, user_id, d['id']) for d in filtered_diaries]
        full_diaries = []
        for future in tqdm(as_completed(futures), total=len(futures), desc="下载日记", unit="篇"):
            diary = future.result()
            if diary:
                save_diary(diary, markdown_folder)
                full_diaries.append(diary)

    used_default_range = (
        start_year == first_date and start_month == 1 and
        end_year == now.year and end_month == now.month
    )

    if not DOWNLOAD_IMAGES_ONLY_DEFAULT or used_default_range:
        download_all_images(all_image_ids, user_id, headers, pictures_folder)
        replace_images_in_markdown(full_diaries, markdown_folder, "./Pictures")
    else:
        print("[INFO] 非默认日期范围，跳过下载图片步骤")

    print("[INFO] 日记导出完成！")

    generate_html_choice = input("是否生成HTML文件？(y/n): ").lower()
    if generate_html_choice == 'y':
        success = run_trans_script(base_folder)
        if success:
            print(f"[INFO] 所有操作完成！HTML文件已生成在 {html_folder}/output/ 目录")
        else:
            print("[WARNING] HTML生成失败，但Markdown文件已保存")
    else:
        print("[INFO] 跳过HTML生成")
