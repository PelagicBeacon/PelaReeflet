# PelaReeflet

> 可嵌入的人机验证组件：一次点击 → SHA-256 工作量证明 → 一张一次性通行票。
> 自由修改、自由嵌入，MIT 协议。
> 由 **PelagicBeacon（PELAGIC BEACON）** 维护，[MIT](LICENSE) 协议。

PelaReeflet 是一个**独立部署**的人机验证服务：任何站点用一行 `<script>` 就能接入，
自己的后端再调一次 `siteverify` 换结论。没有数据库、没有外部依赖，
MIT 协议开源，可以随意修改并嵌入到自己的项目里。

## 它是怎么工作的

```
浏览器                         PelaReeflet 服务                业务后端
  │ ① POST /api/v1/challenge ─────▶│                              │
  │◀── challenge + 签名票 ─────────│                              │
  │ ② POST /api/v1/check（点击/轨迹）▶│ 行为关卡，发 gate 票          │
  │ ③ Worker 暴力找 nonce          │                              │
  │   sha256(challenge:nonce) 前缀全 0                              │
  │ ④ POST /api/v1/solve ─────────▶│ 验答案 → 发 ticket            │
  │ ⑤ 把 ticket 随表单提交 ────────────────────────────────────────▶│
  │                                │◀── POST /api/v1/siteverify ───│
  │                                │─── {success: true} ──────────▶│
```

- **无状态优先**：挑战票 / 关卡票 / 通行票都是 HMAC 签名过的 JSON，服务端只记「已用过的票」，重启不炸。
- **一次性**：票用过即作废（`replayed`），防止拿着一张票反复提交。
- **绑 IP**：挑战票与通行票都绑 IP 指纹，换网络要重来。
- **先验答案再记账**：别人拿真票塞假答案也烧不掉你的票。

## 快速开始

```bash
pip install -r requirements.txt

# 1) 生成密钥
python -c "import secrets; print(secrets.token_hex(32))"

# 2) 写进项目根目录的 .env
#    REEFLET_SECRET=<上一步的输出>
cp .env.example .env      # Windows: Copy-Item .env.example .env

# 3) 启动
python app.py
# 打开 http://127.0.0.1:8080/demo
```

程序启动时会**自动读取项目根目录的 `.env`**（自带极简解析，不依赖 python-dotenv）；
真实环境变量优先级更高，生产环境直接注入即可，不用带这个文件。
没配密钥时启动会打印提示，演示页顶部也会出现红色横幅。

没有配置 `REEFLET_SECRET`（或短于 16 位）时，服务会拒绝签发挑战并返回 503 ——
**宁可不可用，也不能用弱密钥签票**。

生成密钥：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## 嵌入到你的站点

```html
<script src="https://reeflet.example.com/embed/pelareeflet.js" async defer></script>

<form method="post" action="/submit">
  <div class="pelareeflet" data-callback="onReefletToken"></div>
  <input type="hidden" name="reeflet" id="reeflet">
  <button>提交</button>
</form>

<script>
  function onReefletToken(ticket) {
    document.getElementById('reeflet').value = ticket;
  }
</script>
```

也可以用 `data-response-field="reeflet"` 让组件自动填隐藏域，连回调都省掉：

```html
<div class="pelareeflet" data-response-field="reeflet"></div>
```

### 主题：深色 / 浅色 / 跟随系统

组件默认深色。三种方式任选，**`data-theme` 优先级最高**：

```html
<!-- 1. 属性指定：light / dark / auto -->
<div class="pelareeflet" data-theme="light"></div>
<div class="pelareeflet" data-theme="auto"></div>

<!-- 2. 同一页面混用也没问题，每个挂载点独立 -->
<div class="pelareeflet" data-theme="dark"></div>
<div class="pelareeflet" data-theme="light"></div>
```

3. 全局默认改 `REEFLET_THEME=light`（服务端配置），`auto` 会跟随
`prefers-color-scheme`，用户切换系统主题时组件实时跟着变。

### 后端验证

```python
import requests

def verify(ticket, user_ip=None):
    r = requests.post("https://reeflet.example.com/api/v1/siteverify", json={
        "secret": REEFLET_SECRET,
        "response": ticket,
        "remoteip": user_ip,        # 可选，传了就校验 IP 绑定
    }, timeout=3)
    return r.json().get("success") is True
```

返回体与 Turnstile 对齐：

```json
{ "success": true, "challenge_ts": 1767225600, "hostname": "example.com" }
{ "success": false, "error-codes": ["replayed"] }
```

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/config` | 组件渲染所需配置（品牌、主题、政策链接），无秘密 |
| POST | `/api/v1/challenge` | 签发挑战，单 IP 每秒限 2 次 |
| POST | `/api/v1/check` | 交互关卡：轨迹 / 按压时长 / 自动化特征 |
| POST | `/api/v1/solve` | 提交 PoW 答案，通过后返回 `ticket` |
| POST | `/api/v1/siteverify` | 业务后端验票 |
| GET | `/embed/pelareeflet.js` | 可嵌入组件脚本 |
| GET | `/demo` | 演示页 |
| GET | `/healthz` | 健康检查 |

### 错误码

| reason | 含义 |
| --- | --- |
| `rate_limited` | 挑战签发太频繁（429） |
| `unavailable` | 服务端没配密钥 |
| `missing` / `invalid` | 没带票 / 票被篡改 |
| `expired` | 票过期 |
| `replayed` | 票已用过（一次性） |
| `bad_ip` | 换 IP 了 |
| `wrong` | PoW 答案不对 |
| `need_gate` | 跳过了点击关卡，直接交答案 |
| `automation` | 自报 `navigator.webdriver` 或合成事件 |
| `interaction` | 轨迹/按压时长不像人 |

## 检测项（除了 PoW 还有什么）

PoW 只是「提高成本」那一层，真正区分人和脚本靠下面两组信号。

### 1. 环境 / 无头浏览器

| 信号 | 判定 |
| --- | --- |
| `navigator.webdriver === true` | **直接拒绝** |
| UA 含 `HeadlessChrome` | **直接拒绝** |
| UA 是 Chrome 但没有 `window.chrome` | 桌面 **+3**；移动壳浏览器 **+1** |
| `plugins=0` 且 `languages=0` | +3 分 |
| `hardwareConcurrency=0` | +2 分 |
| `screen.colorDepth=0` | +2 分 |
| `screen.width<=0` | +2 分 |

累计 ≥ `REEFLET_AUTOMATION_THRESHOLD`（默认 6）即拒绝。**字段缺失按「未知」处理、不计分** ——
老版本组件只上报部分字段时不会被误判。

> **为什么「没有 `window.chrome`」不再一票否决**
>
> 这个属性在页面里是可伪造的：脚本补一句 `window.chrome = {}` 就消失了，
> 所以它对真正的自动化几乎没有拦截价值。反过来误伤很实在 —— 下面这些环境的
> UA 里照样带 `Chrome/131.x`，却普遍不暴露 `window.chrome`：
>
> - 荣耀 / 华为 / 小米 / OPPO 等手机自带浏览器
> - 微信 / QQ / 钉钉内置浏览器
> - Android WebView、Electron、部分企业套壳
>
> 1.0.0 把它们全部判成机器人（点击后稳定 403 `automation`，与轨迹无关），
> 真实用户彻底无法通过。1.1.0 起改为按 UA 计分；确实需要旧行为时设
> `REEFLET_CHROME_MISSING_HARD=1` 显式打开。

### 2. 鼠标轨迹

| 指标 | 权重 |
| --- | --- |
| 位移值只有一两种（线性插值） | +2 |
| `y` 完全不动（完美水平线） | +2 |
| 全程零回退 | +1 |
| 单次点击前扫过 >5000px | +1 |

**故意不用时间间隔（dt）判机器人**：组件把 `mousemove` 节流到 25ms，真人采到的
dt 本来就高度整齐，用它必然误伤（实测一条周期性轨迹的 dt 只有 2 种取值）。

默认这是**评分不是判决**（会写进 `score` 字段便于观察），只有
`REEFLET_TRACK_STRICT=1` 且评分 ≥ `REEFLET_TRACK_THRESHOLD`（默认 4）时才拒绝。

## 配置

全部走环境变量，改完重启即可。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `REEFLET_SECRET` | 空 | **必填**，≥16 位随机串，签名密钥与 siteverify 私钥 |
| `REEFLET_SITEKEY` | `reeflet-demo` | 站点公开标识，多站点部署时可区分 |
| `REEFLET_DIFFICULTY` | `20000` | 期望哈希次数，换算成前导 0 位数（20000 → 4 位） |
| `REEFLET_CHALLENGE_TTL` | `300` | 挑战有效期（秒） |
| `REEFLET_TICKET_TTL` | `300` | 通行票有效期（秒） |
| `REEFLET_CHALLENGE_RATE` | `2` | 单 IP 每秒挑战数 |
| `REEFLET_CLICK_GATE` | `true` | 是否启用「点击 + 行为」关卡 |
| `REEFLET_AUTOMATION_THRESHOLD` | `6` | 自动化特征累加到多少分才拒绝 |
| `REEFLET_CHROME_MISSING_HARD` | `false` | 「UA 像 Chrome 但没有 `window.chrome`」是否一票否决；开了会误伤手机自带浏览器 |
| `REEFLET_TRACK_STRICT` | `false` | 轨迹评分超阈值时是否直接拒绝 |
| `REEFLET_TRACK_THRESHOLD` | `4` | 轨迹评分拒绝阈值（仅 strict 模式生效） |
| `REEFLET_BRAND` | `PELAGIC BEACON` | 组件右侧的品牌水印文字 |
| `REEFLET_LOGO` | `/static/brand/pelareeflet-mark.svg` | Logo 地址 |
| `REEFLET_THEME` | `dark` | `dark` / `light` / `auto`（跟随系统） |
| `REEFLET_LICENSE_URL` | GitHub 上的 LICENSE | 页脚「开源协议」链接 |
| `REEFLET_ABOUT_URL` | GitHub 组织主页 | 页脚「关于我们」链接 |
| `REEFLET_ALLOWED_ORIGINS` | `*` | CORS 白名单，逗号分隔；生产建议填具体域名 |
| `REEFLET_HOSTNAME` | 空 | siteverify 回报的 hostname，空则用请求 Host |

> 「开源协议」默认指向 GitHub 上的 LICENSE，「关于我们」默认指向组织主页；
> 想改成自己的仓库地址，设置 `REEFLET_LICENSE_URL` / `REEFLET_ABOUT_URL` 即可。

## 部署

单进程（状态在内存里，**不要开多 worker**）：

```bash
# Linux 推荐
gunicorn -w 1 -b 0.0.0.0:8080 "app:app"

# Windows
waitress-serve --listen=0.0.0.0:8080 app:app
```

多实例 / 多进程时要先把 `pelareeflet/store.py` 换成 Redis 实现
（接口只有 `mark_challenge_used` / `consume_ticket` / `rate_ok` 三个）。

Nginx 反代要点：

```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Host $host;
}
```

## 安全边界（说清楚，别过度承诺）

**能挡**：直接调接口的脚本、批量注册、无头浏览器、单点暴力提交。

**挡不住**：真的用浏览器 + 人类化轨迹的定向攻击、分布式代理池、人工打码平台。
那一层要靠业务侧的 IP 限流、账号等级、提交频率。PelaReeflet 只负责把
「零成本的自动化」挡在门外，成本抬到一定程度。

## 目录结构

```
PelagicReeflet/
├── app.py                     # 开发入口
├── pelareeflet/
│   ├── __init__.py            # create_app()、演示页、健康检查
│   ├── config.py              # 全部配置（环境变量 → dataclass）
│   ├── core.py                # 挑战 / 关卡 / PoW / 通行票
│   ├── routes.py              # HTTP 接口 + CORS
│   └── store.py               # 进程内状态（可换 Redis）
├── static/
│   ├── brand/pelareeflet-mark.svg
│   └── widget/
│       ├── pelareeflet.js     # 可嵌入组件
│       └── pelareeflet-worker.js
├── templates/demo.html
├── tests/test_flow.py         # 自检（无 pytest 也能跑）
├── docs/许可说明.md            # 许可证与商标说明
├── TRADEMARK.md                # 品牌使用规则
└── LICENSE                     # MIT
```

## 许可

**MIT** —— 随便用、随便改、随便嵌、可以商用、可以闭源分发，只要保留版权声明。

品牌（名称与 Logo）不随 MIT 授权：去掉水印换成自己的品牌完全合法，
但请一并换掉名称与图标，不要冒充官方。规则见 [TRADEMARK.md](TRADEMARK.md)。

**关于署名**：组件默认在右侧显示 `PELAGIC BEACON`，正下方紧跟着「开源协议 · 关于我们」，都在同一个框内。
保留它不需要任何额外代价，却是这个项目被更多人看见的唯一途径——如果它帮到了你，
请留着（`REEFLET_ATTRIBUTION=false` 可以关，但请同时换掉名称与 Logo）。
细节见 [docs/许可说明.md](docs/许可说明.md)。

## 关于

**PelagicBeacon（远洋辉光）** —— 做轻、做稳、能长期自己维护的工具。
