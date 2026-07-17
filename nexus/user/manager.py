"""多用户管理——借鉴ClaudeCode多租户隔离+LoRA切换"""
import os, json, logging
logger = logging.getLogger("nexus.user")

class UserManager:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "..", "data", "users")
        os.makedirs(self.data_dir, exist_ok=True)
        self.current = None

    def create(self, uid: str, name: str, profession: str = ""):
        user = {"id": uid, "name": name, "profession": profession}
        with open(os.path.join(self.data_dir, f"{uid}.json"), "w") as f:
            json.dump(user, f, ensure_ascii=False)

    def switch(self, uid: str):
        path = os.path.join(self.data_dir, f"{uid}.json")
        if not os.path.exists(path): raise ValueError(f"User not found: {uid}")
        self.current = uid

    def get_current(self):
        if not self.current: return {}
        path = os.path.join(self.data_dir, f"{self.current}.json")
        with open(path) as f: return json.load(f)
