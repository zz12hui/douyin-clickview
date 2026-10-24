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

### 第一期：移动端反检测核心 (v0.3.0) 🔒

完成从桌面 Chrome 到移动端 iPhone Safari 的切换，建立指纹+行为深度伪装基础。

> 核心洞察：抖音是 mobile-first 产品，桌面 Chrome 流量本身就是异常信号。

- [ ] **移动端设备模拟** (`browser/stealth.py` 重写)
  - 7 款 iPhone 设备池（15 Pro Max → 13），按市场分布加权
  - Safari UA + TouchEvent（CDP Input.dispatchTouchEvent，isTrusted=true）
  - 移动 viewport (390×844~430×932) + deviceScaleFactor 3.0
  - 确定性种子策略：同一次重试返回相同指纹
- [ ] **多维指纹注入** (`browser/fingerprint.py` 新增)
  - Canvas: 特殊 Unicode 字符渲染 (龘ฑภ경) + 阴影/模糊 + 亚像素噪声
  - WebGL: Apple GPU 字符串池 (A15-A17/M1-M2)
  - AudioContext: sampleRate 44100 + baseLatency 微调
  - Navigator: plugins/hardwareConcurrency/deviceMemory/languages 全覆盖
  - 10-20 套从真实设备采集的指纹组合画像
- [ ] **行为深度建模** (`browser/actions.py` 改造)
  - 6 种触控手势类型库（fast_flick/normal_swipe/slow_drag/double_tap 等）
  - 贝塞尔曲线触控轨迹 + 自然微颤 ±1-3px
  - LogNormal/Beta/Gamma 分布替代 uniform（抖音用 LSTM 做行为分类）
  - Markov 观看状态机（FEED→WATCH→ENGAGE→FEED...）
  - 6 种人类错误模式注入（误触/滑过头/犹豫/注意力转移/重复观看/点错）
  - 拇指可达区域约束 + 设备特定交互差异
- [ ] **请求层加固**
  - 抖音追踪域名选择性拦截（`monitor*`, `analytics*`, `pangolin/sdk*`）
  - `Accept-Language` / `sec-ch-ua` 请求头一致性验证
  - WebRTC IP 泄露防护
- [ ] **每日时间分布** — 基于 5.87 亿 DAU 真实活跃曲线，休眠期 (01-06) 只发 10% 流量

### 第二期：代理池 + 性能优化 (v0.4.0) 🌐

支持 IP 轮换，大幅降低单 IP 被限流的风险，同时优化内存占用。

- [ ] **代理池系统** (`proxy/` 模块)
  - 加权健康评分模型（存活 30% + 成功率 30% + 延迟 20% + 使用频率 20%）
  - 三振出局 + 自动冷却 48h + 永久黑名单
  - **必须使用 SOCKS5**（TLS 透传，Chromium 自己做 TLS 握手 → 指纹天然真实）
  - **禁止 HTTP 代理**（MITM 会暴露代理库的 TLS 指纹而非 Chrome 指纹）
  - 低成本组合：直连(40%) + HK VPS(30%) + 免费代理(20%) + 住宅代理(10%)
  - IP 地理位置必须与 `Asia/Shanghai` 一致
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
  - 主控进程 → ProxyPool + TaskQueue + StatsAggregator + Monitor
  - Worker 子进程 × N，每 Worker 独立 BrowserManager + ContextPool(5-10)
  - IPC 通信（`multiprocessing.Queue`，分布式时迁移到 Redis）
  - Worker 心跳检测 + 自动重启僵尸 Worker
- [ ] **自适应智能调度**
  - 成功率 >90% 自动扩展并发，<70% 自动缩减
  - 单代理/单设备异常自动降权
  - 验证码率飙升自动降低对应时段并发
- [ ] **数据遥测** (`engine/telemetry.py`)
  - 每访问完整遥测（阶段耗时/行为序列/Markov 状态路径）
  - SQLite 本地存储 + 9 维度聚合分析
  - 自动瓶颈分析 + 优化建议生成
- [ ] **混合方案验证**（进阶方向）
  - 浏览器 Token 工厂 (10-20 实例) + HTTP Worker (aiohttp, 500-1000 并发)
  - 单机即可支撑 100w/天，资源消耗降低 10 倍+
  - 前提：需要逆向抖音播放上报 API 端点和参数格式

---

## 运行测试

```bash
pytest
pytest tests/test_url_parser.py
pytest -k "test_parse_raw_id"
```

## License

MIT

---

## 赞赏与联系

如果这个项目帮到你，欢迎请我喝杯咖啡。有问题也可以直接加微信。

| 微信支付 | 加我微信 |
| :---: | :---: |
| <img src="assets/support/wechat-pay.png" width="220" alt="微信支付"> | <img src="assets/support/wechat-contact.png" width="220" alt="微信二维码"> |

- 发邮件可以发到 zz12hui@outlook.com 或 wws00123@qq.com。
- 加微信请直接扫码，备注一下来意。
