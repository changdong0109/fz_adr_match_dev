"""
CollapsibleSection - header + content collapsible widget

Provides a clear, clickable header with an arrow indicator and a content
area that can be shown/hidden. The whole section is wrapped in a
`QFrame` to give a visible module boundary.

Usage:
    section = CollapsibleSection("Title", expanded=True)
    section.add_content_widget(widget)
    layout.addWidget(section)

This implementation avoids platform-dependent tree indicators and
provides a predictable, interactive UI.
"""

try:
    from qgis.PyQt.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QLabel, QFrame, QSizePolicy
    )
    from qgis.PyQt.QtCore import Qt
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False


class CollapsibleSection(QWidget):
    """A simple collapsible section with a header and content area."""

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)

        # Outer frame to provide visual boundary between modules
        self._frame = QFrame(self)
        # Some QGIS/PyQt bindings don't expose QFrame.StyledPanel/Plain constants.
        # Use common alternatives that exist across bindings to ensure compatibility.
        # Some PyQt/PySide bindings used by different QGIS builds may not
        # expose QFrame enum attributes like StyledPanel/Box/Plain/Raised.
        # Check availability before calling to avoid AttributeError in the
        # target environment. If none are available, skip setting shape/shadow.
        if hasattr(QFrame, 'StyledPanel'):
            try:
                self._frame.setFrameShape(QFrame.StyledPanel)
            except Exception:
                pass
        elif hasattr(QFrame, 'Box'):
            try:
                self._frame.setFrameShape(QFrame.Box)
            except Exception:
                pass

        if hasattr(QFrame, 'Plain'):
            try:
                self._frame.setFrameShadow(QFrame.Plain)
            except Exception:
                pass
        elif hasattr(QFrame, 'Raised'):
            try:
                self._frame.setFrameShadow(QFrame.Raised)
            except Exception:
                pass
        self._frame.setObjectName('collapsible_section_frame')

        # Main layout for this widget
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._frame)

        # Layout inside the frame
        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setContentsMargins(6, 6, 6, 6)
        frame_layout.setSpacing(6)

        # Header: arrow button + title label
        header = QWidget(self._frame)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._toggle_btn = QToolButton(header)
        # Some Qt bindings used by QGIS may not expose ToolButtonIconOnly.
        # Guard the call to avoid AttributeError; if unavailable, skip it.
        try:
            if hasattr(Qt, 'ToolButtonIconOnly'):
                self._toggle_btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
        except Exception:
            pass
        # Arrow indicator: some Qt bindings may not expose DownArrow/RightArrow.
        # Fallback to text arrows if arrow constants are missing.
        if hasattr(Qt, 'DownArrow') and hasattr(Qt, 'RightArrow'):
            try:
                self._toggle_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
            except Exception:
                # fallback to text arrows
                self._toggle_btn.setText('▾' if expanded else '▸')
        else:
            self._toggle_btn.setText('▾' if expanded else '▸')

        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(expanded)
        self._toggle_btn.setAutoRaise(True)
        # 安全获取 PointingHandCursor（兼容不同PyQt版本）
        try:
            if hasattr(Qt, 'CursorShape') and hasattr(Qt.CursorShape, 'PointingHandCursor'):
                cursor = Qt.CursorShape.PointingHandCursor
            elif hasattr(Qt, 'PointingHandCursor'):
                cursor = Qt.PointingHandCursor
            else:
                # 使用数值常量：PointingHandCursor = 13
                cursor = 13
            self._toggle_btn.setCursor(cursor)
        except (AttributeError, TypeError):
            # 如果都失败，使用数值常量
            try:
                self._toggle_btn.setCursor(13)
            except Exception:
                pass

        self._title_label = QLabel(title, header)
        self._title_label.setObjectName('collapsible_section_title')
        # 安全获取 QSizePolicy 常量（兼容不同PyQt版本）
        try:
            if hasattr(QSizePolicy, 'Policy') and hasattr(QSizePolicy.Policy, 'Expanding'):
                expanding = QSizePolicy.Policy.Expanding
                preferred = QSizePolicy.Policy.Preferred
            elif hasattr(QSizePolicy, 'Expanding'):
                expanding = QSizePolicy.Expanding
                preferred = QSizePolicy.Preferred
            else:
                # 使用数值常量：Expanding = 7, Preferred = 1
                expanding = 7
                preferred = 1
            self._title_label.setSizePolicy(expanding, preferred)
        except (AttributeError, TypeError):
            # 如果都失败，使用数值常量
            try:
                self._title_label.setSizePolicy(7, 1)  # Expanding, Preferred
            except Exception:
                pass

        header_layout.addWidget(self._toggle_btn)
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        frame_layout.addWidget(header)

        # Content container
        self._content = QWidget(self._frame)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(6)

        frame_layout.addWidget(self._content)

        # Connect toggle
        self._toggle_btn.toggled.connect(self._on_toggled)

        # Set initial state
        self._content.setVisible(expanded)

        # Basic style - keeps a subtle separation
        self._apply_default_style()

    def _apply_default_style(self):
        # Keep styling minimal so it blends with QGIS native look,
        # but ensure there is a visible boundary for each section.
        style = """
        QFrame#collapsible_section_frame { 
            border: 1px solid #d0d0d0; 
            border-radius: 4px; 
            background: #ffffff; 
        }
        QLabel#collapsible_section_title { 
            font-weight: 600;
            color: #000000;
            font-size: 14px;
        }
        QToolButton {
            border: none;
            background: transparent;
        }
        QToolButton:hover {
            background-color: #f0f0f0;
            border-radius: 3px;
        }
        """
        try:
            self.setStyleSheet(style)
        except Exception:
            pass

    def add_widget(self, widget: QWidget):
        """Add a widget to the content area."""
        # remove parent so layout takes ownership
        widget.setParent(self._content)
        self._content_layout.addWidget(widget)

    def add_content_widget(self, widget: QWidget):
        """Alias for add_widget (keeps previous API)."""
        self.add_widget(widget)

    def _on_toggled(self, checked: bool):
        # update arrow and content visibility
        # Update arrow type if available, otherwise update button text.
        try:
            if hasattr(Qt, 'DownArrow') and hasattr(Qt, 'RightArrow'):
                try:
                    self._toggle_btn.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
                except Exception:
                    # If setArrowType fails, fall back to text
                    self._toggle_btn.setText('▾' if checked else '▸')
            else:
                self._toggle_btn.setText('▾' if checked else '▸')
        except Exception:
            pass
        finally:
            self._content.setVisible(checked)

    def set_expanded(self, expanded: bool):
        self._toggle_btn.setChecked(expanded)
        self._content.setVisible(expanded)

    def is_expanded(self) -> bool:
        return self._toggle_btn.isChecked()

    def set_title(self, title: str):
        self._title_label.setText(title)

    def get_title(self) -> str:
        return self._title_label.text()
