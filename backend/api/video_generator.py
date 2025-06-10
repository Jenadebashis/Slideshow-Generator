import os
import random
import gc
from moviepy.editor import (
    TextClip,
    ImageClip,
    VideoClip,
    CompositeVideoClip,
    concatenate_videoclips,
    AudioFileClip,
)
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout
from moviepy.video.fx.colorx import colorx
from moviepy.video.fx.crop import crop
import numpy as np
from moviepy.audio.fx.audio_loop import audio_loop
from moviepy.config import change_settings
from shutil import which

# Allow overriding the ImageMagick binary location via environment variable
im_path = os.getenv("IMAGEMAGICK_BINARY")
if not im_path:
    im_path = which("magick") or which("convert")
if im_path:
    change_settings({"IMAGEMAGICK_BINARY": im_path})
else:
    print("⚠️ ImageMagick not found. Set IMAGEMAGICK_BINARY or install it to render text.")

TRANSITION_DURATION = 0.3  # seconds for crossfades and text fades

TEXT_TRANSITIONS = [
    "fade",
    "slide_left",
    "slide_right",
    "slide_top",
    "slide_bottom",
    "zoom",
    "typewriter",
    "glitch",
    "rotate",
]

def apply_text_transition(clip, transition, duration, final_pos, video_size):
    vw, vh = video_size
    x_final, y_final = final_pos if isinstance(final_pos, tuple) else ("center", "center")
    if x_final == "center":
        x_final = (vw - clip.w) // 2
    if y_final == "center":
        y_final = (vh - clip.h) // 2
    base_pos = (x_final, y_final)

    if transition == "fade":
        return clip.set_position(base_pos).fx(fadein, duration).fx(fadeout, duration)

    if transition.startswith("slide_"):
        side = transition.split("_")[1]
        start_map = {
            "left": (-clip.w, y_final),
            "right": (vw, y_final),
            "top": (x_final, -clip.h),
            "bottom": (x_final, vh),
        }
        start_pos = start_map.get(side, (x_final, y_final))
        end_map = {
            "left": (vw, y_final),
            "right": (-clip.w, y_final),
            "top": (x_final, vh),
            "bottom": (x_final, -clip.h),
        }
        end_pos = end_map.get(side, (x_final, y_final))

        def pos(t):
            if t < duration:
                p = t / duration
                x = start_pos[0] + (x_final - start_pos[0]) * p
                y = start_pos[1] + (y_final - start_pos[1]) * p
                return x, y
            elif t > clip.duration - duration:
                p = (t - (clip.duration - duration)) / duration
                x = x_final + (end_pos[0] - x_final) * p
                y = y_final + (end_pos[1] - y_final) * p
                return x, y
            else:
                return x_final, y_final

        return clip.set_position(pos)

    if transition == "zoom":
        zoom_in_t = 0.4 * clip.duration
        hold_t = 0.4 * clip.duration
        zoom_out_t = max(clip.duration - zoom_in_t - hold_t, 0.01)

        def resize(t):
            if t < zoom_in_t:
                return 0.3 + 0.7 * (t / zoom_in_t)
            if t < zoom_in_t + hold_t:
                return 1.0
            return 0.3 + 0.7 * (max(clip.duration - t, 0) / zoom_out_t)

        return clip.set_position(base_pos).resize(resize).fx(fadeout, zoom_out_t)

    if transition == "typewriter":
        appear_t = 0.5 * clip.duration
        hold_t = 0.35 * clip.duration
        disappear_t = max(clip.duration - appear_t - hold_t, 0.01)

        def mask_frame(t):
            if t < appear_t:
                frac = t / appear_t
            elif t < appear_t + hold_t:
                frac = 1.0
            else:
                frac = max(0.0, (clip.duration - t) / disappear_t)
            w = int(clip.w * frac)
            mask = np.zeros((clip.h, clip.w))
            mask[:, :w] = 1.0
            return mask

        mask_clip = VideoClip(mask_frame, ismask=True).set_duration(clip.duration)

        if clip.mask is not None:
            def combined_mask_frame(t):
                return clip.mask.get_frame(t) * mask_clip.get_frame(t)
            combined = VideoClip(combined_mask_frame, ismask=True).set_duration(clip.duration)
        else:
            combined = mask_clip

        return clip.set_position(base_pos).set_mask(combined)

    if transition == "glitch":
        def pos(t):
            if t < duration or t > clip.duration - duration:
                jitter = random.randint(-10, 10)
                return base_pos[0] + jitter, base_pos[1] + jitter
            return base_pos

        return clip.set_position(pos)

    if transition == "rotate":
        def rotation(t):
            total_duration = clip.duration
            in_duration = 0.2 * total_duration
            still_duration = 0.6 * total_duration
            out_duration = 0.2 * total_duration

            if t < in_duration:
                return -15 + 15 * (t / in_duration)
            elif t < in_duration + still_duration:
                return 0
            else:
                time_into_out = t - (in_duration + still_duration)
                return 15 * (time_into_out / out_duration)

        return clip.set_position(base_pos).rotate(rotation)

    return clip.set_position(base_pos)

def apply_image_transition(clip1, clip2, duration=TRANSITION_DURATION):
    clip1 = clip1.crossfadeout(duration)
    clip2 = clip2.crossfadein(duration).set_start(clip1.duration - duration)
    final = CompositeVideoClip([clip1, clip2])
    return final.set_duration(clip1.duration + clip2.duration - duration)


def generate_video(
    texts,
    image_paths,
    music_path,
    output_path,
    duration_per_slide=4,
    size=(720, 1280),
    positions=None,
    durations=None,
    darkening=None,
    transitions=None,
):
    if positions is None:
        positions = []
    if transitions is None:
        transitions = []

    image_clips = []
    text_clips = []
    slide_durations = []

    print("🟡 Debug Info:")
    print(f"Number of texts: {len(texts)}")
    print(f"Number of image paths: {len(image_paths)}")
    print(f"Positions received: {positions}")
    print(f"🌓 Darkening level applied to images: {darkening}\n")

    available_transitions = TEXT_TRANSITIONS.copy()
    random.shuffle(available_transitions)

    for i, text in enumerate(texts):
        image_path = image_paths[i % len(image_paths)]
        position_percent = positions[i] if i < len(positions) and positions[i].strip() else None
        slide_duration = durations[i] if durations and i < len(durations) else duration_per_slide

        if position_percent:
            try:
                percent = float(position_percent)
                y_pos = int(size[1] * percent / 100.0)
                y_pos = max(40, min(y_pos, size[1] - 100))
                text_position = ("center", y_pos)
            except Exception as e:
                print(f"Invalid position: {e}")
                text_position = "center"
        else:
            text_position = "center"

        try:
            transition_name = transitions[i].strip() if transitions and i < len(transitions) and transitions[i].strip() else (
                available_transitions.pop() if available_transitions else random.choice(TEXT_TRANSITIONS)
            )
            txt_duration = max(slide_duration - 2 * TRANSITION_DURATION, 0.1)

            txt_clip = TextClip(
                text,
                fontsize=40,
                color='white',
                font="Arial",
                method='caption',
                bg_color='transparent',
                size=(size[0] - 100, None),
                align='center'
            ).set_duration(txt_duration)

            txt_clip = apply_text_transition(txt_clip, transition_name, TRANSITION_DURATION, text_position, size)
            print(f"💫 Slide {i}: Text transition '{transition_name}' applied.")

            text_clips.append(txt_clip)
            print(f"📝 Added text clip of duration {txt_clip.duration:.2f}s")

        except Exception as e:
            print(f"❗ Slide {i}: TextClip creation failed. Error: {e}")
            continue

        darken_value = darkening[i] if isinstance(darkening, list) and i < len(darkening) else (
            darkening if isinstance(darkening, (float, int)) else 1.0
        )

        try:
            img_clip = ImageClip(image_path).resize(height=size[1])
            img_clip = img_clip.crop(width=size[0], height=size[1], x_center=img_clip.w / 2, y_center=img_clip.h / 2)
            img_clip = img_clip.set_duration(slide_duration)
            img_clip = colorx(img_clip, darken_value)
            print(f"🖼 Slide {i}: Image darkened by factor {darken_value} and duration {slide_duration}")
            image_clips.append(img_clip)
            print(f"🖼 Added image clip of duration {img_clip.duration:.2f}s")

        except Exception as e:
            print(f"❗ Slide {i}: Image processing failed. Error: {e}")
            continue

        slide_durations.append(slide_duration)
        print(f"✅ Slide {i} prepared successfully.\n")

    if not image_clips:
        raise ValueError("No slides generated: check texts and image paths.")

    final_video = image_clips[0]
    print(f"🧱 Initial image clip set as base.")
    for i in range(1, len(image_clips)):
        print(f"🔁 Transitioning image {i-1} ➜ {i}")
        final_video = apply_image_transition(final_video, image_clips[i], duration=TRANSITION_DURATION)

    start_times = [0]
    print(f"🧮 Calculating image start times:")
    print(f"  Slide 0 image starts at 0.00s")

    for idx, dur in enumerate(slide_durations[:-1]):
        next_start = start_times[-1] + dur - TRANSITION_DURATION
        start_times.append(next_start)
        print(f"  Slide {idx + 1} image starts at {next_start:.2f}s (previous duration={dur}, crossfade={TRANSITION_DURATION})")

    # Different start logic for first vs others
    text_start_times = []
    for i, s in enumerate(start_times):
        start_time = s + TRANSITION_DURATION
        text_start_times.append(start_time)

    print(f"\n🧮 Calculating text start times (after image transition in):")
    for i, s in enumerate(text_start_times):
        print(f"  Slide {i} text starts at {s:.2f}s")

    # ⚠️ Overlap detection
    for i in range(len(text_start_times)):
        text_start = text_start_times[i]
        text_end = text_start + text_clips[i].duration
        img_start = start_times[i]
        img_end = img_start + slide_durations[i]

        if text_start < img_start + TRANSITION_DURATION:
            print(f"⚠️ Text {i} starts during image transition IN (fade-in overlap).")
        if text_end > img_end - TRANSITION_DURATION:
            print(f"⚠️ Text {i} ends during image transition OUT (fade-out overlap).")

    overlays = [final_video]
    for t, s in zip(text_clips, text_start_times):
        print(f"🕒 Text clip starts at {s:.2f}s, duration = {t.duration:.2f}s, ends at {s + t.duration:.2f}s")
        overlays.append(t.set_start(s))

    print(f"📐 Compositing final video with {len(overlays)} layers (1 base + {len(overlays) - 1} text clips)")
    final_video = CompositeVideoClip(overlays, size=size)

    if music_path:
        try:
            audio = AudioFileClip(music_path)
            final_video = final_video.set_audio(audio_loop(audio, duration=final_video.duration))
        except Exception as e:
            print(f"❗ Audio Error: {e}")

    try:
        print(f"🚀 Starting render of final video. Total duration: {final_video.duration:.2f}s")
        final_video.write_videofile(
            output_path,
            fps=24,
            audio=True,
            remove_temp=True,
            threads=4,
            logger=None
        )
        print("🎬 Video written successfully.")
    finally:
        if hasattr(final_video.audio, 'close'):
            try:
                final_video.audio.close()
            except:
                pass
        del final_video
        gc.collect()
