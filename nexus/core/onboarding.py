"""
Nexus 新用户引导 — 第一次启动时的自我介绍和初始化
"""
import os, json, time

NEXUS_WELCOME = """
╔══════════════════════════════════════════════╗
║                                              ║
║    Nexus v1.0 — 你的个人AI                   ║
║                                              ║
║    我是你的专属AI。我的大脑在你的电脑上，     ║
║    你的数据永远不会离开你的家。              ║
║                                              ║
║    我能做什么：                              ║
║    - 理解你的意图，越用越懂你                ║
║    - 记住我们的对话，不需要你重复            ║
║    - 自己发现不足，后台偷偷学习              ║
║    - 每天扫描新闻，跟上时代                  ║
║    - 保护你的数据，绝不删除                  ║
║                                              ║
║    Constitution 守护你：                     ║
║    A0.1 禁止删除任何文件                    ║
║    A1   先备份再修改                        ║
║    A2   简洁优先                            ║
║    A3   闭环交付                            ║
║                                              ║
║    跟我说"帮我分析股票"开始吧。              ║
║                                              ║
╚══════════════════════════════════════════════╝
"""

class Onboarding:
    """新用户引导——让Nexus自我介绍并初始化。"""

    def __init__(self, data_dir: str):
        self.profile_path = os.path.join(data_dir, "user_profile.json")

    def is_first_run(self) -> bool:
        return not os.path.exists(self.profile_path)

    def welcome(self, user_name: str = "") -> str:
        """显示欢迎界面。"""
        msg = NEXUS_WELCOME
        if user_name:
            msg = msg.replace("你的个人AI", f"{user_name}的Nexus")
        return msg

    def setup(self, user_id: str, profession: str = "", interests: list = None) -> dict:
        """初始化用户档案。"""
        profile = {
            "user_id": user_id,
            "profession": profession,
            "interests": interests or [],
            "joined": time.strftime("%Y-%m-%d %H:%M"),
            "conversation_count": 0,
            "preferences": {},
        }
        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return profile

    def load_profile(self) -> dict:
        if os.path.exists(self.profile_path):
            with open(self.profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
