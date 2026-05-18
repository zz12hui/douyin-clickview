# Douyin ClickView

Python CLI 工具，使用 Playwright 模拟移动端浏览器访问抖音视频。支持模拟 iPhone Safari 用户行为（观看、滚动、评论互动等），内置反检测机制。

## 安装

```bash
pip install -e ".[dev]"
playwright install chromium
```

## 使用

```bash
# 查看帮助
douyin-clickview --help

# 基本用法
douyin-clickview --url "https://www.douyin.com/video/xxxxx" --visit-count 5

# 或使用 Python
python -m douyin_clickview --help
```

## 支持的 URL 格式

- 19 位纯数字视频 ID
- `douyin.com/video/` 标准链接
- `v.douyin.com` 短链接（自动跟随 302 重定向）
- `iesdouyin.com/share/` 分享链接
- 混合中文/表情符号文本中的嵌入链接

## 配置

配置文件搜索路径：`./config.yaml` → `~/.douyin-clickview.yaml`。环境变量使用 `DY_` 前缀。

```yaml
# config.example.yaml
visit_count: 10
headless: true
watch_time_min: 15
watch_time_max: 30
```

## 运行测试

```bash
pytest
pytest tests/test_url_parser.py
pytest -k "test_parse_raw_id"
```

## 架构

- `cli.py` — Click 命令行入口
- `config.py` — Pydantic 配置管理
- `url_parser.py` — URL 解析（6 种格式）
- `engine/` — 访问调度和单次访问逻辑（指数退避重试）
- `browser/` — Playwright 生命周期管理 + 反检测补丁 + DOM 操作
- `display/` — Rich 终端进度显示和结果报告

## License

MIT
