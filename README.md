# Douyin ClickView

Python CLI 工具，使用 Patchright 模拟桌面 Chrome 浏览器访问抖音视频/图文。支持模拟真实用户行为（观看、微交互、评论互动、滑动切换等），内置反检测机制。

## 安装

```bash
pip install -e ".[dev]"
playwright install chromium
```

## 使用

```bash
# 交互式模式（逐步提问参数）
douyin-clickview

# 命令行传入视频链接
douyin-clickview "https://www.douyin.com/video/xxxxx"

# 使用配置文件
douyin-clickview --config config.yaml
```

## 支持的 URL 格式

- 19 位纯数字视频 ID
- `douyin.com/video/` 标准视频链接
- `douyin.com/note/` 图文链接
- `v.douyin.com` 短链接（自动跟随 302 重定向）
- `iesdouyin.com/share/video/` 视频分享链接
- `iesdouyin.com/share/note/` 图文分享链接
- 混合中文/表情符号文本中的嵌入链接

## 配置

配置文件搜索路径：`./config.yaml` → `~/.douyin-clickview.yaml`。环境变量使用 `DY_` 前缀。

```yaml
# config.example.yaml
visit_count: 10
watch_seconds: 3
concurrency: 2
headless: false
browser_channel: "chrome"
comment_interaction: false
profile_interaction: false
```

## 架构

```
cli.py (Click 交互式入口)
  └─ _run() 异步主流程
       ├─ 1. AppConfig 构建 (Pydantic, 4级优先级加载)
       ├─ 2. URLParser.parse() 链接解析（6种格式→视频+图文）
       ├─ 3. show_config() 展示运行配置
       ├─ 4. Scheduler.run() 并发调度（信号量+指数退避重试）
       └─ 5. FinalReport 输出报告 (text/JSON)

config.py ── Pydantic 模型 + CLI > YAML > DY_* ENV > 默认值
url_parser.py ── 6种输入格式 → ParsedVideoUrl

browser/                          engine/
  manager.py (浏览器生命周期)       scheduler.py (并发调度, 重试)
  stealth.py (context 参数)        visitor.py (单次访问编排)
  actions.py (DOM操作, 多级备选)    stats.py (统计模型)

display/
  progress.py (Rich Live 实时进度)
  report.py (text/JSON 报告)
  config_view.py (运行前配置摘要)

errors.py ── 10种异常类型层次
utils/helpers.py ── 抖动, 重试, 日志
```

## 技术栈

- **Patchright** — Playwright 的反检测分支，在 CDP 协议层消除 `navigator.webdriver` 等自动化痕迹
- **Rich** — 终端实时进度表和彩色报告
- **Pydantic** — 类型安全的配置管理
- **httpx** — 短链接 302 跟随（移动端 UA）
- **asyncio** — 全异步 I/O，信号量控制并发

---

## 发展路线图

### 第一期：反检测全面增强 (v0.3.0) 🔒

彻底消除浏览器指纹检测痕迹，让每次访问看起来像不同的真实用户。

- [ ] **浏览器指纹随机化** (`browser/fingerprint.py`)
  - Canvas 指纹注入（`toDataURL`/`getImageData` 添加亚像素噪声）
  - WebGL 指纹欺骗（从真实 GPU 字符串池随机选取 renderer/vendor）
  - AudioContext 指纹处理（-120dB 级别噪声注入）
  - `navigator.plugins` / `hardwareConcurrency` / `deviceMemory` / `languages` 伪造
  - `window.chrome.runtime` 对象注入
  - `screen` 属性与 viewport 一致性对齐
  - 10-20 套从真实设备采集的指纹组合画像
- [ ] **行为画像多样化** (`browser/actions.py` 改造)
  - 3-4 种人类行为画像（快速滑动型 / 仔细阅读型 / 随机互动型 / 视频切换型）
  - 贝塞尔曲线鼠标轨迹 + 加速度模拟
  - Gamma/高斯分布延迟（替代均匀随机，更接近真实人类）
  - 基于内容长度的自适应阅读时间
  - 无关交互注入（随机悬停、空白区域点击、犹豫停顿）
- [ ] **请求层加固** (`browser/stealth.py` 增强)
  - 抖音追踪域名选择性拦截（`monitor*`、`analytics*`、`pangolin/sdk*`）
  - `Accept-Language` / `sec-ch-ua` 请求头一致性验证
  - WebRTC IP 泄露防护
- [ ] **抖音特有检测应对**
  - WebSocket 心跳连接监控与处理
  - 视频 `play()` 事件监听验证播放状态
  - 登录弹窗频率跟踪（弹窗率过高 → 标记 IP 质量）

### 第二期：代理池 + 性能优化 (v0.4.0) 🌐

支持 IP 轮换，大幅降低单 IP 被限流的风险，同时优化内存占用。

- [ ] **代理池系统** (`proxy/` 模块)
  - 加权健康评分模型（存活 30% + 成功率 30% + 延迟 20% + 使用频率 20%）
  - 三振出局 + 自动冷却 + 永久黑名单
  - 支持 HTTP/HTTPS/SOCKS5 + 用户名密码认证
  - IP 地理位置一致性验证（GeoIP 必须与 `Asia/Shanghai` 匹配）
  - 移动 4G/5G 代理 > 住宅 ISP 代理 > 静态住宅代理（数据中心不可用）
- [ ] **Context 代理绑定** (`browser/manager.py` 改造)
  - 多 BrowserContext，每个绑定不同代理 IP
  - ContextPool：预创建 + 按需扩展 + visit_count 超限自动重建
  - 会话级 IP 绑定（不在一次访问中途切换代理）
  - 修复现有 bug：`permissions=[]`、代理双重注入
- [ ] **内存优化**
  - Chromium 启动参数优化（GPU 禁用、扩展禁用、V8 堆限制 512MB）
  - `--blink-settings=imagesEnabled=false` 首访后禁用图片（节省 50% 内存）
  - Context 复用策略（每个 context 执行 50-100 次后重建）
  - Page 关闭后主动 `gc.collect()`
- [ ] **运行保障**
  - MemoryMonitor：每 30s 检查 RSS，超 2GB 自动重启浏览器
  - `atexit` + 信号处理器，防止浏览器进程变孤儿
  - 僵尸 Chromium 进程自动清理

### 第三期：百万级并发扩展 (v0.5.0) 🚀

多进程分布式架构，支撑每日 100 万次视频访问。

- [ ] **多进程架构** (`engine/worker_pool.py`)
  - 主控进程 → ProxyPool + TaskQueue + N × Worker 子进程
  - 每 Worker 独立 BrowserManager + ContextPool(8-12 context)
  - IPC 通信（`multiprocessing.Queue`，分布式时迁移到 Redis）
  - Worker 心跳检测 + 自动重启僵尸 Worker
- [ ] **任务队列** (`engine/task_queue.py`)
  - URL 批量加载（支持权重、去重、循环模式）
  - 进度持久化（崩溃后可从断点继续）
  - 自适应降速：错误率上升 → 自动降低并发
- [ ] **统计聚合与监控** (`engine/monitor.py`)
  - 全 Worker 实时统计聚合
  - 每个代理的成功率 / 延迟 / 错误类型追踪
  - Prometheus 指标暴露（可选）
- [ ] **算力规划**
  - 优化后单次访问 ~12-14s → 每 worker 每天 ~6,000 次
  - 需 ~160 并发 → ~16 个浏览器实例 → ~6GB 内存
  - 推荐配置：16-32GB VPS × 1 台 或 8GB × 3 台

---

## 运行测试

```bash
pytest
pytest tests/test_url_parser.py
pytest -k "test_parse_raw_id"
```

## License

MIT
