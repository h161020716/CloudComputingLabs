"""
用户认证API模块 - 提供用户注册、登录、登出等功能
"""
from flask import Blueprint, request, jsonify, make_response, render_template
from modules.user_manager import (
    register_user, authenticate_user, create_session, 
    validate_session, logout_user, get_user_stats
)
from utils.logger import log_info

# 创建蓝图
auth_api = Blueprint('auth_api', __name__)

@auth_api.route("/register", methods=["GET", "POST"])
def register():
    """用户注册"""
    if request.method == "GET":
        return render_template("register.html")
    
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        email = data.get('email', '').strip()
        display_name = data.get('display_name', '').strip()
        
        # 注册用户
        result = register_user(username, password, email, display_name)
        
        if result["success"]:
            log_info("用户注册", {"username": username, "result": "成功"})
            return jsonify(result), 200
        else:
            log_info("用户注册", {"username": username, "result": "失败", "reason": result["message"]})
            return jsonify(result), 400
            
    except Exception as e:
        log_info("注册请求异常", {"error": str(e)})
        return jsonify({"success": False, "message": "注册请求处理失败"}), 500

@auth_api.route("/login", methods=["GET", "POST"])
def login():
    """用户登录"""
    if request.method == "GET":
        return render_template("login.html")
    
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # 验证用户
        auth_result = authenticate_user(username, password)
        
        if auth_result["success"]:
            # 创建会话
            user = auth_result["user"]
            session_token = create_session(user["user_id"], user["username"])
            
            # 创建响应
            response_data = {
                "success": True,
                "message": "登录成功",
                "user": user,
                "session_token": session_token
            }
            
            response = make_response(jsonify(response_data))
            
            # 设置HttpOnly Cookie（更安全）
            response.set_cookie(
                'session_token', 
                session_token,
                max_age=7*24*60*60,  # 7天
                httponly=True,
                secure=False,  # 开发环境设为False，生产环境应设为True
                samesite='Lax'
            )
            
            log_info("用户登录", {"username": username, "result": "成功"})
            return response
        else:
            log_info("用户登录", {"username": username, "result": "失败", "reason": auth_result["message"]})
            return jsonify(auth_result), 401
            
    except Exception as e:
        log_info("登录请求异常", {"error": str(e)})
        return jsonify({"success": False, "message": "登录请求处理失败"}), 500

@auth_api.route("/logout", methods=["POST"])
def logout():
    """用户登出"""
    try:
        # 从Cookie或请求头获取session token
        session_token = request.cookies.get('session_token')
        if not session_token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_token = auth_header[7:]
        
        if session_token:
            logout_result = logout_user(session_token)
            if logout_result:
                response = make_response(jsonify({"success": True, "message": "登出成功"}))
                response.set_cookie('session_token', '', expires=0)  # 清除Cookie
                return response
        
        return jsonify({"success": True, "message": "登出成功"}), 200
        
    except Exception as e:
        log_info("登出请求异常", {"error": str(e)})
        return jsonify({"success": False, "message": "登出请求处理失败"}), 500

@auth_api.route("/profile", methods=["GET"])
def profile():
    """获取用户资料"""
    try:
        # 验证会话
        session_token = request.cookies.get('session_token')
        if not session_token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_token = auth_header[7:]
        
        if not session_token:
            return jsonify({"success": False, "message": "未登录"}), 401
        
        session_result = validate_session(session_token)
        if not session_result["valid"]:
            response = make_response(jsonify({"success": False, "message": "会话已过期"}))
            response.set_cookie('session_token', '', expires=0)  # 清除无效Cookie
            return response, 401
        
        return jsonify({
            "success": True, 
            "user": session_result["user"]
        }), 200
        
    except Exception as e:
        log_info("获取用户资料异常", {"error": str(e)})
        return jsonify({"success": False, "message": "获取用户资料失败"}), 500

@auth_api.route("/check-auth", methods=["GET"])
def check_auth():
    """检查用户认证状态"""
    try:
        # 验证会话
        session_token = request.cookies.get('session_token')
        if not session_token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_token = auth_header[7:]
        
        if not session_token:
            return jsonify({"authenticated": False}), 200
        
        session_result = validate_session(session_token)
        if session_result["valid"]:
            return jsonify({
                "authenticated": True,
                "user": session_result["user"]
            }), 200
        else:
            response = make_response(jsonify({"authenticated": False}))
            response.set_cookie('session_token', '', expires=0)  # 清除无效Cookie
            return response, 200
        
    except Exception as e:
        log_info("检查认证状态异常", {"error": str(e)})
        return jsonify({"authenticated": False}), 200

@auth_api.route("/stats", methods=["GET"])
def stats():
    """获取用户统计信息（可能需要管理员权限）"""
    try:
        stats_data = get_user_stats()
        return jsonify({
            "success": True,
            "stats": stats_data
        }), 200
        
    except Exception as e:
        log_info("获取用户统计异常", {"error": str(e)})
        return jsonify({"success": False, "message": "获取统计信息失败"}), 500

def get_current_user():
    """
    获取当前登录用户的信息
    这是一个工具函数，供其他模块使用
    
    返回:
        dict: 用户信息或None
    """
    try:
        # 验证会话
        session_token = request.cookies.get('session_token')
        if not session_token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                session_token = auth_header[7:]
        
        if not session_token:
            return None
        
        session_result = validate_session(session_token)
        return session_result["user"] if session_result["valid"] else None
        
    except:
        return None

def require_auth(f):
    """
    装饰器：要求用户认证
    用法: @require_auth
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"success": False, "message": "需要登录"}), 401
        
        # 将用户信息添加到request对象中
        request.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function 