# nideriji-download
你的日记官网：https://nideriji.cn/

你的日记官方导出工具：https://nijiweb.cn/pc/


---
# 预览
<img width="808" height="613" alt="Snipaste_2025-08-29_20-55-02" src="https://github.com/user-attachments/assets/7e69a890-25b1-4f47-93d3-77cd4cf28052" />

# 更新日志：
- 2024年7月：最初版本，可以导出为markdown。
- 2025年8月：新增导出为html。
- 2025年10月：一些小的优化，优化了不同用户的工作目录。


# 主要功能
导出**你的日记APP**自己及匹配搭档的日记为markdown格式。

# 使用说明
```
pip install requests tqdm pycryptodome
python3 main.py
```


# 运行截图
<img width="767" height="462" alt="Snipaste_2025-08-24_20-27-11" src="https://github.com/user-attachments/assets/bc7e4389-7f9d-41cf-b337-a5e71ee8dff8" />


## 其他说明
- 日记把日期作为markdown文件名及标题，采用obsidian高亮格式：==高亮内容==，其他md阅读器可能无法识别，有需要可自行修改。
- 因导出图片速度较慢，导出所有日记时会导出图片，反之不会重新导出图片。
- html文件可以选择按日期正序和倒序，请修改trans.py中REVERSE_ORDER = True项。
- 代码结合AI辅助完成，仅保证代码可用，具体细节未能详细探究，如有疏漏之处欢迎建议。


