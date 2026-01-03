# nideriji-download
你的日记官网：https://nideriji.cn/

你的日记官方导出工具：https://nijiweb.cn/pc/


---
# 主要功能
导出**你的日记APP**自己及匹配搭档的日记为markdown和html。


# 预览
<img width="808" height="613" alt="Snipaste_2025-08-29_20-55-02" src="https://github.com/user-attachments/assets/7e69a890-25b1-4f47-93d3-77cd4cf28052" />

# 更新日志：
- 2024年7月：最初版本，可以导出为markdown。
- 2025年8月：新增导出为html。
- 2025年10月：一些小的优化，优化了不同用户的工作目录。




# 使用说明
```
pip install requests tqdm pycryptodome
python3 main.py
```

# 新增计划任务版本，方便把html保存为浏览器书签自动更新
去掉了原脚本的终端交互，改为输出日志，如果存在大于三天未同步，则增量同步，否则只同步最近三天的脚本（考虑到当天同步时间后还可能修改最近的日记，所以这么做）。  
使用方法：
1. win + r 输入taskschd.msc，打开计划任务程序
2. 新建任务，基本设置按照自己喜好来，注意在action选项中，Program/script要填C:\Windows\System32\wscript.exe，然后在下面的参数中再填vbs的路径（路径要带引号）。


# 运行截图
<img width="767" height="462" alt="Snipaste_2025-08-24_20-27-11" src="https://github.com/user-attachments/assets/bc7e4389-7f9d-41cf-b337-a5e71ee8dff8" />


## 其他说明
- 日记把日期作为markdown文件名及标题，采用obsidian高亮格式：==高亮内容==，其他md阅读器可能无法识别，有需要可自行修改。
- 因导出图片速度较慢，导出所有日记时会导出图片，反之不会重新导出图片。
- html文件可以选择按日期正序和倒序，请修改trans.py中REVERSE_ORDER = True项。
- 代码结合AI辅助完成，仅保证代码可用，具体细节未能详细探究，如有疏漏之处欢迎建议。


