# 未来功能规划清单 (Future Roadmap)

> 本文档记录已设计但尚未实现的功能预案，待对应业务模块启动时一并落地。
> 最后更新：2026-04-12

---

## 1. 用户钱包与资金体系 (`user_wallets` 领域)

### 1.1 `user_wallets` (用户钱包表)
高并发资金钱包，独立于等级体系，采用乐观锁防超卖。
- `id`: UUIDv7, PK
- `user_id`: UUID, UNIQUE
- `balance`: DECIMAL(15,2) 默认 0（当前可用现金余额）
- `frozen_balance`: DECIMAL(15,2) 默认 0（提现审核中冻结的金额）
- `points`: INT 默认 0（当前可用积分）
- `version`: INT 默认 0（乐观锁版本号，每次扣款 +1）

### 1.2 `user_balance_logs` (资金流水铁账本)
每一笔钱的进出都必须留下不可篡改的快照记录。
- `id`: UUIDv7, PK
- `user_id`: UUID
- `change_type`: VARCHAR（StrEnum 枚举常量）
- `amount`: DECIMAL(15,2)（正数=入账，负数=扣减）
- `before_balance`: DECIMAL(15,2)（变动前余额快照）
- `after_balance`: DECIMAL(15,2)（变动后余额快照）
- `ref_id`: UUID | None（关联的订单/提现单 ID）
- `remark`: VARCHAR

**`change_type` 枚举常量定义：**
```python
class BalanceChangeType(StrEnum):
    """资金变动类型 —— 每个值对应一段确定的业务代码路径"""
    # ---- 入账类 (+) ----
    ORDER_REFUND = "order_refund"           # 订单退款返还
    COMMISSION_FIRST = "commission_first"    # 直推佣金到账
    COMMISSION_SECOND = "commission_second"  # 间推佣金到账
    COMMISSION_THIRD = "commission_third"    # 三级佣金到账
    UPGRADE_REWARD = "upgrade_reward"        # 下级升级奖励到账
    ADMIN_RECHARGE = "admin_recharge"        # 后台手工充值（客诉补偿等）

    # ---- 扣减类 (-) ----
    ORDER_PAY = "order_pay"                 # 余额支付扣款
    WITHDRAW_APPLY = "withdraw_apply"       # 提现申请冻结
    WITHDRAW_SUCCESS = "withdraw_success"   # 提现成功扣减冻结
    WITHDRAW_REJECT = "withdraw_reject"     # 提现驳回解冻
    ADMIN_DEDUCT = "admin_deduct"           # 后台手工扣款
```

### 1.3 `user_point_logs` (积分流水表)
积分独立于资金，拥有独立的过期策略与兑换规则。
- `id`: UUIDv7, PK
- `user_id`: UUID
- `change_type`: VARCHAR（StrEnum 枚举常量）
- `points`: INT（正=获取，负=消耗）
- `before_points`: INT（变动前积分快照）
- `after_points`: INT（变动后积分快照）
- `ref_id`: UUID | None
- `remark`: VARCHAR

**`change_type` 枚举常量定义：**
```python
class PointChangeType(StrEnum):
    """积分变动类型"""
    # ---- 获取类 (+) ----
    ORDER_COMPLETE = "order_complete"        # 订单完成赠送积分
    SIGN_IN = "sign_in"                      # 每日签到
    INVITE_REGISTER = "invite_register"      # 邀请新用户注册奖励
    ADMIN_GRANT = "admin_grant"              # 后台手工发放

    # ---- 消耗类 (-) ----
    ORDER_DEDUCT = "order_deduct"            # 积分抵扣订单金额
    EXCHANGE_GOODS = "exchange_goods"         # 积分兑换商品
    ORDER_REFUND_REVOKE = "order_refund_revoke"  # 退款撤回已赠积分
    POINTS_EXPIRE = "points_expire"          # 积分过期清零
    ADMIN_REVOKE = "admin_revoke"            # 后台手工扣除
```

---

## 2. 商品级独立分佣 (Product-Level Commission Override)

当 `OrderService` 计算佣金时，第一优先级检测该商品是否配置了独立佣金。
如果该商品存在独立佣金配置，立即中止读取 `user_levels.commission_rules`，使用商品自身的分佣规则。

---

## 3. C端业务侧待实现清单

- [ ] **多端跨域桥接**：苹果 ID / 微信免密等多平台聚合登录体系
- [ ] **活体与二次验证风控**：OTP 短信、设备信誉机制等二次验签
- [ ] **单元自动化覆盖**：PyTest 防暴撞击与 Token 窃取的全套用例安全防线
- [ ] **B端 Token 越权测试**：集成测试验证 C端 Token 无法访问 `/admin/` 接口

---

## 4. 架构设计原则备忘

- **`user_level_profiles.total_consume/total_points`** 是历史累加器指标，只为升降级引擎提供判定燃料
- **`user_wallets.balance/points`** 是实时余额，面临高并发扣减，必须用行级锁或乐观锁保护
- 两者绝不能合并到同一张表，否则退款/发佣/扣款时会产生巨大的锁冲突
- 资金流水与积分流水必须分成两张独立表，积分有过期策略/兑换规则等不同生命周期
