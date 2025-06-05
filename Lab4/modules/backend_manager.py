"""
后端管理模块 - 负责管理LLM API后端，提供负载均衡和故障转移
"""
import random
import time
import json
import secrets  # 导入更安全的随机数生成模块
from utils.logger import log_info
from modules.resp_handler import raft_set, raft_get, resp_decode
from config import DEFAULT_BACKENDS

# 后端列表（全局变量）
backends = []

# 后端列表锁
import threading
backend_lock = threading.Lock()

def initialize_backends():
    """初始化后端服务列表"""
    global backends
    
    # 从存储中加载后端列表
    stored_backends = load_backends_from_store() # 后端列表是List
    
    with backend_lock:
        if stored_backends and len(stored_backends) > 0:
            backends = stored_backends
            log_info("后端初始化完成", {"数量": len(backends), "来源": "存储"})
        else:
            # 使用默认配置
            backends = DEFAULT_BACKENDS.copy()
            log_info("后端初始化完成", {"数量": len(backends), "来源": "默认配置"})
            
            # 只有当默认配置不为空且是首次初始化时才保存到存储
            if len(backends) > 0:
                save_backends_to_store()

def load_backends_from_store():
    """从Raft KV存储加载后端列表"""
    try:
        resp = raft_get("llm_backends")
        backends_data = resp_decode(resp)
        
        if isinstance(backends_data, list):
            return backends_data
        
        if isinstance(backends_data, str):
            try:
                return json.loads(backends_data)
            except:
                pass
                
        return []
    except Exception as e:
        log_info("加载后端列表失败", {"error": str(e)})
        return []

def save_backends_to_store():
    """保存后端列表到Raft KV存储"""
    try:
        # 避免保存空列表
        if not backends or len(backends) == 0:
            log_info("跳过保存空后端列表")
            #这里有点问题，不设置新后端这儿会导致删除不成功，重新刷新后出现已有后端（因为没有修改数据库），可以在删除后端检测后端数量，不能少于一
            return False
            
        backends_json = json.dumps(backends)
        raft_set("llm_backends", backends_json)
        return True
    except Exception as e:
        log_info("保存后端列表失败", {"error": str(e)})
        return False

def get_backends():
    """获取所有后端列表"""
    with backend_lock:
        return backends.copy()

def get_all_backends():#暂时没用
    """获取所有后端列表（兼容性方法）"""
    return get_backends()

def get_backend(backend_id):
    """获取指定ID的后端"""
    try:
        backend_id = int(backend_id)
        with backend_lock:
            if 0 <= backend_id < len(backends):
                return backends[backend_id]
        return None
    except:
        return None

def add_backend(base_url=None, model=None, api_key="ollama", weight=1, **kwargs):
    """添加新后端"""
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
    
    with backend_lock:
        # 检查是否已存在（URL和模型,api_key相同）
        for backend in backends:
             if backend.get("base_url") == base_url and backend.get("model") == model and backend.get("api_key") == api_key:
                return False, "相同URL和模型的后端已存在"
                
        backends.append(new_backend)
        # 用户主动添加后端，保存到存储
        save_backends_to_store()
    
    log_info("添加新后端", {"base_url": base_url, "model": model})
    return True, "后端添加成功"

def update_backend(backend_id, data):
    """更新后端信息"""
    try:
        backend_id = int(backend_id)
        with backend_lock:
            if 0 <= backend_id < len(backends):
                backend = backends[backend_id]
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
                if "api_key" in data and data["api_key"].strip():
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
                
                save_backends_to_store()
                return True, "后端更新成功"
            return False, "无效的后端ID"
    except Exception as e:
        log_info("更新后端失败", {"error": str(e)})
        return False, f"更新失败: {str(e)}"

def delete_backend(backend_id):
    """删除后端"""
    try:
        backend_id = int(backend_id)
        with backend_lock:
            if(len(backends)==1):
                return False, "至少需要保留一个后端"
            if 0 <= backend_id < len(backends):
                deleted = backends.pop(backend_id)
                # 用户主动删除后端，保存到存储
                save_backends_to_store()
                log_info("删除后端", {"base_url": deleted.get("base_url"), "model": deleted.get("model")})
                return True, "后端删除成功"
            return False, "无效的后端ID"
    except:
        return False, "删除失败"

def get_available_backend():
    """
    选择一个可用后端（可用于负载均衡）
    
    返回:
        dict: 选择的后端信息，包含backend_id字段
    """
    #lab4_Job:请补充代码，实现自己的算法选择一个后端返回
    
    with backend_lock:
        if not backends or len(backends) == 0:
            log_info("没有可用的后端")
            return None
        
        # 获取所有活跃的后端
        active_backends = []
        for i, backend in enumerate(backends):
            if backend.get("status", "active") == "active":
                backend_copy = backend.copy()
                backend_copy["backend_id"] = i
                active_backends.append(backend_copy)
        
        if not active_backends:
            log_info("没有活跃的后端")
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
                selected_backend = backend
                log_info("选择后端", {
                    "backend_id": selected_backend["backend_id"],
                    "base_url": selected_backend.get("base_url"),
                    "model": selected_backend.get("model"),
                    "weight": selected_backend.get("weight", 1)
                })
                return selected_backend
        
        # 兜底方案：如果权重计算有问题，返回第一个活跃后端
        selected_backend = active_backends[0]
        log_info("使用兜底后端", {
            "backend_id": selected_backend["backend_id"],
            "base_url": selected_backend.get("base_url"),
            "model": selected_backend.get("model")
        })
        return selected_backend

def mark_backend_failure(backend_id_or_info):#暂时没用上
    """标记后端失败"""
    with backend_lock:
        # 如果传入的是ID
        if isinstance(backend_id_or_info, int):
            backend_id = backend_id_or_info
            if 0 <= backend_id < len(backends):
                backend = backends[backend_id]
                backend["failures"] += 1
                if backend["failures"] >= 3:  # 3次失败后标记为不可用
                    backend["status"] = "inactive"
                    log_info("后端标记为不可用", {"id": backend_id, "failures": backend["failures"]})
                save_backends_to_store()
        
        # 如果传入的是后端信息对象
        elif isinstance(backend_id_or_info, dict):
            backend_info = backend_id_or_info
            base_url = backend_info.get("base_url")
            model = backend_info.get("model")
            
            # 查找匹配的后端
            for i, backend in enumerate(backends):
                if backend.get("base_url") == base_url and backend.get("model") == model:
                    backend["failures"] += 1
                    if backend["failures"] >= 3:
                        backend["status"] = "inactive"
                        log_info("后端标记为不可用", {"id": i, "base_url": base_url, "model": model})
                    save_backends_to_store()
                    break 