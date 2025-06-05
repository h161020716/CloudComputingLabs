"""
用户级后端管理模块 - 为每个用户管理独立的LLM后端配置
"""
import json
import os
import time
import secrets
import threading
from utils.logger import log_info
from config import DEFAULT_BACKENDS

# 用户后端配置目录
USER_BACKENDS_DIR = "data/user_backends"

# 用户后端缓存 - {user_id: backends_list}
user_backends_cache = {}
cache_lock = threading.Lock()

def ensure_user_backends_dir():
    """确保用户后端配置目录存在"""
    if not os.path.exists(USER_BACKENDS_DIR):
        os.makedirs(USER_BACKENDS_DIR, exist_ok=True)

def get_user_backends_file(user_id):
    """获取用户后端配置文件路径"""
    ensure_user_backends_dir()
    return os.path.join(USER_BACKENDS_DIR, f"{user_id}.json")

def load_user_backends(user_id):
    """加载用户的后端配置"""
    try:
        backends_file = get_user_backends_file(user_id)
        
        # 如果文件存在，从文件加载
        if os.path.exists(backends_file):
            with open(backends_file, 'r', encoding='utf-8') as f:
                backends = json.load(f)
            if isinstance(backends, list) and len(backends) > 0:
                log_info("加载用户后端配置", {"user_id": user_id, "count": len(backends)})
                return backends
        
        # 如果文件不存在或为空，使用默认配置
        default_backends = DEFAULT_BACKENDS.copy() if DEFAULT_BACKENDS else []
        if len(default_backends) == 0:
            # 如果默认配置也为空，创建一个示例配置
            default_backends = [{
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "api_key": "your-api-key-here",
                "weight": 1,
                "status": "active",
                "last_check": time.time(),
                "failures": 0
            }]
        
        # 为新用户保存默认配置
        save_user_backends(user_id, default_backends)
        log_info("为新用户创建后端配置", {"user_id": user_id, "count": len(default_backends)})
        return default_backends
        
    except Exception as e:
        log_info("加载用户后端配置失败", {"user_id": user_id, "error": str(e)})
        return []

def save_user_backends(user_id, backends):
    """保存用户的后端配置"""
    try:
        backends_file = get_user_backends_file(user_id)
        with open(backends_file, 'w', encoding='utf-8') as f:
            json.dump(backends, f, ensure_ascii=False, indent=2)
        
        # 更新缓存
        with cache_lock:
            user_backends_cache[user_id] = backends.copy()
        
        log_info("保存用户后端配置", {"user_id": user_id, "count": len(backends)})
        return True
    except Exception as e:
        log_info("保存用户后端配置失败", {"user_id": user_id, "error": str(e)})
        return False

def get_user_backends(user_id):
    """获取用户的所有后端配置"""
    with cache_lock:
        # 先检查缓存
        if user_id in user_backends_cache:
            return user_backends_cache[user_id].copy()
    
    # 缓存未命中，从文件加载
    backends = load_user_backends(user_id)
    
    # 更新缓存
    with cache_lock:
        user_backends_cache[user_id] = backends.copy()
    
    return backends

def get_user_backend(user_id, backend_id):
    """获取用户的指定后端配置"""
    try:
        backend_id = int(backend_id)
        backends = get_user_backends(user_id)
        if 0 <= backend_id < len(backends):
            return backends[backend_id]
        return None
    except:
        return None

def add_user_backend(user_id, base_url=None, model=None, api_key="ollama", weight=1, **kwargs):
    """为用户添加新的后端配置"""
    # 验证必要参数
    if not base_url or not base_url.strip():
        return False, "基础URL不能为空"
    
    if not model or not model.strip():
        return False, "模型名称不能为空"
    
    # 验证URL格式
    if not base_url.startswith(("http://", "https://")):
        return False, "URL必须以http://或https://开头"
    
    # 构建后端信息
    new_backend = {
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "weight": weight,
        "status": "active",
        "last_check": time.time(),
        "failures": 0
    }
    
    # 验证权重格式
    try:
        weight = int(weight)
        if weight < 1:
            weight = 1
        new_backend["weight"] = weight
    except:
        new_backend["weight"] = 1
    
    # 获取用户当前的后端列表
    backends = get_user_backends(user_id)
    
    # 检查是否已存在（URL和模型相同）
    for backend in backends:
        if backend.get("base_url") == base_url and backend.get("model") == model:
            return False, "相同URL和模型的后端已存在"
    
    # 添加新后端
    backends.append(new_backend)
    
    # 保存更新
    if save_user_backends(user_id, backends):
        log_info("用户添加新后端", {"user_id": user_id, "base_url": base_url, "model": model})
        return True, "后端添加成功"
    else:
        return False, "保存后端配置失败"

def update_user_backend(user_id, backend_id, data):
    """更新用户的后端配置"""
    try:
        backend_id = int(backend_id)
        backends = get_user_backends(user_id)
        
        if not (0 <= backend_id < len(backends)):
            return False, "无效的后端ID"
        
        # 更新基础URL
        if "base_url" in data and data["base_url"].strip():
            base_url = data["base_url"].strip()
            if not base_url.startswith(("http://", "https://")):
                return False, "基础URL必须以http://或https://开头"
            backends[backend_id]["base_url"] = base_url
        
        # 更新模型
        if "model" in data and data["model"].strip():
            backends[backend_id]["model"] = data["model"].strip()
        
        # 更新API密钥
        if "api_key" in data:
            backends[backend_id]["api_key"] = data["api_key"]
        
        # 更新权重
        if "weight" in data:
            try:
                weight = int(data["weight"])
                if weight < 1:
                    weight = 1
                backends[backend_id]["weight"] = weight
            except:
                pass
        
        # 更新状态
        if "status" in data and data["status"] in ["active", "inactive"]:
            backends[backend_id]["status"] = data["status"]
        
        # 重置故障计数
        if "reset_failures" in data and data["reset_failures"]:
            backends[backend_id]["failures"] = 0
            backends[backend_id]["status"] = "active"
        
        # 保存更新
        if save_user_backends(user_id, backends):
            log_info("用户更新后端配置", {"user_id": user_id, "backend_id": backend_id})
            return True, "后端更新成功"
        else:
            return False, "保存后端配置失败"
        
    except Exception as e:
        log_info("更新用户后端配置失败", {"user_id": user_id, "error": str(e)})
        return False, f"更新失败: {str(e)}"

def delete_user_backend(user_id, backend_id):
    """删除用户的后端配置"""
    try:
        backend_id = int(backend_id)
        backends = get_user_backends(user_id)
        
        if len(backends) <= 1:
            return False, "至少需要保留一个后端"
        
        if not (0 <= backend_id < len(backends)):
            return False, "无效的后端ID"
        
        # 删除后端
        deleted = backends.pop(backend_id)
        
        # 保存更新
        if save_user_backends(user_id, backends):
            log_info("用户删除后端", {
                "user_id": user_id,
                "base_url": deleted.get("base_url"),
                "model": deleted.get("model")
            })
            return True, "后端删除成功"
        else:
            return False, "保存后端配置失败"
        
    except Exception as e:
        log_info("删除用户后端配置失败", {"user_id": user_id, "error": str(e)})
        return False, "删除失败"

def get_user_available_backend(user_id):
    """
    为用户选择一个可用后端（负载均衡）
    
    参数:
        user_id: 用户ID
        
    返回:
        dict: 选择的后端信息，包含backend_id字段
    """
    backends = get_user_backends(user_id)
    
    if not backends or len(backends) == 0:
        log_info("用户没有可用的后端", {"user_id": user_id})
        return None
    
    # 获取所有活跃的后端
    active_backends = []
    for i, backend in enumerate(backends):
        if backend.get("status", "active") == "active":
            backend_copy = backend.copy()
            backend_copy["backend_id"] = i
            active_backends.append(backend_copy)
    
    if not active_backends:
        log_info("用户没有活跃的后端", {"user_id": user_id})
        return None
    
    # 实现加权随机负载均衡算法
    # 1. 计算总权重
    total_weight = sum(backend.get("weight", 1) for backend in active_backends)
    
    # 2. 使用加密安全的随机数生成器选择
    random_value = secrets.randbelow(total_weight)
    
    # 3. 根据权重选择后端
    current_weight = 0
    for backend in active_backends:
        backend_weight = backend.get("weight", 1)
        current_weight += backend_weight
        if random_value < current_weight:
            log_info("为用户选择后端", {
                "user_id": user_id,
                "backend_id": backend["backend_id"],
                "base_url": backend.get("base_url"),
                "model": backend.get("model"),
                "weight": backend.get("weight", 1)
            })
            return backend
    
    # 如果没有选中（理论上不应该发生），返回第一个
    log_info("为用户选择默认后端", {"user_id": user_id})
    return active_backends[0]

def clear_user_cache(user_id):
    """清除用户的后端配置缓存"""
    with cache_lock:
        if user_id in user_backends_cache:
            del user_backends_cache[user_id]
            log_info("清除用户后端缓存", {"user_id": user_id})

def init_user_backends(user_id):
    """初始化用户的后端配置（如果不存在）"""
    backends = get_user_backends(user_id)
    log_info("初始化用户后端配置", {"user_id": user_id, "count": len(backends)})
    return backends 