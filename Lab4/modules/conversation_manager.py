"""
对话管理器模块 - 负责管理用户的多个对话
"""
import json
import uuid
import os
from datetime import datetime
from utils.logger import log_info
from modules.resp_handler import resp_decode, raft_set, raft_get

# 本地缓存目录
CONVERSATIONS_DIR = "data/conversations"
CONVERSATION_HISTORY_DIR = "data/conversation_history"

def ensure_directories():
    """确保必要目录存在"""
    for directory in [CONVERSATIONS_DIR, CONVERSATION_HISTORY_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

def get_user_conversations_file(user_id):
    """获取用户对话列表文件路径"""
    ensure_directories()
    return os.path.join(CONVERSATIONS_DIR, f"{user_id}.json")

def create_conversation(user_id, title):
    """创建新对话"""
    try:
        # 使用时间戳作为对话ID（格式：年月日_时分秒_毫秒）
        now = datetime.now()
        conversation_id = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 保留毫秒的前3位
        now_iso = now.isoformat()
        
        conversation = {
            "id": conversation_id,
            "title": title,
            "user_id": user_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "message_count": 0
        }
        
        # 加载现有对话列表
        conversations = get_user_conversations(user_id)
        
        # 添加新对话到列表开头
        conversations.insert(0, conversation)
        
        # 保存到本地文件
        save_user_conversations(user_id, conversations)
        
        log_info("创建新对话", {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "title": title
        })
        
        return conversation
        
    except Exception as e:
        log_info("创建对话失败", {"user_id": user_id, "error": str(e)})
        raise e

def get_user_conversations(user_id):
    """获取用户的所有对话"""
    try:
        conversations_file = get_user_conversations_file(user_id)
        if os.path.exists(conversations_file):
            with open(conversations_file, 'r', encoding='utf-8') as f:
                conversations = json.load(f)
            # 按更新时间排序（最新的在前）
            conversations.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            return conversations
        return []
    except Exception as e:
        log_info("获取用户对话列表失败", {"user_id": user_id, "error": str(e)})
        return []

def save_user_conversations(user_id, conversations):
    """保存用户对话列表到本地文件"""
    try:
        conversations_file = get_user_conversations_file(user_id)
        with open(conversations_file, 'w', encoding='utf-8') as f:
            json.dump(conversations, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_info("保存用户对话列表失败", {"user_id": user_id, "error": str(e)})
        return False

def get_conversation(conversation_id, user_id):
    """获取指定对话的信息"""
    try:
        conversations = get_user_conversations(user_id)
        for conversation in conversations:
            if conversation['id'] == conversation_id:
                return conversation
        return None
    except Exception as e:
        log_info("获取对话信息失败", {"conversation_id": conversation_id, "error": str(e)})
        return None

def update_conversation(conversation_id, user_id, title=None, message_count=None):
    """更新对话信息"""
    try:
        conversations = get_user_conversations(user_id)
        updated = False
        
        for conversation in conversations:
            if conversation['id'] == conversation_id:
                if title is not None:
                    conversation['title'] = title
                if message_count is not None:
                    conversation['message_count'] = message_count
                conversation['updated_at'] = datetime.now().isoformat()
                updated = True
                break
        
        if updated:
            # 重新排序
            conversations.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            # 保存到本地
            save_user_conversations(user_id, conversations)
        
        return updated
    except Exception as e:
        log_info("更新对话失败", {"conversation_id": conversation_id, "error": str(e)})
        return False

def delete_conversation(conversation_id, user_id):
    """删除指定对话"""
    try:
        conversations = get_user_conversations(user_id)
        original_count = len(conversations)
        
        # 从列表中移除对话
        conversations = [c for c in conversations if c['id'] != conversation_id]
        
        if len(conversations) < original_count:
            # 保存更新后的列表
            save_user_conversations(user_id, conversations)
            
            # 删除对话历史文件
            try:
                history_file = os.path.join(CONVERSATION_HISTORY_DIR, f"{conversation_id}.json")
                if os.path.exists(history_file):
                    os.remove(history_file)
            except Exception as e:
                log_info("删除对话历史文件失败", {"conversation_id": conversation_id, "error": str(e)})
            
            return True
        
        return False
    except Exception as e:
        log_info("删除对话失败", {"conversation_id": conversation_id, "error": str(e)})
        return False

def get_conversation_history(conversation_id):
    """获取指定对话的聊天历史"""
    try:
        ensure_directories()
        history_file = os.path.join(CONVERSATION_HISTORY_DIR, f"{conversation_id}.json")
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return history if isinstance(history, list) else []
        return []
    except Exception as e:
        log_info("获取对话历史失败", {"conversation_id": conversation_id, "error": str(e)})
        return []

def save_conversation_history(conversation_id, history):
    """保存指定对话的聊天历史"""
    try:
        ensure_directories()
        history_file = os.path.join(CONVERSATION_HISTORY_DIR, f"{conversation_id}.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        log_info("保存对话历史", {
            "conversation_id": conversation_id,
            "message_count": len(history)
        })
        
        return True
    except Exception as e:
        log_info("保存对话历史失败", {"conversation_id": conversation_id, "error": str(e)})
        return False

def clear_conversation_history(conversation_id):
    """清空指定对话的聊天历史"""
    try:
        return save_conversation_history(conversation_id, [])
    except Exception as e:
        log_info("清空对话历史失败", {"conversation_id": conversation_id, "error": str(e)})
        return False 