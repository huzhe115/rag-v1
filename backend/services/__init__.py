"""Shared service primitives."""
import os
import threading

# 模型已本地缓存：默认强制 HF 离线，避免 import 时访问 huggingface.co
# （国内网络下实测：启动 import 链 79s → 16s）。新机器首次运行需先在线下载模型，
# 在系统/Shell 环境变量显式设 HF_HUB_OFFLINE=0 可覆盖。
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# GPU 推理 + BM25 状态读写共用的一把锁：
# 并发 embed/rerank 会双倍占显存（OOM），BM25 三段状态需原子替换。
# # ponytail: 全局锁——检索毫秒级、推理瓶颈本身就在锁内，吞吐问题不在此
NN_LOCK = threading.Lock()
