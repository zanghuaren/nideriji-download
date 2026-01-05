import urllib3
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
import json
import time
from typing import List, Dict, Set, Tuple
from urllib.parse import urlparse

# 配置
EMAIL = ""
PASSWORD = ""
ORDER_OLD_TO_NEW = True
MAX_WORKERS = 5  # 控制并发,减轻服务器压力
REQUEST_TIMEOUT = 15
REQUEST_INTERVAL = 0.1  # 请求间隔(秒)

# 禁用系统代理以避免SSL问题
urllib3.disable_warnings()


class Logger:
    """日志记录器"""

    def __init__(self, log_file="log.txt"):
        self.log_file = log_file
        # 清空或创建日志文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"=== 日记下载日志 ===\n")
            f.write(
                f"### 开始时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

    def log(self, message, level="INFO"):
        """写入日志"""
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_message = f"[{timestamp}] [{level}] {message}\n"

        # 写入文件
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message)

        # 同时输出到控制台(可选)
        print(log_message.strip())

    def info(self, message):
        self.log(message, "INFO")

    def warn(self, message):
        self.log(message, "WARN")

    def error(self, message):
        self.log(message, "ERROR")


# 创建全局日志器
logger = Logger()


class DiaryDownloader:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.token = None
        self.user_id = None
        self.partner_user_id = None
        self.session = requests.Session()
        self.session.verify = False  # 禁用SSL验证(如果遇到证书问题)
        self.session.trust_env = False  # 禁用系统代理
        self.session.headers.update({
            "User-Agent": "OhApp/3.6.12 Platform/Android"
        })

    def login(self):
        """登录获取token"""
        logger.info("正在登录...")
        url = "https://nideriji.cn/api/login/"
        data = {
            "email": self.email,
            "password": self.password
        }

        try:
            response = self.session.post(
                url, data=data, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()

            if result.get("error") != 0:
                raise ValueError(f"登录失败: {result}")

            self.token = result.get("token")
            self.user_id = result.get("userid")

            if not self.token:
                raise ValueError("登录失败,未获取到token")

            # 更新session的认证头
            self.session.headers.update({"auth": f"token {self.token}"})

            logger.info(f"登录成功,用户ID: {self.user_id}")
            time.sleep(REQUEST_INTERVAL)
            return True

        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False

    def get_sync_data(self, partner=False):
        """获取同步数据"""
        logger.info("正在获取日记列表...")
        url = "https://nideriji.cn/api/v2/sync/"
        data = {
            "user_config_ts": "0",
            "diaries_ts": "0",
            "readmark_ts": "0",
            "images_ts": "0"
        }

        try:
            response = self.session.post(
                url, data=data, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()

            if result.get("error") != 0:
                logger.error(f"同步失败: {result}")
                return None

            if partner:
                diaries = result.get("diaries_paired", [])
                user_config = result.get("user_config", {}).get(
                    "paired_user_config", {})
                user_id = user_config.get("userid")
                if not user_id:
                    user_id = self.user_id  # 备用方案
                logger.info(f"获取到搭档 {len(diaries)} 篇日记")
            else:
                diaries = result.get("diaries", [])
                user_config = result.get("user_config", {})
                user_id = user_config.get("userid", self.user_id)
                logger.info(f"获取到 {len(diaries)} 篇日记")

            # 按日期排序
            diaries.sort(key=lambda x: x.get("createddate", ""), reverse=True)

            time.sleep(REQUEST_INTERVAL)
            return {
                "diaries": diaries,
                "user_id": user_id,
                "user_config": user_config
            }

        except Exception as e:
            logger.error(f"获取同步数据失败: {e}")
            return None

    def get_full_diary_content(self, diary_id, author_user_id):
        """获取单篇完整日记内容"""
        url = f"https://nideriji.cn/api/diary/all_by_ids/{author_user_id}/"
        data = {"diary_ids": str(diary_id)}

        try:
            response = self.session.post(
                url, data=data, timeout=REQUEST_TIMEOUT)
            time.sleep(REQUEST_INTERVAL)
            response.raise_for_status()
            result = response.json()

            if result.get("error") != 0 or not result.get("diaries"):
                logger.warn(f"获取日记 {diary_id} 失败: {result}")
                return None

            diary = result["diaries"][0]

            # 清理内容
            content = diary.get("content", "")
            if content:
                # 解密隐私内容
                content = self.decrypt_privacy(content, author_user_id)
                # 提取图片ID
                image_ids = self.extract_image_ids(content)
            else:
                image_ids = set()

            return {
                "id": diary.get("id"),
                "user_id": diary.get("user"),
                "createddate": diary.get("createddate"),
                "title": diary.get("title", ""),
                "content": content,
                "weather": diary.get("weather", ""),
                "mood": diary.get("mood", ""),
                "space": diary.get("space", ""),
                "createdtime": diary.get("createdtime"),
                "image_ids": image_ids
            }

        except Exception as e:
            logger.error(f"获取日记 {diary_id} 详情失败: {e}")
            return None

    def decrypt_privacy(self, content, user_id):
        """解密隐私内容"""
        if not content or not user_id:
            return content

        try:
            # 查找隐私区域
            pattern = r'\[以下是隐私区域密文,请不要做任何编辑,否则可能导致解密失败\](.*?)\[以上是隐私日记,请不要编辑密文\]'
            matches = re.findall(pattern, content, re.DOTALL)

            if not matches:
                return content

            for cipher_text in matches:
                cipher_text = cipher_text.strip()
                if not cipher_text:
                    continue

                # 准备密钥
                key_str = str(user_id)
                key = key_str.encode('utf-8')

                # 填充到16字节
                if len(key) < 16:
                    key = key + b'\0' * (16 - len(key))
                elif len(key) > 16:
                    key = key[:16]

                # 创建AES解密器
                cipher = AES.new(key, AES.MODE_ECB)

                try:
                    # 尝试base64解码
                    cipher_bytes = base64.b64decode(cipher_text)
                except:
                    try:
                        # 尝试hex解码
                        cipher_bytes = bytes.fromhex(cipher_text)
                    except:
                        logger.warn(f"无法解码密文: {cipher_text[:50]}...")
                        continue

                # 解密
                decrypted = cipher.decrypt(cipher_bytes)

                # 移除PKCS7填充(如果存在)
                try:
                    padding_len = decrypted[-1]
                    if padding_len <= 16:
                        decrypted = decrypted[:-padding_len]
                except:
                    pass

                # 解码为字符串
                try:
                    decrypted_text = decrypted.decode(
                        'utf-8', errors='ignore').strip()
                except:
                    decrypted_text = "[隐私内容解密失败]"

                # 替换原文中的密文
                content = content.replace(
                    f"[以下是隐私区域密文,请不要做任何编辑,否则可能导致解密失败]{cipher_text}[以上是隐私日记,请不要编辑密文]",
                    f"[隐私内容开始]\n{decrypted_text}\n[隐私内容结束]"
                )

            return content

        except Exception as e:
            logger.warn(f"解密失败: {e}")
            return content

    def extract_image_ids(self, content):
        """从内容中提取图片ID"""
        if not content:
            return set()

        pattern = r'\[图(\d+)\]'
        matches = re.findall(pattern, content)

        # 转换为整数集合
        image_ids = set()
        for match in matches:
            try:
                image_ids.add(int(match))
            except:
                pass

        return image_ids

    def download_image(self, image_id, user_id, target_folder):
        """下载单张图片"""
        url = f"https://f.nideriji.cn/api/image/{user_id}/{image_id}/"

        try:
            # 下载图片
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            time.sleep(REQUEST_INTERVAL)
            response.raise_for_status()

            # 确定文件扩展名
            content_type = response.headers.get('content-type', '').lower()
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            else:
                # 尝试从内容判断
                if response.content[:3] == b'\xff\xd8\xff':
                    ext = '.jpg'
                elif response.content[:8] == b'\x89PNG\r\n\x1a\n':
                    ext = '.png'
                else:
                    ext = '.jpg'  # 默认

            # 保存图片
            image_path = os.path.join(target_folder, f"{image_id}{ext}")
            with open(image_path, 'wb') as f:
                f.write(response.content)

            return True

        except requests.exceptions.Timeout:
            logger.warn(f"下载图片 {image_id} 超时")
            return False
        except Exception as e:
            logger.warn(f"下载图片 {image_id} 失败: {e}")
            return False

    def save_diary_markdown(self, diary, base_folder):
        """保存日记为Markdown文件"""
        # 解析日期
        date_str = diary.get("createddate", "")
        if not date_str:
            return None

        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            logger.warn(f"无效的日期格式: {date_str}")
            return None

        # 创建年份-月份文件夹
        year_month = f"{date_obj.year}-{date_obj.month:02d}"
        month_folder = os.path.join(base_folder, "markdown", year_month)
        os.makedirs(month_folder, exist_ok=True)

        # 创建月份内的Pictures文件夹
        month_pictures_folder = os.path.join(month_folder, "Pictures")
        os.makedirs(month_pictures_folder, exist_ok=True)

        # 获取星期几
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekdays[date_obj.weekday()]

        # 构建Markdown内容
        title = diary.get("title", "")
        content = diary.get("content", "")
        weather = diary.get("weather", "")
        mood = diary.get("mood", "")

        # 去除每段开头可能的的四个空格缩进 注:否则会导致html正文排版溢出
        content_lines = content.split('\n')
        content_lines = [line[4:] if line.startswith(
            '    ') else line for line in content_lines]
        content = '\n'.join(content_lines)

        # 替换图片引用为相对路径(指向同一文件夹内的Pictures子文件夹)
        def replace_image_ref(match):
            image_id = match.group(1)
            return f"![图片{image_id}](Pictures/{image_id}.jpg)"

        content = re.sub(r'\[图(\d+)\]', replace_image_ref, content)

        # 构建完整的Markdown
        lines = []
        lines.append(f"=={date_str} {weekday}==")
        lines.append("")

        if title:
            lines.append(f"# {title}")
            lines.append("")

        if weather or mood:
            tags = []
            if weather:
                tags.append(f"天气: {weather}")
            if mood:
                tags.append(f"心情: {mood}")
            lines.append(f"**{' | '.join(tags)}**")
            lines.append("")

        lines.append(content)
        lines.append("")

        # 写入文件
        file_path = os.path.join(month_folder, f"{date_str}.md")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return {
            "file_path": file_path,
            "month_folder": month_folder,
            "year_month": year_month,
            "pictures_folder": month_pictures_folder,
            "image_ids": diary.get("image_ids", set())
        }

    def download_diaries(self, diaries_data, partner=False):
        """下载日记"""
        if not diaries_data or not diaries_data.get("diaries"):
            logger.error("没有日记数据")
            return False

        diaries = diaries_data["diaries"]
        author_user_id = diaries_data["user_id"]

        logger.info(f"准备下载 {len(diaries)} 篇日记...")

        # 选择基础文件夹
        base_folder = "partner" if partner else "myself"

        # 创建基础文件夹
        markdown_base = os.path.join(base_folder, "markdown")
        html_base = os.path.join(base_folder, "html")
        os.makedirs(markdown_base, exist_ok=True)
        os.makedirs(html_base, exist_ok=True)

        # 获取完整日记内容
        logger.info("正在获取日记详情...")
        full_diaries = []

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = []
            for diary in diaries:
                diary_id = diary.get("id")
                if diary_id:
                    future = executor.submit(
                        self.get_full_diary_content,
                        diary_id,
                        author_user_id
                    )
                    futures.append((diary, future))

            for diary, future in tqdm(futures, desc="获取日记", unit="篇"):
                try:
                    result = future.result(timeout=30)
                    if result:
                        full_diaries.append(result)
                except Exception as e:
                    logger.warn(f"获取日记失败: {e}")

        logger.info(f"成功获取 {len(full_diaries)} 篇完整日记")

        # 保存日记并按月份记录需要的图片
        logger.info("正在保存Markdown文件...")
        month_image_map = {}  # {year_month: {folder: path, image_ids: set()}}

        for diary in tqdm(full_diaries, desc="保存日记", unit="篇"):
            save_info = self.save_diary_markdown(diary, base_folder)
            if save_info:
                year_month = save_info["year_month"]
                if year_month not in month_image_map:
                    month_image_map[year_month] = {
                        "folder": save_info["pictures_folder"],
                        "image_ids": set()
                    }
                # 合并该月份的图片ID
                month_image_map[year_month]["image_ids"].update(
                    save_info["image_ids"])

        # 按需下载图片(每个月份的图片都下载到对应的Pictures文件夹)
        total_images = sum(len(info["image_ids"])
                           for info in month_image_map.values())
        downloaded_count = 0
        failed_images = []
        if total_images > 0:
            logger.info(f"需要下载 {total_images} 张图片(按需下载)")

            # 为每个月份的图片创建下载任务
            all_download_tasks = []
            for year_month, info in month_image_map.items():
                pictures_folder = info["folder"]
                for image_id in info["image_ids"]:
                    all_download_tasks.append({
                        "image_id": image_id,
                        "user_id": author_user_id,
                        "folder": pictures_folder,
                        "month": year_month
                    })

            # 下载图片(控制并发)
            downloaded_count = 0
            failed_images = []

            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, 3)) as executor:
                futures = {}
                for task in all_download_tasks:
                    future = executor.submit(
                        self.download_image,
                        task["image_id"],
                        task["user_id"],
                        task["folder"]
                    )
                    futures[future] = task

                for future in tqdm(as_completed(futures), total=len(futures), desc="下载图片"):
                    task = futures[future]
                    try:
                        if future.result():
                            downloaded_count += 1
                        else:
                            failed_images.append(
                                f"图片{task['image_id']} (月份: {task['month']})")
                    except Exception as e:
                        failed_images.append(
                            f"图片{task['image_id']} (月份: {task['month']}) - {e}")

            logger.info(f"图片下载完成: {downloaded_count}/{total_images}")

            # 输出下载失败的图片
            if failed_images:
                logger.warn(f"以下 {len(failed_images)} 张图片下载失败:")
                for failed in failed_images:
                    logger.warn(f"  - {failed}")
        else:
            logger.info("没有需要下载的图片")

        # 保存统计信息
        stats = {
            "total_diaries": len(full_diaries),
            "total_images": total_images,
            "downloaded_images": downloaded_count,
            "failed_images": len(failed_images) if total_images > 0 else 0,
            "months": list(month_image_map.keys()),
            "export_time": datetime.datetime.now().isoformat(),
            "user_id": self.user_id,
            "partner": partner
        }

        stats_file = os.path.join(base_folder, "export_stats.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        return True

    def generate_html(self, base_folder):
        """生成HTML文件"""
        html_folder = os.path.join(base_folder, "html")
        if not os.path.exists(html_folder):
            logger.error(f"HTML文件夹不存在: {html_folder}")
            return False

        try:
            # 调用trans.py脚本(处理 Windows 编码问题)
            result = subprocess.run(
                [sys.executable, "trans.py", base_folder],
                capture_output=True,
                text=True,
                encoding='gbk',  # Windows 系统使用 gbk 编码
                errors='ignore',  # 忽略编码错误
                cwd=os.getcwd()
            )

            if result.returncode == 0:
                logger.info("HTML文件生成成功!")

                # 检查输出目录
                output_dir = os.path.join(base_folder, "html")
                if os.path.exists(output_dir):
                    # 列出生成的HTML文件
                    for file in os.listdir(output_dir):
                        if file.endswith('.html'):
                            logger.info(f"  - {file}")
                return True
            else:
                logger.error("HTML文件生成失败")
                if result.stderr:
                    logger.error(f"错误: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"运行trans.py时出错: {e}")
            return False


def main():
    """主函数"""

    today = datetime.date.today()
    three_days_ago = today - datetime.timedelta(days=3)
    # 输入邮箱和密码
    email = EMAIL
    password = PASSWORD
    # 创建下载器
    downloader = DiaryDownloader(email, password)
    # 登录
    if not downloader.login():
        return
    choice = '1'
    # 选择导出目标
    partner = (choice == "2")
    # 获取日记列表
    sync_data = downloader.get_sync_data(partner)
    if not sync_data:
        logger.error("无法获取日记列表")
        return

    diaries = sync_data["diaries"]
    if not diaries:
        logger.info("没有日记可导出")
        return

    # 显示日期范围
    dates = [d.get("createddate", "") for d in diaries if d.get("createddate")]
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        logger.info(f"日记日期范围: {min_date} 到 {max_date}")

    # 询问日期范围
    logger.info("\n请设置导出日期范围:")
    logger.info(f"最早日期: {min_date}")

    # 获取起始年份和月份
    start_date = three_days_ago
    end_date = today
    logger.info(f"日期范围: {start_date} 到 {end_date}")

    # 筛选日记
    if start_date or end_date:
        filtered_diaries = []
        for diary in diaries:
            date_str = diary.get("createddate", "")
            if date_str:
                try:
                    diary_date = datetime.datetime.strptime(
                        date_str, "%Y-%m-%d").date()
                    if start_date and diary_date < start_date:
                        continue
                    if end_date and diary_date > end_date:
                        continue
                    filtered_diaries.append(diary)
                except:
                    pass
        diaries = filtered_diaries

    logger.info(f"将导出 {len(diaries)} 篇日记")

    if not diaries:
        logger.info("指定日期范围内没有日记")
        return

    # 更新同步数据中的日记列表
    sync_data["diaries"] = diaries

    # 下载日记
    success = downloader.download_diaries(sync_data, partner)

    if success:
        logger.info("日记导出完成!")

        # 询问是否生成HTML
        html_choice = 'y'
        if html_choice in ["", "y", "yes"]:
            base_folder = "partner" if partner else "myself"
            downloader.generate_html(base_folder)

        logger.info("\n导出完成!")
        base_folder = "partner" if partner else "myself"

    else:
        logger.error("导出失败")


if __name__ == "__main__":
    try:
        main()
        # logger.info("\n" + "=" * 60)
        logger.info("程序执行完毕")
        # logger.info("=" * 60)
    except KeyboardInterrupt:
        logger.info("\n\n用户中断操作")
    except Exception as e:
        logger.error(f"\n\n程序运行出错: {e}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(error_details)
