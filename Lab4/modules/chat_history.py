"""
聊天历史管理模块 - 负责存储和检索用户聊天历史
"""
import json
import time
import os
from modules.resp_handler import resp_decode, raft_set, raft_get
from utils.logger import log_info
from config import MAX_HISTORY_CHARS

# 本地缓存字典，用于临时存储聊天历史
local_cache = {}
# 缓存文件目录
CACHE_DIR = "data/chat_cache"

def ensure_cache_dir():
    """确保缓存目录存在"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

def get_local_cache_file(client_id):
    """获取本地缓存文件路径"""
    ensure_cache_dir()
    return os.path.join(CACHE_DIR, f"{client_id}.json")

def save_to_local_cache(client_id, messages):
    """保存到本地缓存"""
    try:
        local_cache[client_id] = messages.copy()
        
        # 同时保存到文件
        cache_file = get_local_cache_file(client_id)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        
        log_info("本地缓存保存成功", {"client_id": client_id, "消息数量": len(messages)})
        return True
    except Exception as e:
        log_info("本地缓存保存失败", {"client_id": client_id, "error": str(e)})
        return False

def load_from_local_cache(client_id):
    """从本地缓存加载"""
    try:
        # 先尝试从内存缓存
        if client_id in local_cache:
            log_info("从内存缓存获取历史", {"client_id": client_id})
            return local_cache[client_id].copy()
        
        # 再尝试从文件缓存
        cache_file = get_local_cache_file(client_id)
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
            
            # 加载到内存缓存
            local_cache[client_id] = messages.copy()
            log_info("从文件缓存获取历史", {"client_id": client_id, "消息数量": len(messages)})
            return messages
        
        return []
    except Exception as e:
        log_info("本地缓存加载失败", {"client_id": client_id, "error": str(e)})
        return []

def get_chat_history(client_id, max_retries=2):
    """
    获取指定客户端的聊天历史
    
    参数:
        client_id (str): 客户端标识
        max_retries (int): 最大重试次数
        
    返回:
        list: 聊天消息列表
    """
    # 首先尝试从Raft获取最新数据
    for attempt in range(max_retries):
        try:
            # 从Raft KV存储中获取历史记录
            resp = raft_get(client_id)
            print("resp:",resp)
            # 使用RESP解码器
            history_data = resp_decode(resp)
            
            # 记录操作
            log_info("获取聊天历史", {"client_id": client_id, "attempt": attempt + 1})
            
            # 检查解码结果
            if history_data is None:
                if attempt < max_retries - 1:
                    log_info("聊天历史数据为空，重试中", {"client_id": client_id, "attempt": attempt + 1})
                    time.sleep(0.3)  # 缩短等待时间
                    continue
                else:
                    break  # 退出重试循环，使用本地缓存
                
            # 如果已经是列表，更新本地缓存并返回
            if isinstance(history_data, list):
                save_to_local_cache(client_id, history_data)
                return history_data
                
            # 尝试解析为JSON
            try:
                if isinstance(history_data, str):
                    messages = json.loads(history_data)
                    if isinstance(messages, list):
                        save_to_local_cache(client_id, messages)
                        return messages
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    log_info("JSON解析失败，重试中", {"client_id": client_id, "attempt": attempt + 1, "error": str(e)})
                    time.sleep(0.3)
                    continue
                else:
                    log_info("JSON解析最终失败", {"client_id": client_id, "data": str(history_data)[:100]})
                    break
            
        except Exception as e:
            if attempt < max_retries - 1:
                log_info("获取聊天历史失败，重试中", {"client_id": client_id, "attempt": attempt + 1, "error": str(e)})
                time.sleep(0.3)
                continue
            else:
                log_info("获取聊天历史最终失败", {"client_id": client_id, "error": str(e)})
                break
    
    # Raft获取失败，尝试使用本地缓存
    log_info("Raft获取失败，使用本地缓存", {"client_id": client_id})
    cached_messages = load_from_local_cache(client_id)
    return cached_messages

def save_chat_history(client_id, messages, max_retries=2):
    """
    保存指定客户端的聊天历史
    
    参数:
        client_id (str): 客户端标识
        messages (list): 消息列表
        max_retries (int): 最大重试次数
        
    返回:
        bool: 保存是否成功
    """
    # 立即保存到本地缓存
    local_saved = save_to_local_cache(client_id, messages)
    
    # 限制历史长度
    if len(json.dumps(messages, ensure_ascii=False)) > MAX_HISTORY_CHARS:
        # 保留最近的消息
        while len(json.dumps(messages, ensure_ascii=False)) > MAX_HISTORY_CHARS and len(messages) > 2:
            messages.pop(0)  # 删除最早的消息
        log_info("聊天历史截断", {"client_id": client_id, "保留消息数": len(messages)})
    
    # 尝试保存到Raft
    raft_saved = False
    for attempt in range(max_retries):
        try:
            result = raft_set(client_id, messages)
            
            # 检查保存结果
            if result and ("+OK" in str(result) or "OK" in str(result)):
                log_info("Raft保存成功", {"client_id": client_id, "消息数量": len(messages), "attempt": attempt + 1})
                raft_saved = True
                break
            else:
                if attempt < max_retries - 1:
                    log_info("Raft保存失败，重试中", {"client_id": client_id, "attempt": attempt + 1, "result": str(result)[:100]})
                    time.sleep(0.5)
                    continue
                else:
                    log_info("Raft保存最终失败", {"client_id": client_id, "result": str(result)[:100]})
                    
        except Exception as e:
            if attempt < max_retries - 1:
                log_info("Raft保存异常，重试中", {"client_id": client_id, "attempt": attempt + 1, "error": str(e)})
                time.sleep(0.5)
                continue
            else:
                log_info("Raft保存最终异常", {"client_id": client_id, "error": str(e)})
    
    log_info("保存聊天历史", {
        "client_id": client_id, 
        "消息数量": len(messages),
        "本地缓存": "成功" if local_saved else "失败",
        "Raft存储": "成功" if raft_saved else "失败"
    })
    
    # 只要有一个保存成功就认为成功
    return local_saved or raft_saved

def smart_truncate_messages(messages):
    """
    智能截断消息历史，保持在大小限制内
    
    参数:
        messages (list): 原始消息列表
        
    返回:
        list: 截断后的消息列表
    """
    if not messages:
        return []
    
    # 计算当前大小
    current_json = json.dumps(messages, ensure_ascii=False)
    if len(current_json) <= MAX_HISTORY_CHARS:
        return messages
    
    # 保留最新的消息，删除最早的
    truncated = messages.copy()
    while len(json.dumps(truncated, ensure_ascii=False)) > MAX_HISTORY_CHARS and len(truncated) > 2:
        truncated.pop(0)
    
    return truncated 