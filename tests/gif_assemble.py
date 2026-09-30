"""把 make_gif_frames.py 产出的原始帧合成 GIF（需要 Pillow）。

用法：
    <有 Pillow 的 python> tests/gif_assemble.py frames.bin screenshots/demo.gif [缩放宽] [颜色数]

说明：帧是原始 RGB，这里用 Pillow 直接构造图像。
默认所有帧共享一个自适应调色板——GIF 每帧自带调色板会白占几百字节，
共享后体积能小一个数量级（代价是渐变色阶略粗，做演示足够）。
"""

import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "frames.bin")
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "screenshots", "demo.gif")
    max_width = int(sys.argv[3]) if len(sys.argv) > 3 else 720
    colors = int(sys.argv[4]) if len(sys.argv) > 4 else 128
    dither = (sys.argv[5].lower() not in ("0", "no", "off")) if len(sys.argv) > 5 else False

    meta_path = os.path.splitext(src)[0] + ".json"
    with open(meta_path, encoding="utf-8") as fh:
        meta = json.load(fh)

    width, height = meta["width"], meta["height"]
    count = meta["frames"]
    durations = meta["durations"]
    frame_bytes = width * height * 3

    scale = min(1.0, max_width / width)
    out_w, out_h = int(round(width * scale)), int(round(height * scale))

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)

    # 第一遍：用若干采样帧统计一个共享调色板
    palette = None
    samples = []
    with open(src, "rb") as fh:
        step = max(1, count // 12)
        for i in range(count):
            raw = fh.read(frame_bytes)
            if len(raw) < frame_bytes:
                break
            if i % step == 0:
                img = Image.frombytes("RGB", (width, height), raw)
                if scale < 1.0:
                    img = img.resize((out_w, out_h), Image.LANCZOS)
                samples.append(img)
    if samples:
        strip = Image.new("RGB", (out_w, out_h * len(samples)))
        for i, img in enumerate(samples):
            strip.paste(img, (0, i * out_h))
        palette = strip.quantize(colors=colors, method=Image.MEDIANCUT)

    # 第二遍：所有帧用同一个调色板转换
    pil_frames = []
    with open(src, "rb") as fh:
        for i in range(count):
            raw = fh.read(frame_bytes)
            if len(raw) < frame_bytes:
                print(f"警告：第 {i} 帧数据不完整，提前结束")
                break
            img = Image.frombytes("RGB", (width, height), raw)
            if scale < 1.0:
                img = img.resize((out_w, out_h), Image.LANCZOS)
            pil_frames.append(img.quantize(
                palette=palette,
                dither=Image.FLOYDSTEINBERG if dither else Image.NONE))
            if (i + 1) % 50 == 0:
                print(f"  已编码 {i + 1}/{count} 帧")

    if not pil_frames:
        raise SystemExit("没有可用帧")

    pil_frames[0].save(
        dst,
        save_all=True,
        append_images=pil_frames[1:],
        duration=durations[:len(pil_frames)],
        loop=0,
        optimize=True,
        disposal=1,
    )
    size_mb = os.path.getsize(dst) / 1024 / 1024
    total_s = sum(durations[:len(pil_frames)]) / 1000
    print(f"已生成 {dst}")
    print(f"  {len(pil_frames)} 帧 · {out_w}x{out_h} · {colors} 色共享调色板 · "
          f"时长 {total_s:.1f}s · {size_mb:.2f} MB")


if __name__ == "__main__":
    main()

