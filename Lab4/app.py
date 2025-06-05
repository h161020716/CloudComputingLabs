"""
主应用文件 - 负载均衡聊天系统的入口点
"""
from flask import Flask, render_template, redirect, url_for, jsonify
from api.chat_api import chat_api, get_client_id
from api.backend_api import backend_api
from api.auth_api import auth_api, get_current_user, require_auth
from api.conversation_api import conversation_api
from modules.user_backend_manager import init_user_backends
from utils.init import initialize_app
from utils.logger import log_info, init_logger
from config import HOST, PORT, DEBUG

# 创建Flask应用
app = Flask(__name__)

# 注册蓝图
app.register_blueprint(chat_api, url_prefix='/api')
app.register_blueprint(backend_api, url_prefix='/api')
app.register_blueprint(conversation_api, url_prefix='/api')
app.register_blueprint(auth_api, url_prefix='')

# 主页路由
@app.route("/")
def chat():
    # 检查用户是否已登录
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_api.login'))
    
    # 初始化用户的后端配置（如果还没有）
    try:
        init_user_backends(user['user_id'])
    except Exception as e:
        log_info("初始化用户后端配置失败", {"user_id": user['user_id'], "error": str(e)})
    
    return render_template("chat.html")

# 获取客户端ID的API端点
@app.route("/client_id")
@require_auth
def client_id():
    """获取当前用户的客户端ID"""
    try:
        client_id = get_client_id()
        return jsonify({"client_id": client_id})
    except Exception as e:
        return jsonify({"error": str(e), "client_id": "未知"}), 500

if __name__ == "__main__":
    # 初始化日志系统
    init_logger()
    
    # 初始化应用
    initialize_app()
    
    # 启动Web服务器
    log_info("启动Web服务器", {"host": HOST, "port": PORT})
    app.run(debug=DEBUG, host=HOST, port=PORT) 