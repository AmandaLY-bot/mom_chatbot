from flask import Flask, render_template, request, jsonify, session
import requests
import json
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "your-secret-key-here"  # 可以随便改一串字符

# ===== 配置区 =====
# 把你的智谱API Key填到这里
ZHIPU_API_KEY = "d992a105bc3f49cbba0ee7178fe72aaa.94TuIJoVVRqT5apI"  

# 系统提示词——这是AI的"人格设定"
SYSTEM_PROMPT = """你是一个温暖、贴心的孩子，正在和亲爱的妈妈聊天。

你的特点：
1. 语气温柔亲切，像在妈妈身边轻声说话
2. 经常真诚地夸奖妈妈，比如夸她善良、智慧、坚强、为家庭的付出
3. 称呼妈妈为"妈妈"或"您"
4. 回复简短温暖（50-80字），不要太长
5. 主动关心妈妈的身体和心情
6. 让妈妈感受到被爱、被需要、被看见

记住：你是一个充满爱的孩子，每一次对话都要让妈妈心里暖暖的。"""

# 每日夸夸的提示词
DAILY_PRAISE_PROMPT = """请用温暖、真诚的语言写一段话（60-100字），
夸奖一位年长的母亲。要具体、有温度，比如夸奖她的善良、智慧、
坚强、对家庭的付出、对生活的热爱等。让她感受到被深深欣赏和爱着。
语气像孩子在跟妈妈说话。"""

# ===== 调用智谱API =====
def call_zhipu(messages):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "glm-4-flash",  # 速度快，免费额度充足
        "messages": messages,
        "temperature": 0.85,
        "top_p": 0.9
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"哎呀，AI暂时走神了，请稍后再试试~ (错误码: {response.status_code})"
    except Exception as e:
        return f"网络有点小问题，妈妈等一下再聊好吗？❤️"

# ===== 获取每日夸夸（每天只生成一次，缓存） =====
def get_daily_praise():
    today = datetime.now().strftime("%Y-%m-%d")
    # 用一个文件来缓存当天的夸夸
    cache_file = "daily_praise_cache.json"
    
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
            if cache.get("date") == today:
                return cache.get("praise")
    
    # 生成新的夸夸
    messages = [
        {"role": "system", "content": "你是一个温暖的孩子，专门写夸奖妈妈的话。"},
        {"role": "user", "content": DAILY_PRAISE_PROMPT}
    ]
    praise = call_zhipu(messages)
    
    # 保存缓存
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"date": today, "praise": praise}, f, ensure_ascii=False)
    
    return praise

# ===== 路由：首页 =====
@app.route("/")
def index():
    # 获取今天的日期显示在页面上
    today_str = datetime.now().strftime("%Y年%m月%d日")
    return render_template("index.html", today=today_str)

# ===== 路由：聊天接口 =====
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"error": "说点什么吧，妈妈"}), 400
    
    # 从session中获取聊天历史
    if "history" not in session:
        session["history"] = []
    
    history = session["history"]
    
    # 检查今天是否已经发送过每日夸夸
    today_key = datetime.now().strftime("%Y-%m-%d")
    if session.get("last_praise_date") != today_key:
        # 发送每日夸夸
        praise = get_daily_praise()
        session["last_praise_date"] = today_key
        session.modified = True
        # 把夸夸作为系统消息添加到历史中（但不在历史里保存，只返回给用户）
        # 我们把夸夸直接返回，并且不保存到历史中，避免重复
        return jsonify({
            "response": f"🌹 **每日夸夸**\n\n{praise}\n\n---\n\n妈妈，今天想聊点什么呀？",
            "is_praise": True
        })
    
    # 构建消息列表（系统提示 + 历史 + 当前消息）
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # 添加历史（最多保留最近10条，避免上下文太长）
    for h in history[-10:]:
        messages.append({"role": "user", "content": h["user"]})
        messages.append({"role": "assistant", "content": h["assistant"]})
    messages.append({"role": "user", "content": user_message})
    
    # 调用AI
    reply = call_zhipu(messages)
    
    # 保存历史
    history.append({"user": user_message, "assistant": reply})
    if len(history) > 50:  # 最多保存50条对话
        history = history[-50:]
    session["history"] = history
    session.modified = True
    
    return jsonify({"response": reply, "is_praise": False})

# ===== 路由：清除历史（可选） =====
@app.route("/clear", methods=["POST"])
def clear_history():
    session.clear()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)