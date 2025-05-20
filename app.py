from flask import Flask, render_template, jsonify, request, Response
from flask_apscheduler import APScheduler
import cv2
import numpy as np
import time
from collections import Counter
from keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array
from volcenginesdkarkruntime import Ark

app = Flask(__name__)

class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# 初始化豆包客户端
client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="74f17031-2a96-4740-8eef-014c208bc6ba"
)

# 全局状态
face_classifier = cv2.CascadeClassifier('HaarcascadeclassifierCascadeClassifier.xml')
classifier = load_model('model.h5')
emotion_labels = ['Angry', 'Disgust', 'Fear', 'Happy', 'Neutral', 'Sad', 'Surprise']

latest_emotion_counts = {}
latest_dominant_emotion = None
chatting = False  # 是否正在聊天状态
chat_sessions = {}  # 保存多轮对话上下文


def recognize_emotions_for_duration(duration=10):
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    start_time = time.time()
    emotions = []

    while time.time() - start_time < duration:
        ret, frame = cap.read()
        if not ret:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_classifier.detectMultiScale(gray)

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y + h, x:x + w]
            roi_gray = cv2.resize(roi_gray, (48, 48), interpolation=cv2.INTER_AREA)

            if np.sum([roi_gray]) != 0:
                roi = roi_gray.astype('float') / 255.0
                roi = img_to_array(roi)
                roi = np.expand_dims(roi, axis=0)

                prediction = classifier.predict(roi, verbose=0)[0]
                label = emotion_labels[prediction.argmax()]
                emotions.append(label)

    cap.release()
    return emotions


def auto_start_chat_based_on_emotion(emotion, user_id="default_user"):
    session_id = f"{user_id}_session"
    prompt = f"你是一个学习陪伴机器人咚咚。用户当前的情绪是“{emotion}”，请你先说一句温柔的、安慰她或引导她的话。"

    chat_sessions[session_id] = [
        {"role": "system", "content": "你是一个中文的温柔学习陪伴机器人"},
        {"role": "user", "content": prompt}
    ]

    try:
        completion = client.chat.completions.create(
            model="doubao-1-5-pro-32k-250115",
            messages=chat_sessions[session_id],
            stream=False,
        )
        bot_reply = completion.choices[0].message.content
        chat_sessions[session_id].append({"role": "assistant", "content": bot_reply})
        print(f"[豆包主动发言]：{bot_reply}")

    except Exception as e:
        print(f"[豆包调用失败] {e}")


@scheduler.task('interval', id='scheduled_emotion_recognition', seconds=20, max_instances=1)
def scheduled_emotion_recognition():
    global latest_emotion_counts, latest_dominant_emotion, chatting

    if chatting:
        print("跳过情绪识别（正在聊天）")
        return

    emotions = recognize_emotions_for_duration()
    if not emotions:
        print("未检测到情绪")
        latest_dominant_emotion = None
        return

    counts = Counter(emotions)
    latest_emotion_counts = dict(counts)
    total = sum(counts.values())
    neutral_count = counts.get('Neutral', 0)

    if neutral_count / total > 0.5:
        print("主要是 Neutral，跳过弹窗")
        latest_dominant_emotion = 'Neutral'
    else:
        counts.pop('Neutral', None)
        dominant = counts.most_common(1)[0][0]
        latest_dominant_emotion = dominant
        print(f"触发弹窗：你看起来有些 {dominant}")
        auto_start_chat_based_on_emotion(dominant)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/get_popup_emotion')
def get_popup_emotion():
    return jsonify({'emotion': latest_dominant_emotion})


@app.route('/start_chat')
def start_chat():
    global chatting
    chatting = True
    print("已进入聊天状态，暂停情绪识别与弹窗")
    return jsonify({'status': 'ok'})


@app.route('/end_chat')
def end_chat():
    global chatting
    chatting = False
    print("聊天结束，恢复情绪识别")
    return jsonify({'status': 'ok'})


@app.route('/is_chatting')
def is_chatting():
    global chatting
    return jsonify({'chatting': chatting})


@app.route('/get_chat_history')
def get_chat_history():
    user_id = request.args.get("user_id", "default_user")
    session_id = f"{user_id}_session"
    messages = chat_sessions.get(session_id, [])
    return jsonify(messages)


@app.route('/chat_stream')
def chat_stream():
    global latest_dominant_emotion

    user_id = request.args.get("user_id", "default_user")
    query = request.args.get("q", "").strip()
    if not query:
        return Response("data: [错误] 用户输入为空\n\n", mimetype='text/event-stream')

    session_id = f"{user_id}_session"
    if session_id not in chat_sessions:
        system_prompt = f"你是一个学习陪伴聊天机器人咚咚，目前用户的情绪是{latest_dominant_emotion or '未知'}，请你用中文友好温柔地跟她聊天。"
        chat_sessions[session_id] = [{"role": "system", "content": system_prompt}]

    chat_sessions[session_id].append({"role": "user", "content": query})

    def generate():
        try:
            stream = client.chat.completions.create(
                model="doubao-1-5-pro-32k-250115",
                messages=chat_sessions[session_id],
                stream=True,
            )

            reply = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta.content
                    reply += delta
                    yield f"data: {delta}\n\n"

            chat_sessions[session_id].append({"role": "assistant", "content": reply})

        except Exception as e:
            yield f"data: [错误] {str(e)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(debug=False)
