# fz_adr_match_dev

QGIS 地址标准化与管网匹配插件 — 轻量化多源数据匹配工具。

## ✨ 核心功能

- **多格式数据加载**: CSV、Excel、SHP、GeoJSON 自动识别与加载
- **智能字段检测**: 自动识别地址字段（省、市、区、街道等）及其类型
- **字段关联推断**: 跨数据源自动识别对应字段关系
- **精准/模糊匹配**: 完全相等匹配 + 基于相似度的容错匹配（可配置阈值）
- **数据清洗**: 去空格、去重、去空行
- **结果导出**: 匹配结果导出为 CSV 格式
- **实时日志**: 控制台日志记录与导出

## 🚀 快速开始

### 安装

1. 将本目录复制到 QGIS 插件目录：
   ```
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\fz_adr_match_dev
   ```

2. 重启 QGIS，在 **Plugins → Manage and Install Plugins** 中启用 `fz_adr_match_dev`

### 使用

1. 在 QGIS 工具栏或 Plugins 菜单中点击 **地址标准化与管网匹配**
2. 按照界面提示加载数据、配置字段、执行匹配
3. 导出匹配结果

## 📚 详细文档

**请查看 [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md) 获取完整文档**，包括：
- 项目概述和需求
- 架构设计
- 代码组织指南
- 实现逻辑
- 开发规范
- 使用指南
- 开发状态和待办事项
- **AI开发指南**（如何使用AI助手开发代码）

## 🤖 AI开发提示词

**快速使用AI助手开发代码？**

- **🚀 快速参考** → [AI_QUICK_REFERENCE.md](AI_QUICK_REFERENCE.md) - 最常用的提示词，一键复制
- **📝 提示词模板** → [AI_PROMPT_TEMPLATE.md](AI_PROMPT_TEMPLATE.md) - 完整提示词模板库
- **💡 使用示例** → [AI_PROMPT_EXAMPLES.md](AI_PROMPT_EXAMPLES.md) - 实际使用示例和技巧

**快速开始**：复制 [AI_QUICK_REFERENCE.md](AI_QUICK_REFERENCE.md) 中的提示词，替换 `[功能名称]` 即可使用！

## 📁 项目结构

```
fz_adr_match_dev/
├── core/          # 核心业务逻辑层
├── ui/            # 用户界面层
├── utils/         # 通用工具层
├── data/          # 数据文件
└── cache/         # 运行时缓存
```

## 📄 许可证

GPL v3 (QGIS 标准)

---

**注意**: 本文档为简要介绍，详细文档请参考 [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)
