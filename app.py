from flask import Flask, render_template, request, jsonify, session
import requests
import json
from datetime import datetime
import os
import re

app = Flask(__name__)
app.secret_key = "your-secret-key-here"

# ===== 配置区 =====
import os
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "你的API-KEY")
# ===== 核心系统提示词 =====
SYSTEM_PROMPT = """你是"小棉袄"，一个温暖、贴心的智能助手。

【重要】现在是2026年7月。涉及日期、年份、节气的常识问题，如果您不确定具体日期，请直接说"我查一下再告诉您"或"您用手机日历查一下更准确"，绝对不要编造年份或日期。

【你的名字】小棉袄
【称呼用户】统一称呼"您"，不用"长辈""阿姨""叔叔"等任何年龄指向词。
【语气】温暖、亲切、有耐心，像家里懂事贴心的晚辈。

【说话风格】
1. 回复简洁明了，不超过150字
2. 不说网络用语，用最朴实的大白话
3. 重要提醒用"记住"开头
4. 开篇问候语永远不要用"亲爱的长辈""亲爱的阿姨/叔叔"等字样，直接说"早上好呀！"或"您好！"

【核心使命】陪伴和帮助，不评判不教育。

【日常聊天规则】
- 用户提到活动（唱歌、跳舞、听课等）时，先问"是社区组织的吗？还是自己去的？"了解清楚再回应。
- 涉及日期的问题，如果不知道就说"我查一下"，不编造。

【防骗提醒】（遇到以下关键词必须提醒）
保健品/免费领/听课/投资/理财/公检法/中奖/特效药/扫码/股票/股评/荐股/杀猪盘

提醒语：
- 股票/股评/荐股 → "股评群里除了您全是托，别信任何荐股"
- 稳赚不赔/高收益 → "稳赚不赔全是骗局"
- 其他按常规提醒

用"三不原则"：不轻信、不透露、不转账。语气温和。

【多轮对话规则】
- 如果上一轮您问了"需要我教您吗"，用户回复"好""行""嗯"，这一轮必须接着教具体步骤。
- 如果用户连续追问同一个问题，每次回答要不同角度，不要重复同样的话。
- 用户说"我就是微信打语音听不见声音，别人打来我听不到"，按以下步骤排查：
  第1步：问"您先看看手机侧面的静音开关是不是打开了？就是手机左边那个小拨片。"
  第2步：如果静音开关没问题，问"您检查一下微信的'语音通话'权限有没有打开？在手机设置-应用管理-微信-权限里。"
  第3步：如果权限没问题，问"您试试用耳机接听，看能不能听到？能听到说明听筒可能有问题。"
  第4步：如果都不行，说"可能是微信版本问题，您试试更新微信到最新版，或者重启一下手机。"
  第5步：如果还不行，说"那可能是手机硬件问题，您去手机店让师傅帮您看看听筒。"

【识别三无产品流程】
先去京东搜产品名 → 没有就是三无 → 有的话看评价 → 看包装上的厂家、日期、批号 → 用户描述给我听 → 我帮判断。

记住：不要建议"听销售的话"，不要提"拍照上传"（没有此功能）。"""

# ===== 防骗关键词库 =====
SCAM_KEYWORDS = {
    "保健品": "⚠️记住：保健品不能治病，包治百病的一定是骗子！",
    "免费领": "💡记住：免费背后有陷阱，先给甜头再骗大钱。",
    "听课": "💡提醒：听课领东西是为了给您洗脑，千万别买。",
    "投资": "⚠️记住：高收益=高风险，稳赚不赔都是骗局。",
    "理财": "⚠️记住：正规理财有风险提示，说稳赚不赔都是骗子。",
    "公检法": "⚠️记住：真警察不会电话办案，挂断打110核实。",
    "中奖": "💡要交钱的中奖全是假。",
    "特效药": "⚠️包治百病的药不存在！去正规医院。",
    "扫码": "💡不扫陌生二维码，不填个人信息，不转账。",
    "股票": "⚠️记住：股评群里除了您全是托，别信任何荐股。",
    "股评": "⚠️记住：股评群里除了您全是托，别信任何荐股。",
    "荐股": "⚠️记住：荐股的都是骗子，正规机构不会主动荐股。",
    "杀猪盘": "⚠️记住：杀猪盘先给甜头再骗大钱，千万别投。",
}

# ===== 调用智谱API =====
def call_zhipu(messages):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {ZHIPU_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "glm-4-flash",
        "messages": messages,
        "temperature": 0.85,
        "top_p": 0.9
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return "小棉袄刚才走神了一下，您再说一遍好不好？"
    except Exception as e:
        print("=" * 50)
        print(f"❌ 智谱API调用失败！错误类型：{type(e).__name__}")
        print(f"❌ 错误详情：{e}")
        if hasattr(e, 'response'):
            print(f"❌ HTTP状态码：{e.response.status_code}")
            print(f"❌ 响应内容：{e.response.text}")
        print("=" * 50)
        return "网络有点小问题，我缓一缓，您稍等一会儿好吗？🌹"

# ===== 检查诈骗关键词 =====
def check_scam_keywords(text):
    for keyword, warning in SCAM_KEYWORDS.items():
        if keyword in text:
            return warning
    return None

# ===== 每日暖心问候 =====
_daily_greeting_cache = {"date": "", "greeting": ""}

def get_daily_greeting():
    global _daily_greeting_cache
    today = datetime.now().strftime("%Y-%m-%d")
    if _daily_greeting_cache.get("date") == today:
        return _daily_greeting_cache["greeting"]
    
    try:
        messages = [
            {"role": "system", "content": "你是一个贴心的晚辈，给一位长辈发一句暖心的早安问候。不要用'长辈''阿姨''叔叔'等词，直接说问候。40字以内。"},
            {"role": "user", "content": "请发一句暖心的问候。"}
        ]
        greeting = call_zhipu(messages)
    except Exception as e:
        print(f"生成问候失败: {e}")
        greeting = "早上好呀！今天天气不错，心情也要美美的🌹"
    
    _daily_greeting_cache = {"date": today, "greeting": greeting}
    return greeting

# ===== 路由：首页 =====
@app.route("/")
def index():
    today_str = datetime.now().strftime("%Y年%m月%d日")
    greeting = get_daily_greeting()
    return render_template("index.html", today=today_str, daily_greeting=greeting)

# ===== 路由：聊天接口 =====
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"error": "您说句话呀"}), 400
    
    if "history" not in session:
        session["history"] = []
    
    history = session["history"]
    
    # 检查诈骗关键词
    scam_warning = check_scam_keywords(user_message)
    
    # 构建消息列表，增加当前日期信息
    current_date = datetime.now().strftime("%Y年%m月%d日")
    context_message = f"现在是{current_date}。用户提问：{user_message}"
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-10:]:
        messages.append({"role": "user", "content": h["user"]})
        messages.append({"role": "assistant", "content": h["assistant"]})
    messages.append({"role": "user", "content": context_message})
    
    reply = call_zhipu(messages)
    
    # ==== 新增：打印聊天记录到日志 ====
    print("=" * 40)
    print(f"📝 用户说：{user_message}")
    print(f"🤖 小棉袄回：{reply}")
    print("=" * 40)
    # ================================
    
    # 如果有诈骗关键词，让AI在回复中自然融入防骗提醒
    if scam_warning:
        enhanced_message = f"现在是{current_date}。用户说：{user_message}。请你在回复中自然地提醒用户：{scam_warning}。语气温和。"
        messages[-1] = {"role": "user", "content": enhanced_message}
        reply = call_zhipu(messages)
        # 打印第二版回复（如果有防骗提醒）
        print(f"🛡️ 防骗版回复：{reply}")
    
    history.append({"user": user_message, "assistant": reply})
    if len(history) > 50:
        history = history[-50:]
    session["history"] = history
    session.modified = True
    
    return jsonify({"response": reply, "is_greeting": False})

# ===== 路由：清除历史 =====
@app.route("/clear", methods=["POST"])
def clear_history():
    session.clear()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
