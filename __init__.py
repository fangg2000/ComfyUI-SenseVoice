import os
now_dir = os.path.dirname(os.path.abspath(__file__))
import sounddevice as sd
import numpy as np
import time
import re
import torch
import threading

from funasr import AutoModel
# from funasr.utils.postprocess_utils import rich_transcription_postprocess
from modelscope import snapshot_download
from scipy.io.wavfile import write
from datetime import datetime


pre_model_dir = os.path.join(now_dir,"pretrianed_models","SenseVoiceSmall")
snapshot_download(model_id="iic/SenseVoiceSmall",local_dir=pre_model_dir)

# 注册节点
class VoiceRecorderNode:
    CATEGORY = "fg/录音工具"
    RETURN_TYPES = ("LIST",)
    RETURN_NAMES = ("file_path_list",)
    FUNCTION = "process_record"
    OUTPUT_NODE = True

    def __init__(self):
        self.save_dir = None

        # 录音控制变量
        self.is_recording = False
        self.audio_data = []
        self.audio_path = ""
        self.last_press_time = 0
        self.debounce_interval = 0.3  # 优化防抖时间

        # 音频流对象
        self.stream = None
        self.fs = 44100  # 固定采样率

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"directory": True, "default":"./ComfyUI/output"}),
                "enable_processing": ("BOOLEAN", {"default": False}),
                "record_seconds": ("FLOAT", {"default": 10.0, "min":1.0, "max":360.0})
            },
        }

    def process_record(self, folder, enable_processing, record_seconds):
        try:
            # 创建保存目录
            os.makedirs(folder, exist_ok=True)
            self.save_dir = folder

            # 状态切换逻辑
            if enable_processing:
                # 启动一个定时器，在10秒后调用函数
                timer = threading.Timer(record_seconds, self.stop_recording)
                timer.start()

                self.start_recording()

                time.sleep(record_seconds+1)

                return {
                    "ui": {
                        "status": [self.audio_path],
                        "progress": [0.5 if enable_processing else 0]
                    },
                    "result": [self.audio_path]
                }
            else:
                return {"ui": {"error": "no record data"}, "result": ""}
        except Exception as e:
            # return (None, f"错误: {str(e)}")
            return {"ui": {"error": "no record data"}, "result": "error"}

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
                self.save_recording()
            # print("✅ 录音已保存")

    def audio_callback(self, indata, frames, time, status):
        """实时音频回调函数"""
        if self.is_recording:
            self.audio_data.append(indata.copy())

    # 文件保存逻辑 ------------------------------------------------------
    def save_recording(self):
        """优化的音频保存方法"""
        try:
            # print('开始保存音频数据...')
            full_recording = np.concatenate(self.audio_data, axis=0)

            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(
                self.save_dir,
                f"recording_{timestamp}.wav"
            )

            write(filename, self.fs, full_recording)
            # print(f"💾 文件已保存到：{os.path.abspath(filename)}")
            print("✅ 录音已保存")

            self.audio_path = filename
        except Exception as e:
            print(f"保存失败: {str(e)}")


class STTNode:

    def __init__(self):
        self.model = None

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # "audio": ("AUDIO",),
                "audio_path": ("STRING",),
                "batch_size_s": ("INT", {
                    "default": 30
                })
            }
        }

    RETURN_TYPES = ("LIST",)
    RETURN_NAMES = ("list_string",)
    FUNCTION = "generate"
    CATEGORY = "STT/SenseVoice"
    OUTPUT_NODE = True

    def generate(self, audio_path, batch_size_s):
        if self.model is None:
            self.model = AutoModel(
                model=pre_model_dir,
                trust_remote_code=True,
                # remote_code="./model.py",
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                disable_update=True,
                device="cuda:0",
            )

            # print(f"模型加载成功--{audio_path}")

        res = self.model.generate(
            input=audio_path,
            cache={},
            language="auto",  # "zh", "en", "yue", "ja", "ko", "nospeech"
            use_itn=True,
            batch_size_s=batch_size_s,
            merge_vad=True,
            merge_length_s=15,
        )

        text = re.sub(r'<\|.*?\|>', '', res[0]["text"])
        # print(text)

        return [text]

# class ShowTextNode:
#     @classmethod
#     def INPUT_TYPES(s):
#         return {
#             "required": {
#                 "sense_voice_output":("TEXT",),
#                 "text": ("STRING", {"multiline": True, "dynamicPrompts": True}),
#             }
#         }
#     RETURN_TYPES = ()
#     FUNCTION = "encode"
#     OUTPUT_NODE = True
#     CATEGORY = "AIFSH_SenseVoice"
#
#     def encode(self,sense_voice_output,text):
#         return {"ui":{"text":[sense_voice_output]}}
#
# WEB_DIRECTORY = "./js"

NODE_CLASS_MAPPINGS = {
    "VoiceRecorderNode":VoiceRecorderNode,
    "STTNode": STTNode,
    # "ShowTextNode":ShowTextNode
}
NODE_DISPLAY_NAME_MAPPINGS = {"VoiceRecorderNode": "voice record", "STTNode": "voice to text"}

# 主程序入口 ---------------------------------------------------------
# if __name__ == "__main__":
#     recorder = STTNode()
#     print("="*40)
#     print("语音录制系统已启动".center(40))
#     print("="*40)
#     recorder.generate('/home/fangg/other/save_voice/data_set/zh/TP225/300006.wav', 60)
