"""Inference latency of M1 (fine-tuned Chronos-Bolt-Small, 47.7 M) and the distilled student (14.5 M), batch 1.
Budgets from the paper text: < 5 ms full model, < 2 ms distilled. Measured, not assumed; several execution
configurations are reported separately (GPU eager fp32 / bf16 / CUDA graph, CPU one thread) -- they are NOT interchangeable.
Per configuration: warm-up, then N timed calls with a device sync, perf_counter_ns.

Run: python -m paibo_bip.m1.latency_m1
"""
import json
import os
import time

import numpy as np
import torch

from .train_m1 import OUT, load_chronos, make_student

N, WARM = 1500, 200


def stats(us):
    us = np.asarray(us)
    return {"n": int(us.size), "mean_ms": float(us.mean() / 1000), "median_ms": float(np.median(us) / 1000),
            "std_ms": float(us.std(ddof=1) / 1000), "p95_ms": float(np.percentile(us, 95) / 1000),
            "p99_ms": float(np.percentile(us, 99) / 1000), "max_ms": float(us.max() / 1000)}


def timed(fn, sync):
    for _ in range(WARM):
        fn()
    sync()
    out = []
    for _ in range(N):
        t0 = time.perf_counter_ns()
        fn()
        sync()
        out.append((time.perf_counter_ns() - t0) / 1000.0)
    return stats(out)


def main():
    res = {"note": "batch 1, context 60 s, horizon 30 s; sync after every call", "device": None, "torch": torch.__version__}
    ctx_cpu = torch.rand(1, 60) * 400
    models = {}
    small = load_chronos("small")
    small.load_state_dict(torch.load(os.path.join(OUT, "m1_small_finetuned.pt"), map_location="cpu"))
    models["small_finetuned_47.7M"] = small
    sp = os.path.join(OUT, "m1_student_distilled.pt")
    if os.path.exists(sp):
        st = make_student()
        st.load_state_dict(torch.load(sp, map_location="cpu"))
        models["student_distilled_14.5M"] = st
    res["params"] = {k: int(sum(p.numel() for p in m.parameters())) for k, m in models.items()}
    cuda = torch.cuda.is_available()
    res["device"] = torch.cuda.get_device_name(0) if cuda else "cpu only"
    for name, m in models.items():
        m.eval()
        r = {}
        with torch.inference_mode():
            if cuda:
                m.to("cuda")
                c = ctx_cpu.to("cuda")
                sync = torch.cuda.synchronize
                r["gpu_eager_fp32"] = timed(lambda: m(context=c).quantile_preds, sync)
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    r["gpu_eager_bf16"] = timed(lambda: m(context=c).quantile_preds, sync)
                try:
                    static = c.clone()
                    s = torch.cuda.Stream()
                    s.wait_stream(torch.cuda.current_stream())
                    with torch.cuda.stream(s):
                        for _ in range(3):
                            m(context=static)
                    torch.cuda.current_stream().wait_stream(s)
                    g = torch.cuda.CUDAGraph()
                    with torch.cuda.graph(g):
                        out = m(context=static).quantile_preds
                    ref = m(context=static).quantile_preds
                    static.copy_(c); g.replay(); sync()
                    r["cuda_graph_matches_eager"] = bool(torch.allclose(out, ref, atol=1e-3, rtol=1e-3))
                    r["gpu_cuda_graph_fp32"] = timed(lambda: (static.copy_(c), g.replay()), sync)
                except Exception as e:
                    r["gpu_cuda_graph_fp32"] = f"not captured: {type(e).__name__}: {str(e)[:100]}"
                m.to("cpu")
            torch.set_num_threads(1)
            r["cpu_1_thread_fp32"] = timed(lambda: m(context=ctx_cpu).quantile_preds, lambda: None)
            torch.set_num_threads(4)
            r["cpu_4_threads_fp32"] = timed(lambda: m(context=ctx_cpu).quantile_preds, lambda: None)
        res[name] = r
    res["budgets_ms"] = {"full_model": 5.0, "distilled_model": 2.0}
    json.dump(res, open(os.path.join(OUT, "m1_latency.json"), "w"), indent=2)
    for name in models:
        for cfg, v in res[name].items():
            if isinstance(v, dict) and "mean_ms" in v:
                print(f"{name:26s} {cfg:22s} mean {v['mean_ms']:7.2f} ms  median {v['median_ms']:7.2f}  p95 {v['p95_ms']:7.2f}  p99 {v['p99_ms']:7.2f}")
            else:
                print(f"{name:26s} {cfg:22s} {v}")


if __name__ == "__main__":
    main()
