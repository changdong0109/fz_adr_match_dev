"""
样式管理模块 - 集中管理所有 UI 样式和样式表
Stylesheet manager for the fz_adr_match plugin.

功能：
  1. 加载外部 QSS 文件
  2. 提供样式常量接口
  3. 支持主题扩展（未来可支持 Dark Mode）
"""

import os
from typing import Optional


class StyleManager:
    """样式管理器 - 负责加载和管理所有样式"""

    _styles = {}
    _qss_content = None

    @classmethod
    def _get_styles_dir(cls) -> str:
        """获取样式文件所在目录"""
        return os.path.dirname(__file__)

    @classmethod
    def load_qss(cls) -> str:
        """
        加载主样式表文件 (styles.qss)
        
        Returns:
            str: QSS 样式表内容
        """
        if cls._qss_content is not None:
            return cls._qss_content

        qss_path = os.path.join(cls._get_styles_dir(), 'styles.qss')
        try:
            with open(qss_path, 'r', encoding='utf-8') as f:
                cls._qss_content = f.read()
                return cls._qss_content
        except FileNotFoundError:
            print(f"Warning: QSS file not found at {qss_path}")
            return ""
        except Exception as e:
            print(f"Error loading QSS: {e}")
            return ""

    @classmethod
    def get_collapsible_groupbox_style(cls) -> str:
        """
        获取可折叠分组框的样式表
        用于应用到所有需要折叠的 QGroupBox 小部件
        
        Returns:
            str: 整个 QSS 样式表（包含所有 QGroupBox 相关样式）
        """
        return cls.load_qss()

    @classmethod
    def get_style(cls, name: str) -> str:
        """
        获取命名样式
        
        Args:
            name: 样式名称 (如 'collapsible_groupbox')
        
        Returns:
            str: 对应的样式表内容
        """
        if not cls._styles:
            cls._init_styles()
        return cls._styles.get(name, "")

    @classmethod
    def _init_styles(cls):
        """初始化所有命名样式（可选，用于未来扩展）"""
        qss = cls.load_qss()
        # 这里可以解析 QSS 并分割成多个命名样式
        # 当前直接加载整个文件
        cls._styles['collapsible_groupbox'] = qss
        cls._styles['main'] = qss


# 便捷函数 - 全局接口
def get_collapsible_groupbox_style() -> str:
    """
    获取可折叠分组框样式的便捷函数
    
    使用示例：
        from .styles import get_collapsible_groupbox_style
        groupbox.setStyleSheet(get_collapsible_groupbox_style())
    """
    return StyleManager.get_collapsible_groupbox_style()


def load_stylesheet() -> str:
    """加载完整样式表"""
    return StyleManager.load_qss()
