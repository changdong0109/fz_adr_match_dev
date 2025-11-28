import os
import traceback

try:
    from qgis.PyQt.QtCore import QCoreApplication, QTranslator, QSettings
    from qgis.PyQt.QtGui import QIcon
    from qgis.PyQt.QtWidgets import QAction, QMessageBox

    QGIS_AVAILABLE = True
    QGIS_IMPORT_ERROR = None
except ImportError as import_error:
    QGIS_AVAILABLE = False
    QGIS_IMPORT_ERROR = import_error


def load_match_dialog():
    """动态加载匹配对话框（处理导入错误）"""
    try:
        from .ui.match_dialog import MatchDialog
        return MatchDialog
    except Exception as e:
        print(f"Failed to load MatchDialog: {e}")
        return None


class FzAdrMatchPlugin:
    """QGIS 地址标准化匹配插件"""

    def __init__(self, iface):
        """构造函数."""
        if not QGIS_AVAILABLE:
            raise RuntimeError(
                "QGIS Python 环境不可用"
            ) from QGIS_IMPORT_ERROR

        self.iface = iface
        self.actions = []
        self.menu_name = "地址标准化匹配"
        self.plugin_dir = os.path.dirname(__file__)
        self.match_dialog = None

        print(f"fz_adr_match_dev: 插件实例已创建")

    def initGui(self):
        """初始化插件界面"""
        try:
            print("fz_adr_match_dev: 开始初始化 GUI")

            # 创建动作
            icon_path = os.path.join(self.plugin_dir, "icons", "fz_adr_match.svg")
            self.action = QAction(
                QIcon(icon_path) if os.path.exists(icon_path) else QIcon(),
                "地址标准化匹配",
                self.iface.mainWindow(),
            )
            self.action.triggered.connect(self.run)

            # 添加到界面
            self.iface.addToolBarIcon(self.action)
            self.iface.addPluginToMenu(self.menu_name, self.action)
            self.actions.append(self.action)

            print("fz_adr_match_dev: GUI 初始化成功")

        except Exception as e:
            print(f"fz_adr_match_dev: GUI 初始化失败: {e}")
            traceback.print_exc()

    def unload(self):
        """卸载插件"""
        print("fz_adr_match_dev: 开始卸载")
        for action in self.actions:
            self.iface.removePluginMenu(self.menu_name, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []
        print("fz_adr_match_dev: 卸载完成")

    def run(self):
        """运行插件主功能"""
        try:
            # 加载匹配对话框
            MatchDialogClass = load_match_dialog()
            
            if MatchDialogClass is None:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "错误",
                    "无法加载匹配对话框，请检查模块导入"
                )
                return
            
            # 创建并显示对话框
            self.match_dialog = MatchDialogClass(self.iface.mainWindow())
            self.match_dialog.show()
            
        except Exception as e:
            print(f"fz_adr_match_dev: 执行功能时出错: {e}")
            traceback.print_exc()
            QMessageBox.critical(
                self.iface.mainWindow(),
                "错误",
                f"执行失败: {e}"
            )