import os
import time
import threading
import tkinter as tk
from datetime import datetime
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write

now_dir = os.path.dirname(os.path.abspath(__file__))
pre_model_dir = os.path.join(now_dir, "pretrained_models", "SenseVoiceSmall")


class SenseVoiceNode:
    def __init__(self) -> None:
        self.model = None
        self.save_dir = os.path.join(now_dir, "output")
        os.makedirs(self.save_dir, exist_ok=True)

        # 录音控制变量
        self.is_recording = False
        self.audio_data = []
        self.last_press_time = 0
        self.debounce_interval = 0.3  # 优化防抖时间

        # 音频流对象
        self.stream = None
        self.fs = 44100  # 固定采样率

    # 核心录音控制逻辑 --------------------------------------------------
    def start_recording(self):
        """优化的录音启动逻辑"""
        current_time = time.time()
        if (current_time - self.last_press_time) < self.debounce_interval:
            return

        if not self.is_recording:
            self.last_press_time = current_time
            self.is_recording = True
            self.audio_data = []
            print("🎤 录音开始...")

            # 启动音频流
            self.stream = sd.InputStream(
                samplerate=self.fs,
                channels=1,
                dtype='int16',
                blocksize=int(self.fs * 0.05),  # 更灵敏的中断响应
                callback=self.audio_callback
            )
            self.stream.start()

    def stop_recording(self):
        """即时停止录音并保存"""
        if self.is_recording:
            print("⏹ 正在停止录音...")
            self.is_recording = False

            # 关闭音频流
            if self.stream and self.stream.active:
                self.stream.stop()
                self.stream.close()

            # 保存录音
            if len(self.audio_data) > 0:
                self._save_recording()
            print("✅ 录音已保存")

    def audio_callback(self, indata, frames, time, status):
        """实时音频回调函数"""
        if self.is_recording:
            self.audio_data.append(indata.copy())

    # 文件保存逻辑 ------------------------------------------------------
    def _save_recording(self):
        """优化的音频保存方法"""
        try:
            print('开始保存音频数据...')
            full_recording = np.concatenate(self.audio_data, axis=0)

            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(
                self.save_dir,
                f"recording_{timestamp}.wav"
            )

            write(filename, self.fs, full_recording)
            print(f"💾 文件已保存到：{os.path.abspath(filename)}")
        except Exception as e:
            print(f"保存失败: {str(e)}")
        finally:
            self.audio_data.clear()

    # 用户界面相关 ------------------------------------------------------
    def start_record_session(self):
        """增强的录音控制界面"""
        root = tk.Tk()
        root.title("语音录制控制台 V2.0")
        root.geometry("300x220")  # 调整窗口大小
        root.configure(bg="#f0f0f0")

        # 增强的UI组件
        self._setup_enhanced_ui(root)
        root.mainloop()

    def _setup_enhanced_ui(self, root):
        """构建增强型界面"""
        # 状态指示灯
        self.status_label = tk.Label(
            root,
            text="●",
            font=("Arial", 32),
            fg="gray",
            bg="#f0f0f0"
        )
        self.status_label.pack(pady=15)

        # 实时波形可视化占位
        self.canvas = tk.Canvas(root, width=200, height=50, bg="white")
        self.canvas.pack()

        # 按钮容器
        btn_frame = tk.Frame(root, bg="#f0f0f0")
        btn_frame.pack(pady=15)

        # 开始按钮
        start_btn = tk.Button(
            btn_frame,
            text="开始录音",
            command=self.start_recording,
            width=10,
            height=2,
            bg="#4CAF50",
            fg="white",
            activebackground="#45a049"
        )
        start_btn.pack(side=tk.LEFT, padx=10)

        # 结束按钮
        stop_btn = tk.Button(
            btn_frame,
            text="结束录音",
            command=self.stop_recording,
            width=10,
            height=2,
            bg="#f44336",
            fg="white",
            activebackground="#da190b"
        )
        stop_btn.pack(side=tk.RIGHT, padx=10)

        # 状态更新定时器
        def update_ui():
            color = "red" if self.is_recording else "gray"
            self.status_label.config(fg=color)

            # 简单的波形动画
            if self.is_recording:
                self.canvas.delete("all")
                for i in range(5):
                    height = np.random.randint(10, 40)
                    self.canvas.create_rectangle(
                        i * 40, 25 - height / 2,
                        i * 40 + 20, 25 + height / 2,
                        fill="#4CAF50"
                    )
            root.after(100, update_ui)

        update_ui()

        # 操作说明
        tk.Label(
            root,
            text="操作说明：\n点击「开始录音」按钮开始录制\n点击「结束录音」按钮保存文件",
            font=("Microsoft YaHei", 10),
            bg="#f0f0f0"
        ).pack(pady=10)


if __name__ == "__main__":
    recorder = SenseVoiceNode()
    print("=" * 40)
    print("增强版语音录制系统已启动".center(40))
    print("=" * 40)
    recorder.start_record_session()