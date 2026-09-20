# 图片下载器

[English](README.md)

这是一个简单的 Python 工具，可以从网页 HTML 中提取图片地址并将图片下载到本地。工具还会将图片 URL 中的 `caw` 查询参数更新为配置的目标宽度。

## 环境要求

- Python 3.13 或更高版本
- 能够访问目标网页和图片服务器的网络环境

## 安装依赖

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装项目及其依赖：

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

项目依赖包括：

- `requests`：发送 HTTP 请求
- `beautifulsoup4`：解析网页 HTML

## 运行交互式下载器

启动控制台交互程序：

```powershell
python run.py
```

每行输入一个网页地址，也可以一次粘贴包含多个网址的文本。输入空行后开始下载：

```text
Enter one or more webpage URLs.
URL> https://example.com/page-one
URL> https://example.com/page-two
URL>
```

程序会自动提取、清理并去重网址，无效文本会被忽略。下载的图片会保存到 `downloaded_images` 目录。

## 使用源文件中的网址运行

原始脚本仍然支持从 `RAW_TEXT` 中读取固定网址：

```powershell
python do.py
```

运行前请编辑 `do.py` 中的 `RAW_TEXT`。这种方式同样支持多个网址。

## 配置

如有需要，可以修改 `do.py` 顶部附近的配置项：

- `SAVE_DIR`：本地输出目录
- `TARGET_CAW`：通过 `caw` 查询参数传递的目标图片宽度
- `HEADERS`：网页和图片请求使用的请求头

## 故障排查

如果 PowerShell 阻止激活脚本，可以在当前终端会话中运行以下命令，然后重新激活虚拟环境：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

部分网站可能会阻止自动化请求或要求登录。此工具不会绕过这些限制。
