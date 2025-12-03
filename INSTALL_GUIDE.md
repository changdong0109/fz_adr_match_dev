# 地址清洗与多源匹配插件 - 安装指南

## 系统要求

- QGIS 3.40+ (推荐 3.44)
- Python 3.12 (QGIS 自带)
- Windows 10/11

## 一、插件安装

1. 将插件文件夹复制到 QGIS 插件目录：
   ```
   C:\Users\<用户名>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\
   ```

2. 重启 QGIS，在 **插件管理器** 中启用 "地址清洗与多源匹配"

## 二、依赖库安装（重要）

### 打开 OSGeo4W Shell

1. 开始菜单搜索 **OSGeo4W Shell**
2. 以管理员身份运行

### 安装核心依赖

```bash
# 1. 安装 PyTorch (CPU 版本)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 2. 安装 sentence-transformers 和相关依赖
pip install sentence-transformers==2.7.0 rapidfuzz tqdm

# 3. 安装兼容版本的 pyarrow 和 scikit-learn
pip install pyarrow==14.0.0 scikit-learn==1.3.2
```

### 清理用户目录冲突包（如有问题）

如果遇到 DLL 加载错误，需要清理用户目录下的冲突包：

```bash
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\torch"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\sentence_transformers"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\transformers"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\pyarrow"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\tokenizers"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\safetensors"
```

然后重新安装到 QGIS 目录：

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu --target "C:\soft\QGIS\apps\Python312\Lib\site-packages"
pip install sentence-transformers==2.7.0 --target "C:\soft\QGIS\apps\Python312\Lib\site-packages"
pip install pyarrow==14.0.0 --target "C:\soft\QGIS\apps\Python312\Lib\site-packages"
```

> 注意：`C:\soft\QGIS` 替换为实际的 QGIS 安装路径

## 三、语义模型下载

首次使用 Step4 匹配功能时，会自动从 HuggingFace 下载语义模型：
- 模型：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 大小：约 500MB
- 下载位置：`C:\Users\<用户名>\.cache\huggingface\`

### 离线安装模型（可选）

如果网络环境受限，可以提前下载模型：

1. 在有网络的电脑上下载模型文件夹
2. 复制到目标电脑的 `C:\Users\<用户名>\.cache\huggingface\hub\` 目录

或者使用以下 Python 脚本提前下载：

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
print("模型下载完成")
```

## 四、验证安装

在 QGIS Python 控制台中执行：

```python
# 验证依赖
import torch
print(f"PyTorch: {torch.__version__}")

from sentence_transformers import SentenceTransformer
print("sentence-transformers: OK")

from rapidfuzz import fuzz
print("rapidfuzz: OK")

print("\n所有依赖安装成功！")
```

## 五、常见问题

### Q1: DLL load failed while importing lib

**原因**：用户目录下有冲突的包

**解决**：按照 "清理用户目录冲突包" 步骤操作

### Q2: 模型下载失败/超时

**解决方案**：
1. 检查网络连接
2. 使用代理
3. 使用离线安装方式

### Q3: 插件加载失败

**解决方案**：
1. 检查 QGIS 版本（需要 3.40+）
2. 检查依赖是否正确安装
3. 查看 QGIS 日志面板的错误信息

## 六、阿里云 API 配置

使用 Step3 标准化解析功能需要配置阿里云 API：

1. 登录阿里云控制台
2. 开通 "地址标准化" 服务
3. 创建 AccessKey
4. 在插件 Step3 界面填入 AccessKeyId、AccessKeySecret、AppKey

---

**技术支持**：如有问题请联系开发团队

