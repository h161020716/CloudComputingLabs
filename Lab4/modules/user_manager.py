"""
用户管理模块 - 负责用户注册、登录和数据管理
"""
import json
import os
import hashlib
import time
from datetime import datetime, timedelta
import secrets
from utils.logger import log_info

# 用户数据文件路径
USER_DATA_FILE = "data/users.json"
SESSION_DATA_FILE = "data/sessions.json"

# 确保数据目录存在
def ensure_data_dir():
    """确保数据目录存在"""
    if not os.path.exists("data"):
        os.makedirs("data", exist_ok=True)

def hash_password(password):
    """对密码进行哈希处理"""
    salt = "Lab4_ChatSystem_Salt_2024"  # 应用特定的盐值
    return hashlib.sha256((password + salt).encode()).hexdigest()

def load_users():
    """加载用户数据"""
    ensure_data_dir()
    try:
        if os.path.exists(USER_DATA_FILE):
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        log_info("加载用户数据失败", {"error": str(e)})
        return {}

def save_users(users):
    """保存用户数据"""
    ensure_data_dir()
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_info("保存用户数据失败", {"error": str(e)})
        return False

def load_sessions():
    """加载会话数据"""
    ensure_data_dir()
    try:
        if os.path.exists(SESSION_DATA_FILE):
            with open(SESSION_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        log_info("加载会话数据失败", {"error": str(e)})
        return {}

def save_sessions(sessions):
    """保存会话数据"""
    ensure_data_dir()
    try:
        with open(SESSION_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_info("保存会话数据失败", {"error": str(e)})
        return False

def register_user(username, password, email=None, display_name=None):
    """
    注册新用户
    
    参数:
        username (str): 用户名
        password (str): 密码
        email (str): 邮箱 (可选)
        display_name (str): 显示名称 (可选)
        
    返回:
        dict: {"success": bool, "message": str, "user_id": str}
    """
    if not username or not password:
        return {"success": False, "message": "用户名和密码不能为空"}
    
    if len(username) < 3:
        return {"success": False, "message": "用户名至少需要3个字符"}
    
    if len(password) < 6:
        return {"success": False, "message": "密码至少需要6个字符"}
    
    users = load_users()
    
    # 检查用户名是否已存在
    if username in users:
        return {"success": False, "message": "用户名已存在"}
    
    # 检查邮箱是否已存在
    if email:
        for user_data in users.values():
            if user_data.get("email") == email:
                return {"success": False, "message": "邮箱已被注册"}
    
    # 创建新用户
    user_id = f"user_{int(time.time())}_{secrets.token_hex(4)}"
    user_data = {
        "user_id": user_id,
        "username": username,
        "password_hash": hash_password(password),
        "email": email or "",
        "display_name": display_name or username,
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_active": True
    }
    
    users[username] = user_data
    
    if save_users(users):
        log_info("用户注册成功", {"username": username, "user_id": user_id})
        return {"success": True, "message": "注册成功", "user_id": user_id}
    else:
        return {"success": False, "message": "保存用户数据失败"}

def authenticate_user(username, password):
    """
    验证用户登录
    
    参数:
        username (str): 用户名
        password (str): 密码
        
    返回:
        dict: {"success": bool, "message": str, "user": dict}
    """
    if not username or not password:
        return {"success": False, "message": "用户名和密码不能为空"}
    
    users = load_users()
    
    if username not in users:
        return {"success": False, "message": "用户不存在"}
    
    user_data = users[username]
    
    if not user_data.get("is_active", True):
        return {"success": False, "message": "账户已被禁用"}
    
    # 验证密码
    if user_data["password_hash"] != hash_password(password):
        return {"success": False, "message": "密码错误"}
    
    # 更新最后登录时间
    user_data["last_login"] = datetime.now().isoformat()
    users[username] = user_data
    save_users(users)
    
    log_info("用户登录成功", {"username": username})
    
    # 返回用户信息（不包含密码）
    safe_user = {
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "email": user_data["email"],
        "display_name": user_data["display_name"],
        "last_login": user_data["last_login"]
    }
    
    return {"success": True, "message": "登录成功", "user": safe_user}

def create_session(user_id, username):
    """
    创建用户会话
    
    参数:
        user_id (str): 用户ID
        username (str): 用户名
        
    返回:
        str: 会话token
    """
    sessions = load_sessions()
    
    # 生成会话token
    session_token = secrets.token_urlsafe(32)
    
    # 会话过期时间（7天）
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()
    
    sessions[session_token] = {
        "user_id": user_id,
        "username": username,
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at,
        "last_accessed": datetime.now().isoformat()
    }
    
    save_sessions(sessions)
    
    log_info("创建用户会话", {"username": username, "expires_at": expires_at})
    
    return session_token

def validate_session(session_token):
    """
    验证会话有效性
    
    参数:
        session_token (str): 会话token
        
    返回:
        dict: {"valid": bool, "user": dict}
    """
    if not session_token:
        return {"valid": False, "user": None}
    
    sessions = load_sessions()
    
    if session_token not in sessions:
        return {"valid": False, "user": None}
    
    session_data = sessions[session_token]
    
    # 检查会话是否过期
    expires_at = datetime.fromisoformat(session_data["expires_at"])
    if datetime.now() > expires_at:
        # 删除过期会话
        del sessions[session_token]
        save_sessions(sessions)
        return {"valid": False, "user": None}
    
    # 更新最后访问时间
    session_data["last_accessed"] = datetime.now().isoformat()
    sessions[session_token] = session_data
    save_sessions(sessions)
    
    # 获取用户信息
    users = load_users()
    username = session_data["username"]
    
    if username not in users:
        # 用户不存在，删除会话
        del sessions[session_token]
        save_sessions(sessions)
        return {"valid": False, "user": None}
    
    user_data = users[username]
    safe_user = {
        "user_id": user_data["user_id"],
        "username": user_data["username"],
        "email": user_data["email"],
        "display_name": user_data["display_name"],
        "last_login": user_data["last_login"]
    }
    
    return {"valid": True, "user": safe_user}

def logout_user(session_token):
    """
    用户登出
    
    参数:
        session_token (str): 会话token
        
    返回:
        bool: 是否成功
    """
    if not session_token:
        return False
    
    sessions = load_sessions()
    
    if session_token in sessions:
        username = sessions[session_token].get("username", "unknown")
        del sessions[session_token]
        save_sessions(sessions)
        log_info("用户登出", {"username": username})
        return True
    
    return False

def get_user_stats():
    """
    获取用户统计信息
    
    返回:
        dict: 统计信息
    """
    users = load_users()
    sessions = load_sessions()
    
    # 清理过期会话
    now = datetime.now()
    active_sessions = {}
    for token, session_data in sessions.items():
        expires_at = datetime.fromisoformat(session_data["expires_at"])
        if now <= expires_at:
            active_sessions[token] = session_data
    
    if len(active_sessions) != len(sessions):
        save_sessions(active_sessions)
    
    return {
        "total_users": len(users),
        "active_sessions": len(active_sessions),
        "registered_today": len([
            user for user in users.values()
            if user.get("created_at", "").startswith(datetime.now().strftime("%Y-%m-%d"))
        ])
    } 