# pdfscanner

从雅思 PDF 材料中提取话题、重点词汇和例句，生成 Markdown 词汇报告或 M4A 音频。

支持文字版 PDF（直接提取文字）和扫描版/自定义字体 PDF（Apple Vision OCR）。

---

## 安装

需要 Python 3.9+，macOS（OCR 功能依赖 Apple Vision 框架）。

```bash
cd pdfscanner
pip install -e .
```

OCR 模式还需要安装 pyobjc：

```bash
pip install pyobjc-framework-Vision
```

安装后确认命令可用：

```bash
pdfscanner --help
```

> 如果提示 `command not found`，将 Python 脚本目录加入 PATH：
> ```bash
> echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
> source ~/.zshrc
> ```

---

## 使用

### 基本语法

```
pdfscanner scan <PDF文件> [选项]
```

至少需要指定 `--audio` 或 `--markdown` 之一。

### 选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--start-page N` | `1` | 起始页（1-based） |
| `--end-page N` | 最后一页 | 结束页（1-based） |
| `--topics "1,2,广告"` | 全部话题 | 按编号或名称筛选话题，逗号分隔 |
| `--ocr` | 自动检测 | 强制使用 Apple Vision OCR（适用于扫描版 PDF） |
| `--password SECRET` | 无 | PDF 密码 |
| `--audio` | 关闭 | 生成 M4A 音频文件 |
| `--markdown` | 关闭 | 生成 Markdown 词汇报告 |
| `--output DIR` | `./output` | 输出目录 |
| `--voice-en VOICE` | `Samantha` | 英文 TTS 语音（macOS `say` 命令） |
| `--voice-zh VOICE` | `Tingting` | 中文 TTS 语音 |
| `--workers N` | `8` | 并行生成音频的进程数 |

### 示例

**生成 Markdown 报告（文字版 PDF）：**
```bash
pdfscanner scan 雅思口语900句.pdf --markdown --output ./output
```

**扫描版 PDF，指定页码范围，只提取话题 1-4：**
```bash
pdfscanner scan 雅思口语900句1.pdf \
  --start-page 2 --end-page 30 \
  --topics "1,2,3,4" \
  --ocr --markdown \
  --output ./output
```

**同时生成音频和报告：**
```bash
pdfscanner scan 雅思口语900句1.pdf \
  --ocr --audio --markdown \
  --output ./output
```

**按话题名称筛选，指定语音：**
```bash
pdfscanner scan file.pdf \
  --topics "广告,环境,科技" \
  --ocr --audio \
  --voice-en Alex --voice-zh Mei-Jia \
  --output ./output
```

---

## 输出

### Markdown 报告（`--markdown`）

输出文件：`<output>/highlights.md`

每个话题包含：
- **重点词汇表**：从 PDF 高亮区域提取的词汇（表格格式，预留词性/释义/例句列）
- **例句列表**：话题下的英文例句

### 音频文件（`--audio`）

每个话题输出一个 M4A 文件：`<output>/topic_<编号>_<名称>.m4a`

音频内容：话题名 → 英文例句（含停顿）

---

## PDF 类型说明

| 类型 | 特征 | 使用方式 |
|------|------|----------|
| 文字版 PDF | `get_text()` 可提取正常文字 | 默认模式，无需 `--ocr` |
| 扫描版 / 自定义字体 PDF | `get_text()` 返回乱码或空白 | 必须加 `--ocr` |

工具会自动检测是否为文字版 PDF（抽样前3页判断）。如果不确定，直接加 `--ocr` 即可。

---

## 话题检测逻辑

工具通过以下两种策略识别话题边界（两者可叠加）：

1. **颜色矩形**：检测纯黄色背景（r>0.95, g>0.95, b<0.10）区域，提取其中的话题标题
2. **正则匹配**：识别以下格式的标题行：
   - `1. Title`
   - `话题1标题`（支持 OCR 模式）
   - `Chapter 1 Title`

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -q
```

测试覆盖：话题提取、句子过滤、词汇报告生成、音频脚本构建、CLI 参数解析。

---

## 依赖

- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF 解析与渲染
- [pyobjc-framework-Vision](https://pyobjc.readthedocs.io/) — Apple Vision OCR（仅 OCR 模式）
- macOS `say` + `afconvert` — 文字转语音与音频格式转换（仅 `--audio` 模式）
