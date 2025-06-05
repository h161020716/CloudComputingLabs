"""
聊天API模块 - 提供聊天相关的API端点
"""
from flask import Blueprint, request, jsonify
import traceback
import time
import threading
from utils.logger import log_info
from modules.conversation_manager import (
    get_conversation_history, save_conversation_history, 
    get_conversation, update_conversation
)
from modules.llm_client import create_client
from modules.user_backend_manager import get_user_available_backend
from api.auth_api import get_current_user, require_auth
from config import DEFAULT_MODEL

# 创建蓝图
chat_api = Blueprint('chat_api', __name__)

# 请求超时时间（秒）
REQUEST_TIMEOUT = 120  # 2分钟

def get_client_id():
    """
    获取客户端唯一标识，优先使用用户ID
    
    返回:
        str: 用户ID或IP标识
    """
    # 优先使用登录用户的ID
    user = get_current_user()
    if user:
        return f"user_{user['user_id']}"
    
    # 未登录用户使用IP标识
    client_ip = request.remote_addr
    print(client_ip)
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        client_ip = request.environ['HTTP_X_FORWARDED_FOR']
    
    # 简单的哈希处理，避免直接使用IP
    client_id = f"guest_{hash(client_ip) % 10000:04d}"
    return client_id

class TimeoutError(Exception):
    """请求超时异常"""
    pass

def call_with_timeout(func, timeout, *args, **kwargs):
    """
    使用超时执行函数
    
    参数:
        func: 要执行的函数
        timeout: 超时时间（秒）
        args, kwargs: 传递给函数的参数
        
    返回:
        函数的返回值
        
    异常:
        TimeoutError: 如果函数执行超时
    """
    result = [None]
    exception = [None]
    completed = [False]
    
    def worker():
        try:
            result[0] = func(*args, **kwargs)
            completed[0] = True
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    
    thread.join(timeout)
    
    if not completed[0]:
        if exception[0]:
            raise exception[0]
        raise TimeoutError(f"操作超时（{timeout}秒）")
    
    if exception[0]:
        raise exception[0]
        
    return result[0]

@chat_api.route("/chat_history", methods=["GET"])
@require_auth
def get_user_chat_history():
    """
    获取用户的聊天历史（兼容旧版本）
    
    返回:
        JSON: 包含聊天历史的JSON对象
    """
    try:
        # 获取当前用户的客户端ID
        client_id = get_client_id()
        
        # 返回空历史，引导用户使用新的多对话功能
        log_info("获取聊天历史（旧版本兼容）", {
            "client_id": client_id
        })
        
        return jsonify({
            "history": [],
            "client_id": client_id,
            "message_count": 0,
            "note": "请使用新的多对话功能"
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("获取聊天历史失败", {"error": str(e), "details": error_details})
        return jsonify({
            "error": "获取聊天历史失败",
            "history": []
        }), 500

@chat_api.route("/clear_history", methods=["POST"])
@require_auth
def clear_user_chat_history():
    """
    清空用户的聊天历史（兼容旧版本）
    
    返回:
        JSON: 操作结果
    """
    try:
        return jsonify({
            "success": True,
            "message": "请使用新的多对话功能管理聊天历史"
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("清空聊天历史失败", {"error": str(e), "details": error_details})
        return jsonify({
            "error": "清空聊天历史失败",
            "success": False
        }), 500

@chat_api.route("/chat", methods=["POST"])
@require_auth
def chat():
    """
    处理聊天请求
    
    请求体:
        message (str): 用户消息
        conversation_id (str): 对话ID
        
    返回:
        JSON: 包含模型回复的JSON对象
    """
    try:
        # 获取请求数据
        data = request.get_json()
        user_message = data.get('message', '')
        conversation_id = data.get('conversation_id')
        
        if not user_message.strip():
            return jsonify({"error": "消息不能为空"}), 400
        
        if not conversation_id:
            return jsonify({"error": "对话ID不能为空"}), 400
        
        # 获取当前用户
        user = get_current_user()
        if not user:
            return jsonify({"error": "用户未登录"}), 401
        
        # 验证对话归属
        conversation = get_conversation(conversation_id, user['user_id'])
        if not conversation:
            return jsonify({"error": "对话不存在或无权访问"}), 404
        
        # 获取对话历史
        messages = get_conversation_history(conversation_id)
        print(f"加载历史消息 - 对话: {conversation_id}, 消息数量:", len(messages))
        
        # 确保历史是列表格式
        if not isinstance(messages, list):
            log_info("历史格式异常，重置为空列表", {"conversation_id": conversation_id, "type": type(messages)})
            messages = []
        
        # 添加用户消息
        user_msg = {"role": "user", "content": user_message}
        messages.append(user_msg)
        
        # 立即保存用户消息
        save_success = save_conversation_history(conversation_id, messages)
        log_info("保存用户消息", {"conversation_id": conversation_id, "success": save_success, "message_count": len(messages)})
        
        # 记录用户请求
        log_info("用户发送消息", {"conversation_id": conversation_id, "message": user_message})
        
        # 获取用户的可用后端
        backend = get_user_available_backend(user['user_id'])
        if not backend:
            return jsonify({"error": "您还没有配置可用的语言模型后端，请先在后端管理中添加", "no_backend": True}), 503
        
        # 获取后端ID
        backend_id = backend.get("backend_id")
        
        # 创建LLM客户端
        llm_client = create_client(backend)
        
        try:
            # 使用超时调用LLM API
            start_time = time.time()
            model_name = backend.get("model", DEFAULT_MODEL)
            
            # 带超时的模型调用
            assistant_response = call_with_timeout(
                llm_client.chat, 
                REQUEST_TIMEOUT, 
                messages, 
                model=model_name
            )
            
            # 记录请求耗时
            elapsed_time = time.time() - start_time
            log_info("模型响应完成", {"conversation_id": conversation_id, "耗时": f"{elapsed_time:.2f}秒"})
            
            # 添加助手回复到历史记录
            assistant_msg = {"role": "assistant", "content": assistant_response}
            messages.append(assistant_msg)
            
            # 保存完整的对话历史
            save_success = save_conversation_history(conversation_id, messages)
            
            # 更新对话信息（消息数量和更新时间）
            update_conversation(conversation_id, user['user_id'], message_count=len(messages))
            
            log_info("保存完整对话历史", {
                "conversation_id": conversation_id, 
                "success": save_success, 
                "total_messages": len(messages)
            })
            
            # 返回响应
            return jsonify({
                "message": {
                    "role": "assistant",
                    "content": assistant_response
                },
                "model": model_name,
                "backend_id": backend_id,
                "conversation_id": conversation_id,
                "reply": assistant_response,  # 兼容旧版前端
                "save_success": save_success  # 指示历史保存是否成功
            })
            
        except TimeoutError:
            # 请求超时处理
            timeout_message = f"请求处理超时（超过{REQUEST_TIMEOUT}秒）。请尝试简化您的问题或稍后再试。"
            log_info("请求超时", {"conversation_id": conversation_id, "backend_id": backend_id})
            
            # 添加超时消息到历史记录
            timeout_msg = {"role": "system", "content": timeout_message}
            messages.append(timeout_msg)
            save_conversation_history(conversation_id, messages)
            
            return jsonify({
                "error": timeout_message,
                "timeout": True,
                "backend_id": backend_id,
                "conversation_id": conversation_id
            }), 504  # Gateway Timeout
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("聊天请求处理错误", {"error": str(e), "details": error_details})
        return jsonify({"error": str(e)}), 500

