# -*- coding: utf-8 -*-
"""认证:单用户/受邀账号体系。

- 密码:PBKDF2-HMAC-SHA256,600k 迭代 + 16B 随机盐(hashlib 标准实现,非自造算法)
- 会话:服务端随机 token(32B),有效期 7 天,滑动续期;cookie HttpOnly + SameSite=Lax
- 审计:登录/登出/失败/敏感操作写入 data/audit.jsonl
- 数据层按单用户隔离:所有集合即该用户数据;导出/删除走 exporter/account
"""
import base64
import datetime
import hashlib
import json
import os
import secrets

PBKDF2_ITER = 600_000
SESSION_TTL_DAYS = 7
AUDIT_FILE = "audit.jsonl"


def _hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITER)
    return base64.b64encode(salt).decode(), base64.b64encode(dk).decode()


def verify_password(password, salt_b64, hash_b64):
    salt = base64.b64decode(salt_b64)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITER)
    return secrets.compare_digest(base64.b64encode(dk).decode(), hash_b64)


def audit(store, event, detail=""):
    """追加审计事件(一行一条 JSON)。"""
    path = os.path.join(store.data_dir, AUDIT_FILE)
    entry = {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "detail": str(detail)[:300],
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def get_user(store):
    users = store.load("users")
    return users[0] if users else None


def create_user(store, username, password):
    if get_user(store):
        return None, "账号已存在(如需重置请删除 data/users.json 并联系数据备份流程)"
    if len(password) < 6:
        return None, "密码至少 6 位"
    salt, pw = _hash_password(password)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    user = {"username": username.strip() or "ascent", "salt": salt,
            "password": pw, "created": now, "display_name": username.strip() or "ascent"}
    store.save("users", [user])
    return user, None


def check_login(store, username, password):
    user = get_user(store)
    if not user:
        return None, "账号尚未创建"
    if username and username.strip().lower() != user["username"].lower():
        return None, "用户名或密码不正确"
    if not verify_password(password, user["salt"], user["password"]):
        return None, "用户名或密码不正确"
    return user, None


def create_session(store, username):
    token = secrets.token_hex(32)
    expires = (datetime.datetime.now()
               + datetime.timedelta(days=SESSION_TTL_DAYS)).isoformat(timespec="seconds")
    sessions = store.load("sessions")
    sessions = [s for s in sessions
                if s["expires"] > datetime.datetime.now().isoformat(timespec="seconds")][-50:]
    sessions.append({"token": token, "user": username, "expires": expires,
                     "created": datetime.datetime.now().isoformat(timespec="seconds")})
    store.save("sessions", sessions)
    return token, expires


def session_user(store, token):
    if not token:
        return None
    now = datetime.datetime.now().isoformat(timespec="seconds")
    for s in store.load("sessions"):
        if s["token"] == token and s["expires"] > now:
            return s["user"]
    return None


def destroy_session(store, token):
    sessions = [s for s in store.load("sessions") if s["token"] != token]
    store.save("sessions", sessions)


def change_password(store, old_password, new_password):
    user = get_user(store)
    if not user:
        return "账号不存在"
    if not verify_password(old_password, user["salt"], user["password"]):
        return "原密码不正确"
    if len(new_password) < 6:
        return "新密码至少 6 位"
    salt, pw = _hash_password(new_password)
    user["salt"], user["password"] = salt, pw
    users = store.load("users")
    users[0] = user
    store.save("users", users)
    return None
