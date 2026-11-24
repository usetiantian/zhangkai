"""Permission Manager — 权限策略评估 (移植自 grok-build permission system)"""

import fnmatch
from enum import Enum
from dataclasses import dataclass, field


class RuleAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"       # 询问用户


class AccessKind:
    """访问类型"""
    def __init__(self, kind: str, target: str = ""):
        self.kind = kind  # bash / file_read / file_write / network
        self.target = target


class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class PermissionRule:
    """一条权限规则"""
    action: RuleAction
    pattern: str  # glob pattern, e.g. "rm*" or "*"
    description: str = ""


@dataclass
class PermissionConfig:
    """权限配置 — 规则列表"""
    rules: list = field(default_factory=list)

    def add_allow(self, pattern: str, desc: str = ""):
        self.rules.append(PermissionRule(RuleAction.ALLOW, pattern, desc))

    def add_deny(self, pattern: str, desc: str = ""):
        self.rules.append(PermissionRule(RuleAction.DENY, pattern, desc))


def evaluate_policy(access: AccessKind, config: PermissionConfig) -> Decision | None:
    """
    评估权限 — Deny 优先, Allow 次之.
    
    移植自 grok-build evaluate_policy:
    - 遍历规则, 用 glob 匹配
    - Deny 规则一旦匹配立即拒绝
    - Allow 规则匹配则允许 (但 Deny 优先)
    - 无匹配 → None (使用默认策略)
    """
    result = None

    for rule in config.rules:
        if fnmatch.fnmatch(access.target, rule.pattern):
            if rule.action == RuleAction.DENY:
                return Decision.DENY
            elif rule.action == RuleAction.ALLOW:
                result = Decision.ALLOW
            elif rule.action == RuleAction.ASK and result != Decision.ALLOW:
                result = Decision.ASK

    return result


# 默认安全配置
DEFAULT_PERMISSIONS = PermissionConfig([
    # 基础安全: 禁止危险命令
    PermissionRule(RuleAction.DENY, "rm *", "禁止删除"),
    PermissionRule(RuleAction.DENY, "del *", "禁止删除"),
    PermissionRule(RuleAction.DENY, "format *", "禁止格式化"),
    PermissionRule(RuleAction.DENY, "shutdown *", "禁止关机"),
    PermissionRule(RuleAction.DENY, "diskpart *", "禁止磁盘操作"),
    # 文件: 只读关键目录, 允许工作区
    PermissionRule(RuleAction.DENY, "C:\\Windows\\*", "系统目录只读"),
    PermissionRule(RuleAction.DENY, "C:\\Program Files\\*", "程序目录只读"),
    PermissionRule(RuleAction.ALLOW, "D:\\qiankun\\*", "允许工作区"),
    PermissionRule(RuleAction.ALLOW, "D:\\node\\*", "允许笔记区"),
    # 网络: 允许出站
    PermissionRule(RuleAction.ALLOW, "*", "默认允许"),
])


class PermissionGate:
    """
    权限门控 — 在工具执行前检查.
    
    移植自 grok-build permission gate.
    """
    def __init__(self, config: PermissionConfig = None):
        self.config = config or DEFAULT_PERMISSIONS
        self.decisions: list = []

    def check(self, access: AccessKind) -> Decision:
        """检查权限 — 返回决策"""
        decision = evaluate_policy(access, self.config)
        result = decision if decision else Decision.ASK  # 默认询问
        self.decisions.append({
            "access": f"{access.kind}:{access.target}",
            "decision": result.value,
        })
        return result

    def is_allowed(self, access: AccessKind) -> bool:
        return self.check(access) == Decision.ALLOW

    def recent_decisions(self, limit: int = 20) -> list[dict]:
        return self.decisions[-limit:]
