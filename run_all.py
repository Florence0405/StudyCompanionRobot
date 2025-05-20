import subprocess
import sys
import time
import threading
from PyQt6.QtWidgets import QApplication
from emotion_widget import FloatingEmotionBubble  # 你的小组件类

# 启动 Flask 应用的函数
def run_flask():
    subprocess.run([sys.executable, "app.py"])  # 确保路径正确

# 启动 PyQt 小组件的函数
def run_widget():
    app = QApplication(sys.argv)
    widget = FloatingEmotionBubble()
    widget.show()
    sys.exit(app.exec())

# 启动 Flask 在子线程中
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True  # 主线程退出时自动关闭
flask_thread.start()

# 等待 Flask 启动完毕（简单等待，也可以换成轮询检测）
time.sleep(2)

# 启动 PyQt 小组件
run_widget()
