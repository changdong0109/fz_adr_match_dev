# fz_adr_match

QGIS 插件雏形，用于对地址标准化、管网匹配等工具链进行整合。当前仓库仅包含最小化插件骨架，便于后续迭代功能。

## 目录结构

```
fz_adr_match/
├── __init__.py          # 插件入口（QGIS 会 import 并调用 classFactory）
├── fz_adr_match.py      # 插件主体类，负责 UI 与业务逻辑
├── metadata.txt         # QGIS 插件必需的元数据
├── resources.qrc        # Qt 资源文件（指向图标）
├── resources_rc.py      # 由 pyrcc 生成（占位）
├── README.md            # 当前说明
└── icons/
    └── fz_adr_match.svg # 插件图标
```

## 本地调试

1. **设置 QGIS Python 环境**
   - QGIS 安装路径：`C:\soft\QGISQT6 3.44.3`
   - 运行 `C:\soft\QGISQT6 3.44.3\bin\python-qgis.bat` 可进入 PyQGIS 控制台。

2. **软链接 / 拷贝插件**
   - QGIS 用户插件目录通常在 `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - 将 `C:\soft\pythonProject\fz_adr_match` 拷贝或链接到上面目录，启动 QGIS 后在插件管理器里启用即可。

3. **命令行调试**
   - 使用 `qgis_process` 或 `qgis-bin.exe --code your_script.py` 运行 PyQGIS 脚本。
   - 也可以在 IDE 中配置 Python 解释器指向 `python-qgis.bat`，并把 `C:\soft\QGISQT6 3.44.3\apps\qgis\python` 加入 `PYTHONPATH`。

4. **生成资源文件**
   - 如需更新图标资源，执行：
     ```
     C:\soft\QGISQT6 3.44.3\bin\pyrcc6.exe resources.qrc -o resources_rc.py
     ```

## 下一步

- 在 `fz_adr_match.py` 中实现具体的 UI（工具栏按钮 / 面板）和业务逻辑。
- 将 `addr_std_1.py`、`addr_std_gis_1.py` 等核心功能拆成模块，封装为插件中的服务。
- 添加 Processing Provider，使标准化和匹配功能能通过 QGIS 模型/批处理调用。


