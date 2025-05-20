import sys
import requests
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

class FloatingEmotionBubble(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(240, 180)
        self.move_to_corner()

        # 表情图标
        self.label = QLabel("🤖", self)
        self.label.setStyleSheet("color: #444; background: transparent;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Arial", 48))
        self.label.setGeometry(45, 30, 150, 150)

        # 气泡文本
        self.bubble = QLabel("", self)
        self.bubble.setStyleSheet("""
            QLabel {
                background-color: #fff8f0;
                color: #444;
                border: 2px solid #f4c27a;
                border-radius: 12px;
                padding: 6px 10px;
            }
        """)
        self.bubble.setFont(QFont("Arial", 10))
        self.bubble.setWordWrap(True)
        self.bubble.setFixedWidth(200)
        self.bubble.hide()

        self.bubble_timer = QTimer()
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.hide_bubble)

        self.setMouseTracking(True)
        self.old_pos = None
        self.current_emotion = None
        self.chatting = False  # 新增聊天状态标志

        # 轮询聊天状态（每5秒）
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_chat_status)
        self.status_timer.start(5000)

        # 情绪轮询（每20秒）
        self.emotion_timer = QTimer()
        self.emotion_timer.timeout.connect(self.check_emotion)
        self.emotion_timer.start(20000)

    def move_to_corner(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 260, screen.height() - 200)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def show_bubble(self, text):
        self.bubble.setText(text)
        self.bubble.adjustSize()
        bubble_x = (self.width() - self.bubble.width()) // 2
        bubble_y = max(10, self.label.y() - self.bubble.height() - 10)
        self.bubble.move(bubble_x, bubble_y)
        self.bubble.show()
        self.bubble.raise_()
        self.bubble_timer.start(10000)

    def hide_bubble(self):
        self.bubble.hide()

    def emotion_to_emoji(self, emotion):
        return {
            'Angry': '😠', 'Disgust': '🤢', 'Fear': '😨',
            'Happy': '😊', 'Neutral': '🤖', 'Sad': '😢',
            'Surprise': '😲'
        }.get(emotion, '🤖')

    def check_chat_status(self):
        try:
            res = requests.get("http://127.0.0.1:5000/is_chatting", timeout=3)
            self.chatting = res.json().get("chatting", False)
        except Exception as e:
            print("聊天状态检查失败：", e)
            self.chatting = False  # 默认恢复检测

    def check_emotion(self):
        if self.chatting:
            return  # 聊天时完全静默

        try:
            res = requests.get("http://127.0.0.1:5000/get_popup_emotion", timeout=5)
            data = res.json()
            emotion = data.get("emotion")
            if emotion :
                self.current_emotion = emotion
                if emotion != "Neutral":
                    emoji = self.emotion_to_emoji(emotion)
                    self.label.setText(emoji)
                    self.setToolTip(f"你看起来有些 {emotion}，快来聊一聊吧！")
                    self.show_bubble(f"你看起来有些 {emotion}，快来聊一聊吧！")
                else:
                    self.label.setText('🤖')
                    self.setToolTip("咚咚一直都在！")
                    self.show_bubble("咚咚一直都在！")
        except Exception as e:
            print("连接后端失败：", e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    bubble = FloatingEmotionBubble()
    bubble.show()
    sys.exit(app.exec())
