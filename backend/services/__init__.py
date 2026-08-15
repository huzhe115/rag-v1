"""Shared service primitives."""
import threading

# GPU 推理 + BM25 状态读写共用的一把锁：
# 并发 embed/rerank 会双倍占显存（OOM），BM25 三段状态需原子替换。
# # ponytail: 全局锁——检索毫秒级、推理瓶颈本身就在锁内，吞吐问题不在此
NN_LOCK = threading.Lock()
