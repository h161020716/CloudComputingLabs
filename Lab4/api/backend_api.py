"""
后端管理API模块 - 提供用户级后端管理相关的API端点
"""
from flask import Blueprint, request, jsonify
from modules.user_backend_manager import (
    get_user_backends, 
    get_user_backend, 
    add_user_backend, 
    update_user_backend, 
    delete_user_backend,
    init_user_backends
)
from api.auth_api import get_current_user, require_auth
from utils.logger import log_info

# 创建蓝图
backend_api = Blueprint('backend_api', __name__)

@backend_api.route("/backends", methods=["GET"])
@require_auth
def list_backends():
    """
    获取当前用户的后端配置列表
    
    返回:
        JSON: 包含用户后端配置信息的JSON对象
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "用户未登录"}), 401
        
        user_id = user['user_id']
        backends = get_user_backends(user_id)
        backend_list = []
        
        # 格式化返回数据
        for idx, backend in enumerate(backends):
            backend_info = {
                "id": idx,
                "base_url": backend["base_url"],
                "model": backend.get("model", ""),
                "api_key": backend.get("api_key", ""),
                "weight": backend["weight"],
                "status": backend["status"],
                "failures": backend.get("failures", 0),
                "last_check": backend.get("last_check", 0)
            }
            backend_list.append(backend_info)
        
        log_info("获取用户后端列表", {"user_id": user_id, "count": len(backend_list)})
        return jsonify({"backends": backend_list})
    except Exception as e:
        log_info("获取用户后端列表失败", {"error": str(e)})
        return jsonify({"error": str(e)}), 500

@backend_api.route("/backends", methods=["POST"])
@require_auth
def create_backend():
    """
    为当前用户创建新后端配置
    
    请求体:
        base_url (str): 后端基础URL
        model (str): 模型名称
        api_key (str): API密钥
        weight (int): 权重，默认为1
        
    返回:
        JSON: 操作结果
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "用户未登录"}), 401
        
        user_id = user['user_id']
        data = request.get_json()
        base_url = data.get("base_url", "").strip()
        model = data.get("model", "").strip()
        api_key = data.get("api_key", "ollama").strip()
        weight = data.get("weight", 1)
        
        if not base_url:
            return jsonify({"error": "基础URL不能为空"}), 400
        
        if not model:
            return jsonify({"error": "模型名称不能为空"}), 400
            
        success, message = add_user_backend(
            user_id=user_id, 
            base_url=base_url, 
            model=model, 
            api_key=api_key, 
            weight=weight
        )
        
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"error": message}), 400
    except Exception as e:
        log_info("为用户添加后端失败", {"user_id": user.get('user_id') if 'user' in locals() else 'unknown', "error": str(e)})
        return jsonify({"error": str(e)}), 500

@backend_api.route("/backends/<backend_id>", methods=["PUT"])
@require_auth
def update_backend_handler(backend_id):
    """
    更新当前用户的后端配置信息
    
    参数:
        backend_id (str): 后端ID
        
    请求体:
        base_url (str, optional): 更新的基础URL
        model (str, optional): 更新的模型名称
        api_key (str, optional): 更新的API密钥
        weight (int, optional): 更新的权重
        status (str, optional): 更新的状态
        reset_failures (bool, optional): 是否重置故障计数
        
    返回:
        JSON: 操作结果
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "用户未登录"}), 401
        
        user_id = user['user_id']
        data = request.get_json()
        
        success, message = update_user_backend(user_id, backend_id, data)
        
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"error": message}), 400
    except Exception as e:
        log_info("更新用户后端失败", {"user_id": user.get('user_id') if 'user' in locals() else 'unknown', "error": str(e), "backend_id": backend_id})
        return jsonify({"error": str(e)}), 500

@backend_api.route("/backends/<backend_id>", methods=["DELETE"])
@require_auth
def delete_backend_handler(backend_id):
    """
    删除当前用户的后端配置
    
    参数:
        backend_id (str): 后端ID
        
    返回:
        JSON: 操作结果
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({"error": "用户未登录"}), 401
        
        user_id = user['user_id']
        success, message = delete_user_backend(user_id, backend_id)
        
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"error": message}), 400
    except Exception as e:
        log_info("删除用户后端失败", {"user_id": user.get('user_id') if 'user' in locals() else 'unknown', "error": str(e), "backend_id": backend_id})
        return jsonify({"error": str(e)}), 500 