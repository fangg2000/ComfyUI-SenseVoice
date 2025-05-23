import os
import sys
import sounddevice as sd
import numpy as np
import time
import re
import torch
import threading
import random
import io

from funasr import AutoModel
# from funasr.utils.postprocess_utils import rich_transcription_postprocess
from modelscope import snapshot_download
from scipy.io.wavfile import write
from datetime import datetime

now_dir = os.path.dirname(os.path.abspath(__file__))


# 注册节点
class VoiceRecorderNode:
    CATEGORY = "fg/Record Node"
    RETURN_TYPES = ("AUDIO", "LIST")
    RETURN_NAMES = ("audio", "file_path_list")
    FUNCTION = "process_record"
    OUTPUT_NODE = True

    def __init__(self):
        self.save_dir = None

        # 录音控制变量
        self.is_recording = False
        self.audio_data_list = []
        self.audio_data = None
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
                "folder": ("STRING", {"directory": True, "default": "./temp"}),
                "random_seed": ("INT", {
                    "default": random.randint(0, 10000000),
                    "min": 0,
                    "max": 10000000
                }),
                "wait_for_seconds": ("INT", {"default": 1, "min": 0, "max": 5}),
                "sample_rate": ([8000, 16000, 22050, 44100, 48000], {
                    "default": 16000
                }),
                "record_seconds": ("FLOAT", {"default": 5.0, "min": 1.0, "max": 360.0, "step": 1.0}),
                "remove_file": ("BOOLEAN", {"default": False})
            },
        }

    def process_record(self, folder, random_seed, wait_for_seconds, sample_rate, record_seconds, remove_file):
        # 采样率
        self.fs = sample_rate

        try:
            # 创建保存目录
            os.makedirs(folder, exist_ok=True)
            self.save_dir = folder

            # 等待录音时长
            time.sleep(wait_for_seconds)

            # 启动一个定时器，在10秒后调用函数
            timer = threading.Timer(record_seconds, self.stop_recording)
            timer.start()

            self.start_recording()

            time.sleep(record_seconds + 1)
            # random_value = random.randint(0, 100)

            return {
                "ui": {
                    "status": [self.audio_path],
                    "progress": [0.5]
                },
                "result": (self.audio_data, [self.audio_path])
            }
        except Exception as e:
            # return (None, f"错误: {str(e)}")
            return {"ui": {"error": "no record data"}, "result": (None, ["error"])}
        finally:
            self.audio_data_list = None
            self.audio_data = None
            if remove_file:
                print('准备删除音频文件')
                timer = threading.Timer(15, self.remove_audio_file)
                timer.start()
            else:
                self.audio_path = None

    def remove_audio_file(self):
        print(f"删除音频文件--{self.audio_path}")
        os.remove(self.audio_path)
        self.audio_path = None

    # 核心录音控制逻辑 --------------------------------------------------
    def start_recording(self):
        """优化的录音启动逻辑"""
        current_time = time.time()
        if (current_time - self.last_press_time) < self.debounce_interval:
            return

        if not self.is_recording:
            self.last_press_time = current_time
            self.is_recording = True
            self.audio_data_list = []
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
            if len(self.audio_data_list) > 0:
                self.save_recording()
            # print("✅ 录音已保存")

    def audio_callback(self, indata, frames, time, status):
        """实时音频回调函数"""
        if self.is_recording:
            self.audio_data_list.append(indata.copy())

    # 文件保存逻辑 ------------------------------------------------------
    def save_recording(self):
        """优化的音频保存方法"""
        try:
            # print('开始保存音频数据...')
            full_recording = np.concatenate(self.audio_data_list, axis=0)

            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(
                self.save_dir,
                f"recording_{timestamp}.wav"
            )

            write(filename, self.fs, full_recording)
            # print(f"💾 文件已保存到：{os.path.abspath(filename)}")
            print("✅ 录音已保存")

            # 创建一个 BytesIO 缓冲区来保存 WAV 数据
            # wav_buffer = io.BytesIO()
            # 写入 WAV 数据到缓冲区
            # write(wav_buffer, self.fs, full_recording)
            # 获取二进制数据
            # binary_wav_data = wav_buffer.getvalue()

            # 假设 full_recording 是 int16 类型的 NumPy 数组，形状是 (T,) 或 (T, 1) 或 (T, 2)
            # fs = self.fs 一般是 44100 或 48000

            # Step 1: 如果是整数 PCM 格式（如 int16），归一化到 [-1, 1]
            if full_recording.dtype == np.int16:
                full_recording = full_recording.astype(np.float32) / 32768.0
            elif full_recording.dtype == np.int32:
                full_recording = full_recording.astype(np.float32) / 2147483648.0

            # Step 2: 确保形状为 [1, T] 或 [1, 1, T]（batch=1, channel=1）
            if len(full_recording.shape) == 1:
                # 单声道，shape: (T,)
                full_recording = full_recording[np.newaxis, np.newaxis, :]  # -> (1, 1, T)
            elif len(full_recording.shape) == 2:
                if full_recording.shape[1] == 1 or full_recording.shape[1] == 2:
                    # 单声道或立体声 shape: (T, 1) or (T, 2)
                    full_recording = np.expand_dims(full_recording, axis=0)  # -> (1, T, 1/2)

            # Step 3: 转换为 PyTorch 张量，并确保是 float32
            waveform_tensor = torch.tensor(full_recording, dtype=torch.float32)

            # 最终结果
            # output = {
            #     'waveform': waveform_tensor,
            #     'sample_rate': self.fs
            # }

            self.audio_path = filename
            self.audio_data = (waveform_tensor, self.fs)
        except Exception as e:
            print(f"保存失败: {str(e)}")


class STTNode:

    def __init__(self):
        self.model = None
        self.model_dir = None
        self.result_txt = None

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # "audio": ("AUDIO",),
                "audio_path": ("STRING",),
                "language": (["auto",  "zh", "en", "yue", "ja", "ko", "nospeech"], {
                    "default": "auto"
                }),
                "use_itn": ("BOOLEAN", {"default": True}),
                "batch_size_s": ("INT", {"default": 60, "min": 1, "max": 100}),
                "merge_vad": ("BOOLEAN", {"default": True}),
                "merge_length_s": ("INT", {"default": 15, "min": 1, "max": 30})
            }
        }

    RETURN_TYPES = ("LIST",)
    RETURN_NAMES = ("list_string",)
    FUNCTION = "generate"
    CATEGORY = "STT/SenseVoice"
    OUTPUT_NODE = True

    def generate(self, audio_path, language, use_itn, batch_size_s, merge_vad, merge_length_s):
        # 使用示例
        comfyui_root = get_comfyui_root()
        #comfyui_root = None
        # print("ComfyUI根目录:", comfyui_root)

        try:
            if comfyui_root is None:
                self.model_dir = "iic/SenseVoiceSmall"
                snapshot_download(model_id="iic/SenseVoiceSmall")
            else:
                #self.model_dir = os.path.join(now_dir, "models", "checkpoints", "SenseVoiceSmall")
                self.model_dir = os.path.join(comfyui_root, "models", "checkpoints", "SenseVoiceSmall")
                snapshot_download(model_id="iic/SenseVoiceSmall", local_dir=self.model_dir)

            if self.model is None:
                self.model = AutoModel(
                    model=self.model_dir,
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
                language=language,  # "zh", "en", "yue", "ja", "ko", "nospeech"
                use_itn=use_itn,
                batch_size_s=batch_size_s,
                merge_vad=merge_vad,
                merge_length_s=merge_length_s,
            )

            self.result_txt = re.sub(r'<\|.*?\|>', '', res[0]["text"])
            # print(text)

            return [self.result_txt]
        except Exception as e:
            print(f"sensevoice推理异常: {str(e)}")
            pass
        finally:
            self.result_txt = None

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
NODE_DISPLAY_NAME_MAPPINGS = {"VoiceRecorderNode": "voice record", "STTNode": "STT By SenseVoice"}

# 主程序入口 ---------------------------------------------------------
# if __name__ == "__main__":
#     recorder = STTNode()
#     print("="*40)
#     print("语音录制系统已启动".center(40))
#     print("="*40)
#     recorder.generate('/home/fangg/other/save_voice/data_set/zh/TP225/300006.wav', 60)

def get_comfyui_root():
    # 获取主模块（通常是启动脚本，如main.py）
    main_module = sys.modules.get('__main__')
    if main_module and hasattr(main_module, '__file__'):
        main_path = os.path.abspath(main_module.__file__)
        root_dir = os.path.dirname(main_path)
        return root_dir
    else:
        # 若无法获取主模块路径，回退到当前工作目录
        return None
