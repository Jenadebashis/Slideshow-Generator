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
    """Apply one of several animation effects to a text clip."""
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
        def resize(t):
            if t < duration:
                return 0.3 + 0.7 * (t / duration)
            if t > clip.duration - duration:
                return 0.3 + 0.7 * (max(clip.duration - t, 0) / duration)
            return 1.0
        return clip.set_position(base_pos).resize(resize)

    if transition == "typewriter":
        appear_t = 0.7 * clip.duration
        hold_t = 0.2 * clip.duration
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

        return clip.set_position(base_pos).set_mask(mask_clip)

    if transition == "glitch":
        def pos(t):
            if t < duration or t > clip.duration - duration:
                jitter = random.randint(-10, 10)
                return base_pos[0] + jitter, base_pos[1] + jitter
            return base_pos

        return clip.set_position(pos)

    if transition == "rotate":
        def rotation(t):
            if t < duration:
                return -15 + 15 * (t / duration)
            if t > clip.duration - duration:
                return 15 * ((clip.duration - t) / duration)
            return 0

        return clip.set_position(base_pos).rotate(rotation)

    # Fallback
    return clip.set_position(base_pos)

def apply_image_transition(clip1, clip2, duration=TRANSITION_DURATION):
    """Crossfade two clips without affecting their original durations."""
    return concatenate_videoclips(
        [clip1.crossfadeout(duration), clip2.crossfadein(duration)],
        method="compose",
    )

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

        if position_percent is not None and position_percent != "":
            try:
                percent = float(position_percent)
                y_pos = int(size[1] * percent / 100.0)
                y_pos = max(40, min(y_pos, size[1] - 100))  # Clamp
                text_position = ("center", y_pos)
            except Exception as e:
                print(f"Invalid position: {e}")
                text_position = "center"
        else:
            text_position = "center"
        try:
            if transitions and i < len(transitions) and transitions[i].strip():
                transition_name = transitions[i].strip()
            else:
                transition_name = (
                    available_transitions.pop()
                    if available_transitions
                    else random.choice(TEXT_TRANSITIONS)
                )
            is_last_slide = i == len(texts) - 1
            if is_last_slide:
                txt_duration = slide_duration
            else:
                txt_duration = max(slide_duration - 2 * TRANSITION_DURATION, 0.1)
            txt_clip = (
                TextClip(
                    text,
                    fontsize=40,
                    color='white',
                    font="Arial",  # or your font path
                    method='caption',
                    bg_color='transparent',
                    size=(size[0] - 100, None),
                    align='center'
                )
                .set_duration(txt_duration)
            )
            txt_clip = apply_text_transition(
                txt_clip,
                transition_name,
                TRANSITION_DURATION,
                text_position,
                size,
            )
            print(f"💫 Slide {i}: Text transition '{transition_name}' applied.")
        except Exception as e:
            print(f"❗ Slide {i}: TextClip creation failed. Error: {e}")
            continue  # Skip this slide if text rendering fails
        
        # Determine per-slide darkening value
        if isinstance(darkening, list):
            darken_value = darkening[i] if i < len(darkening) else darkening[-1]
        elif isinstance(darkening, (float, int)):
            darken_value = darkening
        else:
            darken_value = 1.0  # No darkening

        try:
            img_clip = ImageClip(image_path).resize(height=size[1])
            img_clip = img_clip.crop(width=size[0], height=size[1], x_center=img_clip.w / 2, y_center=img_clip.h / 2)
            img_clip = img_clip.set_duration(slide_duration)
            img_clip = colorx(img_clip, darken_value)
            print(f"🖼 Slide {i}: Image darkened by factor {darken_value} and duration {slide_duration}")
        except Exception as e:
            print(f"❗ Slide {i}: Image processing failed. Error: {e}")
            continue

        image_clips.append(img_clip)
        text_clips.append(txt_clip)
        slide_durations.append(slide_duration)
        print(f"✅ Slide {i} prepared successfully.\n")

    if not image_clips:
        raise ValueError("No slides generated: check texts and image paths.")

    # Build the base video by crossfading only the images
    final_video = image_clips[0]
    for i in range(1, len(image_clips)):
        final_video = apply_image_transition(final_video, image_clips[i], duration=TRANSITION_DURATION)

    # Calculate start times for overlaying text clips
    start_times = [0]
    for dur in slide_durations[:-1]:
        start_times.append(start_times[-1] + dur - TRANSITION_DURATION)

    text_start_times = [s + TRANSITION_DURATION for s in start_times]

    # Overlay text clips at their corresponding start times
    overlays = [final_video] + [t.set_start(s) for t, s in zip(text_clips, text_start_times)]
    final_video = CompositeVideoClip(overlays, size=size)

    if music_path:
        try:
            audio = AudioFileClip(music_path)
            final_video = final_video.set_audio(audio_loop(audio, duration=final_video.duration))
        except Exception as e:
            print(f"❗ Audio Error: {e}")

    try:
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
