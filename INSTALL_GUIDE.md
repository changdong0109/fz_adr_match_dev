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
2. **以管理员身份运行**

### 安装依赖（按顺序执行）

```bash
# 1. 安装 PyTorch (CPU 版本)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 2. 安装兼容版本的核心依赖（版本号很重要！）
pip install numpy==1.26.4
pip install scikit-learn==1.3.2
pip install transformers==4.38.0
pip install huggingface-hub==0.21.0
pip install sentence-transformers==2.7.0
pip install rapidfuzz tqdm

# 3. 安装兼容版本的 pyarrow
pip install pyarrow==14.0.0
```

### ⚠️ 常见问题：用户目录冲突

如果遇到 **DLL load failed** 错误，需要清理用户目录下的冲突包：

```bash
# 关闭 QGIS 后执行
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\torch"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\sentence_transformers"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\transformers"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\pyarrow"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\tokenizers"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\safetensors"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\numpy"
rd /s /q "C:\Users\<用户名>\AppData\Roaming\Python\Python312\site-packages\sklearn"
```

清理后重新执行上面的安装命令。

## 三、语义模型下载

### 方式一：自动下载（需要网络）

首次使用 Step4 匹配功能时，会自动从 HuggingFace 下载模型：
- 模型：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 大小：约 500MB
- 下载位置：`C:\Users\<用户名>\.cache\huggingface\hub\`

### 方式二：使用国内镜像加速

如果下载缓慢，可以设置镜像：

```python
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
print("模型下载完成")
```

### 方式三：离线安装（推荐用于批量部署）

1. 在有网络的电脑上执行：
   ```python
   from sentence_transformers import SentenceTransformer
   model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
   ```

2. 复制模型缓存目录到目标电脑：
   ```
   C:\Users\<用户名>\.cache\huggingface\hub\models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2
   ```
   
   复制到目标电脑的相同位置即可。

## 四、验证安装

在 QGIS Python 控制台中执行：

```python
# 验证依赖
import torch
print(f"PyTorch: {torch.__version__}")

import numpy
print(f"NumPy: {numpy.__version__}")

import sklearn
print(f"scikit-learn: {sklearn.__version__}")

import transformers
print(f"transformers: {transformers.__version__}")

from sentence_transformers import SentenceTransformer
print("sentence-transformers: OK")

from rapidfuzz import fuzz
print("rapidfuzz: OK")

print("\n✅ 所有依赖安装成功！")
```

预期输出：
```
PyTorch: 2.x.x+cpu
NumPy: 1.26.4
scikit-learn: 1.3.2
transformers: 4.38.0
sentence-transformers: OK
rapidfuzz: OK

✅ 所有依赖安装成功！
```

## 五、依赖版本汇总

| 库名 | 推荐版本 | 说明 |
|------|----------|------|
| torch | 2.x (CPU) | 必须使用 CPU 版本 |
| numpy | 1.26.4 | 与 scikit-learn 兼容 |
| scikit-learn | 1.3.2 | 与 numpy 兼容 |
| transformers | 4.38.0 | 与旧模型兼容 |
| huggingface-hub | 0.21.0 | 与 transformers 4.38 兼容 |
| sentence-transformers | 2.7.0 | 稳定版本 |
| pyarrow | 14.0.0 | 与 QGIS 环境兼容 |
| rapidfuzz | 最新 | 模糊匹配 |

## 六、阿里云 API 配置

使用 Step3 标准化解析功能需要配置阿里云 API：

1. 登录 [阿里云控制台](https://www.aliyun.com/)
2. 开通 "地址标准化" 服务
3. 创建 AccessKey
4. 在插件 Step3 界面填入：
   - AccessKeyId
   - AccessKeySecret
   - AppKey

## 七、常见问题

### Q1: DLL load failed while importing lib

**原因**：用户目录下有冲突的包

**解决**：按照 "常见问题：用户目录冲突" 步骤清理

### Q2: numpy.dtype size changed

**原因**：numpy 版本与 scikit-learn 不兼容

**解决**：
```bash
pip install numpy==1.26.4 scikit-learn==1.3.2 --force-reinstall
```

### Q3: 404 Not Found for additional_chat_templates

**原因**：transformers/huggingface-hub 版本太新

**解决**：
```bash
pip install transformers==4.38.0 huggingface-hub==0.21.0
```

### Q4: 模型下载超时

**解决**：使用国内镜像或离线安装方式

### Q5: 插件窗口关闭后任务中断

**说明**：点击关闭按钮只会隐藏窗口，后台任务继续运行。再次点击插件图标可恢复窗口。

---

**技术支持**：如有问题请联系开发团队
