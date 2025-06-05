"""
对话管理API模块 - 提供多对话管理功能
"""
from flask import Blueprint, request, jsonify
import uuid
import traceback
from datetime import datetime
from utils.logger import log_info
from modules.conversation_manager import (
    create_conversation, get_user_conversations, get_conversation,
    update_conversation, delete_conversation, get_conversation_history,
    save_conversation_history, clear_conversation_history
)
from api.auth_api import get_current_user, require_auth

# 创建蓝图
conversation_api = Blueprint('conversation_api', __name__)

@conversation_api.route("/conversations", methods=["GET"])
@require_auth
def get_conversations():
    """
    获取用户的所有对话
    
    返回:
        JSON: 包含对话列表的JSON对象
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "用户未登录"}), 401
        
        conversations = get_user_conversations(user['user_id'])
        
        log_info("获取对话列表", {
            "user_id": user['user_id'],
            "conversation_count": len(conversations)
        })
        
        return jsonify({
            "success": True,
            "conversations": conversations
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("获取对话列表失败", {"error": str(e), "details": error_details})
        return jsonify({
            "success": False,
            "error": "获取对话列表失败",
            "conversations": []
        }), 500

@conversation_api.route("/conversations", methods=["POST"])
@require_auth
def create_new_conversation():
    """
    创建新对话
    
    返回:
        JSON: 操作结果和新创建的对话信息
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "用户未登录"}), 401
        
        # 处理可能为空的请求体
        try:
            data = request.get_json() or {}
        except Exception:
            data = {}
        
        title = data.get('title', f'新对话 {datetime.now().strftime("%m-%d %H:%M")}')
        
        conversation = create_conversation(user['user_id'], title)
        
        log_info("创建新对话", {
            "user_id": user['user_id'],
            "conversation_id": conversation['id'],
            "title": title
        })
        
        return jsonify({
            "success": True,
            "conversation": conversation
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("创建新对话失败", {"error": str(e), "details": error_details})
        return jsonify({
            "success": False,
            "error": "创建新对话失败"
        }), 500

@conversation_api.route("/conversations/<conversation_id>", methods=["GET"])
@require_auth
def get_conversation_info(conversation_id):
    """
    获取指定对话的信息
    
    参数:
        conversation_id: 对话ID
        
    返回:
        JSON: 对话信息
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "用户未登录"}), 401
        
        conversation = get_conversation(conversation_id, user['user_id'])
        
        if not conversation:
            return jsonify({
                "success": False,
                "error": "对话不存在或无权访问"
            }), 404
        
        return jsonify({
            "success": True,
            "conversation": conversation
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("获取对话信息失败", {"error": str(e), "details": error_details})
        return jsonify({
            "success": False,
            "error": "获取对话信息失败"
        }), 500

@conversation_api.route("/conversations/<conversation_id>", methods=["PUT"])
@require_auth
def update_conversation_info(conversation_id):
    """
    更新对话信息（如标题）
    
    参数:
        conversation_id: 对话ID
        
    返回:
        JSON: 操作结果
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "用户未登录"}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求数据为空"}), 400
        
        title = data.get('title', '').strip()
        if not title:
            return jsonify({"success": False, "error": "标题不能为空"}), 400
        
        success = update_conversation(conversation_id, user['user_id'], title=title)
        
        if not success:
            return jsonify({
                "success": False,
                "error": "对话不存在或无权访问"
            }), 404
        
        log_info("更新对话信息", {
            "user_id": user['user_id'],
            "conversation_id": conversation_id,
            "new_title": title
        })
        
        return jsonify({
            "success": True,
            "message": "对话信息已更新"
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("更新对话信息失败", {"error": str(e), "details": error_details})
        return jsonify({
            "success": False,
            "error": "更新对话信息失败"
        }), 500

@conversation_api.route("/conversations/<conversation_id>", methods=["DELETE"])
@require_auth
def delete_conversation_endpoint(conversation_id):
    """
    删除指定对话
    
    参数:
        conversation_id: 对话ID
        
    返回:
        JSON: 操作结果
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "用户未登录"}), 401
        
        success = delete_conversation(conversation_id, user['user_id'])
        
        if not success:
            return jsonify({
                "success": False,
                "error": "对话不存在或无权访问"
            }), 404
        
        log_info("删除对话", {
            "user_id": user['user_id'],
            "conversation_id": conversation_id
        })
        
        return jsonify({
            "success": True,
            "message": "对话已删除"
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("删除对话失败", {"error": str(e), "details": error_details})
        return jsonify({
            "success": False,
            "error": "删除对话失败"
        }), 500

@conversation_api.route("/conversations/<conversation_id>/history", methods=["GET"])
@require_auth
def get_conversation_history_endpoint(conversation_id):
    """
    获取指定对话的聊天历史
    
    参数:
        conversation_id: 对话ID
        
    返回:
        JSON: 聊天历史
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "用户未登录"}), 401
        
        # 验证对话归属
        conversation = get_conversation(conversation_id, user['user_id'])
        if not conversation:
            return jsonify({
                "success": False,
                "error": "对话不存在或无权访问"
            }), 404
        
        history = get_conversation_history(conversation_id)
        
        log_info("获取对话历史", {
            "user_id": user['user_id'],
            "conversation_id": conversation_id,
            "message_count": len(history)
        })
        
        return jsonify({
            "success": True,
            "history": history,
            "conversation": conversation
        })
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("获取对话历史失败", {"error": str(e), "details": error_details})
        return jsonify({
            "success": False,
            "error": "获取对话历史失败",
            "history": []
        }), 500

@conversation_api.route("/conversations/<conversation_id>/clear", methods=["POST"])
@require_auth
def clear_conversation_history_endpoint(conversation_id):
    """
    清空指定对话的聊天历史
    
    参数:
        conversation_id: 对话ID
        
    返回:
        JSON: 操作结果
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "error": "用户未登录"}), 401
        
        # 验证对话归属
        conversation = get_conversation(conversation_id, user['user_id'])
        if not conversation:
            return jsonify({
                "success": False,
                "error": "对话不存在或无权访问"
            }), 404
        
        success = clear_conversation_history(conversation_id)
        
        log_info("清空对话历史", {
            "user_id": user['user_id'],
            "conversation_id": conversation_id,
            "success": success
        })
        
        if success:
            return jsonify({
                "success": True,
                "message": "对话历史已清空"
            })
        else:
            return jsonify({
                "success": False,
                "error": "清空对话历史失败"
            }), 500
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_info("清空对话历史失败", {"error": str(e), "details": error_details})
        return jsonify({
            "success": False,
            "error": "清空对话历史失败"
        }), 500 