"""
原生微信数据库读取器 - 彻底取代 WeFlow
支持自动定位、解密和增量查询消息。
"""
import os
import shutil
import sqlite3
import hashlib
import hmac
import logging
import time
import asyncio
from pathlib import Path
from typing import List, Optional, Callable
from .models import WeChatMessage, SessionType, MessageType
from .diagnostics import locate_wechat_db

try:
    from Cryptodome.Cipher import AES
except ImportError:
    try:
        from Crypto.Cipher import AES
    except ImportError:
        AES = None

logger = logging.getLogger("wechat-cli.db_reader")

class WeChatDBReader:
    def __init__(self, key: str, db_path: Optional[str] = None):
        self.key = bytes.fromhex(key) if key else None
        self.db_path = Path(db_path) if db_path else self._auto_locate_db()
        self.page_size = 4096
        self.last_msg_id = 0

    def _auto_locate_db(self) -> Optional[Path]:
        """自动定位当前登录用户的 MSG.db"""
        return locate_wechat_db()

    def decrypt_db(self, source: Path, target: Path) -> bool:
        """
        解密 SQLCipher 数据库到临时文件
        这是最稳定的方式，避开复杂的 SQLCipher 驱动安装。
        """
        if not AES:
            logger.error("缺少依赖: pip install pycryptodome")
            return False

        try:
            with open(source, 'rb') as f:
                data = f.read()

            salt = data[:16]
            key = hashlib.pbkdf2_hmac('sha1', self.key, salt, 64000, 32)
            
            with open(target, 'wb') as f:
                # 写入 SQLite 文件头
                f.write(b'SQLite format 3\x00')
                
                # 逐页解密
                for i in range(1, len(data) // self.page_size):
                    offset = i * self.page_size
                    page = data[offset : offset + self.page_size]
                    
                    # 每一页最后 48 字节通常是 HMAC 和 IV
                    iv = page[-48:-32]
                    cipher = AES.new(key, AES.MODE_CBC, iv)
                    decrypted = cipher.decrypt(page[:-48])
                    f.write(decrypted)
                    f.write(page[-48:]) # 补全页面大小（虽然内容已解密）
            return True
        except Exception as e:
            logger.error(f"数据库解密失败: {e}")
            return False

    def get_new_messages(self) -> List[WeChatMessage]:
        """增量查询新消息"""
        if not self.db_path or not self.db_path.exists():
            return []
        if not self.key:
            logger.error("缺少数据库 Key，无法读取微信数据库")
            return []

        # 1. 拷贝并解密到临时文件（避免锁死数据库）
        temp_db = Path("/tmp/wechat_msg_temp.db") if os.name != 'nt' else Path(os.environ['TEMP']) / "wechat_msg_temp.db"
        encrypted_copy = temp_db.with_suffix(".encrypted")
        
        # 实际生产中建议使用更加高效的 WAL 读取方式，这里采用“快照解密”作为最稳妥的兼容方案
        shutil.copy2(self.db_path, encrypted_copy)
        if not self.decrypt_db(encrypted_copy, temp_db):
            return []
        
        msgs = []
        try:
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            # 查询最新消息
            # 微信 4.0 的表名通常是 Message
            cursor.execute('''
                SELECT localId, TalkerId, CreateTime, Content, Type, IsSender 
                FROM Message 
                WHERE localId > ? 
                ORDER BY localId ASC
            ''', (self.last_msg_id,))
            
            rows = cursor.fetchall()
            for row in rows:
                mid, talker, ctime, content, mtype, is_sender = row
                self.last_msg_id = max(self.last_msg_id, mid)
                
                # 转换为标准模型
                msgs.append(WeChatMessage(
                    session_id=talker,
                    content=str(content),
                    timestamp=ctime,
                    message_id=str(mid),
                    is_self=bool(is_sender),
                    session_type=SessionType.GROUP if "@chatroom" in talker else SessionType.PRIVATE
                ))
            conn.close()
        except Exception as e:
            logger.error(f"读取数据库出错: {e}")
            
        return msgs

    async def start_polling(self, callback: Callable[[WeChatMessage], None], interval: float = 2.0):
        """开始实时轮询新消息"""
        logger.info(f"开始轮询微信数据库: {self.db_path}")
        while True:
            try:
                new_msgs = self.get_new_messages()
                for m in new_msgs:
                    await callback(m)
            except Exception as e:
                logger.error(f"轮询异常: {e}")
            await asyncio.sleep(interval)
