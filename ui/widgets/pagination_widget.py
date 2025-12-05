# -*- coding: utf-8 -*-
"""
分页控件组件
"""
from qgis.PyQt.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QLineEdit
)
from qgis.PyQt.QtGui import QIntValidator
from qgis.PyQt.QtCore import Qt, pyqtSignal
from typing import Optional


class PaginationWidget(QWidget):
    """分页控件"""
    
    page_changed = pyqtSignal(int)  # 页码改变信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_page = 1
        self._total_pages = 1
        self._total_items = 0
        self._page_size = 100
        self._build_ui()
    
    def _build_ui(self):
        """构建UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # 首页按钮
        self.btn_first = QPushButton("首页")
        self.btn_first.setObjectName("pagination_btn_first")
        self.btn_first.clicked.connect(self._on_first_page)
        layout.addWidget(self.btn_first)
        
        # 上一页按钮
        self.btn_prev = QPushButton("上一页")
        self.btn_prev.setObjectName("pagination_btn_prev")
        self.btn_prev.clicked.connect(self._on_prev_page)
        layout.addWidget(self.btn_prev)
        
        # 页码信息
        self.lbl_page_info = QLabel("第 1 页 / 共 1 页")
        self.lbl_page_info.setObjectName("pagination_label")
        layout.addWidget(self.lbl_page_info)
        
        # 跳转输入框
        layout.addWidget(QLabel("跳转到:"))
        self.edit_page = QLineEdit()
        self.edit_page.setObjectName("pagination_edit")
        self.edit_page.setMaximumWidth(60)
        self.edit_page.setValidator(QIntValidator(1, 9999, self))
        self.edit_page.returnPressed.connect(self._on_jump_to_page)
        layout.addWidget(self.edit_page)
        
        # 跳转按钮
        self.btn_jump = QPushButton("跳转")
        self.btn_jump.setObjectName("pagination_btn_jump")
        self.btn_jump.clicked.connect(self._on_jump_to_page)
        layout.addWidget(self.btn_jump)
        
        # 下一页按钮
        self.btn_next = QPushButton("下一页")
        self.btn_next.setObjectName("pagination_btn_next")
        self.btn_next.clicked.connect(self._on_next_page)
        layout.addWidget(self.btn_next)
        
        # 末页按钮
        self.btn_last = QPushButton("末页")
        self.btn_last.setObjectName("pagination_btn_last")
        self.btn_last.clicked.connect(self._on_last_page)
        layout.addWidget(self.btn_last)
        
        # 数据统计信息
        self.lbl_stats = QLabel("共 0 条")
        self.lbl_stats.setObjectName("pagination_stats")
        layout.addWidget(self.lbl_stats)
        
        layout.addStretch()
        
        self._update_ui()
    
    def set_pagination(self, current_page: int, total_pages: int, total_items: int, page_size: int = 100):
        """设置分页信息"""
        self._current_page = current_page
        self._total_pages = total_pages
        self._total_items = total_items
        self._page_size = page_size
        self._update_ui()
    
    def _update_ui(self):
        """更新UI状态"""
        # 更新按钮状态
        self.btn_first.setEnabled(self._current_page > 1)
        self.btn_prev.setEnabled(self._current_page > 1)
        self.btn_next.setEnabled(self._current_page < self._total_pages)
        self.btn_last.setEnabled(self._current_page < self._total_pages)
        
        # 更新页码信息
        if self._total_pages > 0:
            start_item = (self._current_page - 1) * self._page_size + 1
            end_item = min(self._current_page * self._page_size, self._total_items)
            self.lbl_page_info.setText(f"第 {self._current_page} 页 / 共 {self._total_pages} 页")
            self.lbl_stats.setText(f"共 {self._total_items} 条 (显示 {start_item}-{end_item})")
        else:
            self.lbl_page_info.setText("第 0 页 / 共 0 页")
            self.lbl_stats.setText("共 0 条")
        
        # 更新跳转输入框
        self.edit_page.setText(str(self._current_page))
    
    def _on_first_page(self):
        """首页"""
        if self._current_page > 1:
            self._go_to_page(1)
    
    def _on_prev_page(self):
        """上一页"""
        if self._current_page > 1:
            self._go_to_page(self._current_page - 1)
    
    def _on_next_page(self):
        """下一页"""
        if self._current_page < self._total_pages:
            self._go_to_page(self._current_page + 1)
    
    def _on_last_page(self):
        """末页"""
        if self._current_page < self._total_pages:
            self._go_to_page(self._total_pages)
    
    def _on_jump_to_page(self):
        """跳转到指定页"""
        try:
            page = int(self.edit_page.text())
            if 1 <= page <= self._total_pages:
                self._go_to_page(page)
            else:
                # 输入无效，恢复当前页
                self.edit_page.setText(str(self._current_page))
        except ValueError:
            self.edit_page.setText(str(self._current_page))
    
    def _go_to_page(self, page: int):
        """跳转到指定页（内部方法）"""
        if 1 <= page <= self._total_pages and page != self._current_page:
            self._current_page = page
            self._update_ui()
            self.page_changed.emit(page)

