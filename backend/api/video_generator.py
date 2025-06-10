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
    ColorClip,
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

IMAGE_EFFECTS = [
    "depth_zoom",
    "ken_burns",
    "color_grade",
    "light_leaks",
    "film_grain",
    "vignette",
    "motion_overlay",
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
        zoom_in_t = 0.4 * clip.duration
        hold_t = 0.4 * clip.duration
        zoom_out_t = max(clip.duration - zoom_in_t - hold_t, 0.01)

        def resize(t):
            if t < zoom_in_t:
                return 0.3 + 0.7 * (t / zoom_in_t)
            if t < zoom_in_t + hold_t:
                return 1.0
            return 0.3 + 0.7 * (max(clip.duration - t, 0) / zoom_out_t)
        return (
            clip.set_position(base_pos)
            .resize(resize)
            .fx(fadeout, zoom_out_t)
        )

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

def apply_image_effect(clip, effect_name, duration, size):
    """Apply visual effects to an image clip."""
    if effect_name == "depth_zoom":
        def zoom(t):
            return 1 + 0.3 * (t / duration)

        def pos(t):
            p = t / duration
            return (-size[0] * 0.05 * p, -size[1] * 0.05 * p)

        return clip.resize(zoom).set_position(pos)

    if effect_name == "ken_burns":
        def zoom(t):
            return 1 + 0.1 * (t / duration)

        def pos(t):
            p = t / duration
            return (-size[0] * 0.02 * p, -size[1] * 0.02 * p)

        return clip.resize(zoom).set_position(pos)

    if effect_name == "color_grade":
        return colorx(clip, 1.2)

    if effect_name == "light_leaks":
        overlay = ColorClip(size, color=(255, 200, 150)).set_opacity(0.3).set_duration(duration)
        return CompositeVideoClip([clip, overlay], size=size)

    if effect_name == "film_grain":
        def noise_frame(t):
            return (np.random.rand(size[1], size[0], 3) * 255).astype("uint8")

        grain = VideoClip(noise_frame, ismask=False).set_opacity(0.05).set_duration(duration)
        return CompositeVideoClip([clip, grain], size=size)

    if effect_name == "vignette":
        y, x = np.ogrid[:size[1], :size[0]]
        cx, cy = size[0] / 2, size[1] / 2
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        max_dist = np.sqrt(cx ** 2 + cy ** 2)
        mask = 1 - np.clip(dist / max_dist, 0, 1)

        def apply(frame):
            return (frame * mask[..., None]).astype("uint8")

        return clip.fl_image(apply)

    if effect_name == "motion_overlay":
        def motion_frame(t):
            frame = np.zeros((size[1], size[0], 3), dtype="uint8")
            y = int((t * 50) % size[1])
            frame[max(0, y - 2):y + 2, :, :] = 255
            return frame

        overlay = VideoClip(motion_frame).set_opacity(0.1).set_duration(duration)
        return CompositeVideoClip([clip, overlay], size=size)

    return clip

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
    image_effects=None,
):
    if positions is None:
        positions = []
    if transitions is None:
        transitions = []
    if image_effects is None:
        image_effects = []
    image_clips = []
    text_clips = []
    slide_durations = []

    print("🟡 Debug Info:")
    print(f"Number of texts: {len(texts)}")
    print(f"Number of image paths: {len(image_paths)}")
    print(f"Positions received: {positions}")
    print(f"🌓 Darkening level applied to images: {darkening}")
    print(f"✨ Image effects: {image_effects}\n")
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
                txt_duration = max(slide_duration - TRANSITION_DURATION, 0.1)

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
            effect_name = image_effects[i].strip() if image_effects and i < len(image_effects) and image_effects[i].strip() else None
            if effect_name:
                img_clip = apply_image_effect(img_clip, effect_name, slide_duration, size)
                print(f"🖼 Slide {i}: Effect '{effect_name}' applied")
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
