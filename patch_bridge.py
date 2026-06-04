import sys, re

with open('wechat_cli/agent_bridge.py', 'r', encoding='utf-8') as f:
    c = f.read()

def_resolve_target = '''    def resolve_reply_target(self, chat_id: str) -> str:
        """将 Hakimi chat_id 解析为微信发送通道需要的显示名称。"""
        # 如果缓存里有，直接使用；否则交给 weflow 的映射解析器
        resolved = self._reply_targets.get(chat_id)
        if resolved:
            return resolved
        if hasattr(self, "weflow") and hasattr(self.weflow, "name_resolver"):
            return self.weflow.name_resolver.resolve(chat_id)
        return chat_id'''

c = re.sub(r'    def resolve_reply_target\(self, chat_id: str\) -> str:.*?return self\._reply_targets\.get\(chat_id\) or self\.weflow\.name_resolver\.resolve\(chat_id\)', def_resolve_target, c, flags=re.DOTALL)

with open('wechat_cli/agent_bridge.py', 'w', encoding='utf-8') as f:
    f.write(c)
