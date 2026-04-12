# 双轨认证与 Token 安全体系 — 业务规则标准文档

> **文档版本**: v1.0  
> **最后更新**: 2026-04-12  
> **适用范围**: FastAPI-Mini-Standard 项目  
> **阅读对象**: 架构师、前后端开发、安全审计人员

---

## 目录

1. [体系全景概述](#1-体系全景概述)
2. [B 端与 C 端隔离机制 (物理与逻辑双隔离)](#2-b-端与-c-端隔离机制)
3. [双 Token 架构设计](#3-双-token-架构设计)
4. [核心流程：登录与签发](#4-核心流程登录与签发)
5. [Token 刷新与无感续期策略 (Rotation)](#5-token-刷新与无感续期策略)
6. [防重放与 Token 盗用检测 (安全联防与诛九族机制)](#6-防重放与-token-盗用检测)
7. [防暴破与审计机制](#7-防暴破与审计机制)
8. [API 设计基准](#8-api-设计基准)

---

## 1. 体系全景概述

本系统放弃了传统的 Session 状态存留与单一长效 JWT 方案，采用目前业界最高的安全基线要求，构建了一套**双轨（B端/C端物理隔离）、双牌（Access+Refresh）、防盗防重放**的现代化鉴权系统。

其核心理念是：
- **无状态与有状态结合**：前端高频 API 请求使用无状态的 JWT (Access Token) 保障性能；长线会话维持依靠存储在 Redis 中的 Refresh Token (高熵随机字符串) 进行。
- **一旦被盗，全家连坐**：任何对历史 Refresh Token 的二次使用（即使是网络重放）将立刻被安全模块捕获为“盗用事件”，并瞬间熔断该会话的所有关联令牌。
- **强制留痕**：每一次登录尝试（无论成功或失败、甚至被拦截）必须落库审计（`LoginLog`）。

---

## 2. B 端与 C 端隔离机制

由于系统同时承载面向消费者的 C 端接口与面向内部运营的 B 端接口，如果 B/C 端的 Token 通用，一旦存在接口越权，将导致毁灭性打击。

**安全机制：JWT `aud` (Audience) 门卫验证**
我们不在业务代码中判断身份，而是直接在 JWT 的声明阶段进行硬编码物理隔离。

| 客户端类型 | API 路由前缀 | JWT `aud` 载荷特征 | 数据库依赖表 |
|-----------|------------|------------------|-------------|
| **C端 (买家)** | `/api/v1/users/...` | **无** (不包含 `backend` 标识) | `users` |
| **B端 (后台)** | `/api/v1/admin/...` | 必须精确包含 `aud=backend` | `sys_admins` |

**拦截层：** (`app/api/deps.py`)
- C 端鉴权器 (`get_current_user`) 检测到 `aud="backend"` 时，直接抛出 `B端凭证禁止访问C端接口`。
- B 端鉴权器 (`get_current_admin`) 检测不到 `aud="backend"` 时，直接抛出 `仅Backend凭证可访问管理接口`。
- 分毫不差的逻辑隔离使得两套系统互不相涉。

---

## 3. 双 Token 架构设计

| Token 类型 | 形态 | 承载媒介 | 寿命 | 特性 | 传输方式 |
|------------|-----|----------|------|------|----------|
| **Access Token** | JWT 签名串 | 客户端内存 | **短效** (通常 2 小时) | 无状态，不查库，解析出 ID 即可操作。 | `Authorization: Bearer <Access Token>` |
| **Refresh Token** | 48位安全随机字符串 (UrlSafe) | Redis 会话族谱树 | **长效** (通常 7~30 天) | 有状态，绑定 `SessionID`，单次有效(用后即焚)。 | 请求 Body 提交，用于换取全新双 Token。 |

> **为什么 Refresh Token 不用 JWT？**
> 因为 Refresh Token 需要支持**立刻撤销**（踢人下线）、**用后即焚**（检测盗用）。使用传统 JWT 无法满足精准的黑名单管理和长周期的族谱演变。我们将其作为 Redis 里的一个指针，后端拥有 100% 的生杀大权。

---

## 4. 核心流程：登录与签发

### C 端登录特征：
- 需要强制进行行为验证码（Captcha）验签以防止撞库。
- 采用 Argon2id 异步哈希验算密码。
- 会为当前设备生成一个唯一的 UUID 作为 `SessionID` (族谱树的根)。

### Redis 存储模型 (会话族谱)：
生成的双 Token 不仅返回给前端，同时后端的 Redis 会写入以下数据，形成树状绑定：

**[B 端管理员登录示例]**
1. `admin_refresh_token:{refresh_token_string}`  ===>  绑定至此会话的 `SessionID`
2. `admin_session:{session_id}` ===> 绑定至真实的管理员 ID (`admin_id`)

这意味着：**每一台独立的设备登录，都会在后台生成一棵独立的会话树。**

---

## 5. Token 刷新与无感续期策略

当 Access Token 返回 401（或前端预判即将过期）时，前端通过提交 Refresh Token 到 `/auth/refresh` 接口完成无感续期。

该操作的核心是**旧换新 (Rotation)**，一次只能用一次。这就涉及到了极端的并发条件竞争问题，我们的解决方式是 **Redis 原子 `RENAME` 指令**。

**Token Rotation 原理机制说明：**
```
前端提交: 旧 RefreshToken [R_old]

1. [原子锁定竞争]
后端尝试在 Redis 中执行:
>> RENAME refresh_token:R_old 转移为 consumed_token:R_old

成功表示获得了这把旧钥匙的独占权，这是唯一的合法刷新请求。失败说明已经被别人换过了。

2. [签发落库]
解析出 SessionID。生成全新的 [Access_new] 和 [R_new]。

3. [延续根系]
把新的 refresh_token:R_new 指向原来的 SessionID。
把 consumed_token:R_old 删除（或设置短TTL用于钓鱼检测）。
```

---

## 6. 防重放与 Token 盗用检测

**(核心亮点：诛连机制)**

基于上面第 5 节，如果因为黑客盗取了 Token，或者用户老设备网络延迟卡顿连续发送了两次刷新请求。
第二个抵达的请求，它的 `RENAME` 会失败（也就是抛出 `ResponseError`）。

此时系统不会简单地返回“Token 过期”，而是进入**盗用检测 (Theft Detection) 流程**：
1. 请求 `RENAME` 失败，进入捕获。
2. 此时我去 Redis 里找找有没有 `consumed_token:R_old`。
3. 如果 **有！** —— 这意味着有人拿着一张“刚刚被合法消费掉的废机票”企图闯关。这是典型的 Token 泄露被第三方恶意利用、或重放攻击。
4. **【安防拉升：诛十族机制】**
   既然凭证已经面临被盗用的重度风险，由于无法证明上一次刷新的是用户本人还是黑客，系统执行**无差别熔断**。
   - 提取背后的 `SessionID`
   - 将当前 Session 树下所有依然合法的 Token、SessionID 全部从 Redis 删除！（对应业务代码 `_destroy_session_family`）
   - **结果：** 黑客和本人的该设备双双被强制踢出，同时前端抛出最高安全级别异常 `TOKEN_THEFT_DETECTED`，强制要求用户重新输入密码登录。

---

## 7. 防暴破与审计机制

系统实现了 `LoginLog` 审计级追踪。
在 `service.py` 内部，使用了 `finally + 独立提交/异常隔离` 机制来保障这本“铁账簿”：

- 不管遇到异常情况（验证码错误、密码错误）、还是被封禁状态、甚至代码崩溃报错。
- `user_agent`、`ip_address`、`status`、`reason` **必将写入数据库 `sys_login_logs` / C端暂不表**。
- 这为后期的 SIEM (安全信息和事件管理系统) 提供了关键判定数据源，运营可以随时在 B 端通过日志大屏审视暴破行为。

---

## 8. API 设计基准

### Headers 规范
所有需要鉴权的接口，必须在头部携带标准的 Bearer 格式：
`Authorization: Bearer eyJhbGciOi... (你的 Access Token)`

### 401 Unauthorized 触发场景
业务系统在以下任何环节均直接向前端返回全局 401 报错：
1. JWT 不存在格式不对、签名非法。
2. JWT 中自带的时间戳判定已过期。
3. `aud` 声名未能校验成功（防越权）。
4. 解析出 user_id/admin_id 后再去数据库比对，发现此账号**已被逻辑删除（`is_deleted=True`）或被停用封禁（`is_active=False`）**。

> **架构注记：** 由于 Access Token 默认具有几小时存活期，我们在 JWT 层无法做到秒级踢除。但每次业务请求时 `deps.py` 会做 `session.get(User, id)` 的 DB 查询验证 `is_active`。这是在“绝对无状态 JWT”和“业务及时止损”之间的最佳安全折中。
