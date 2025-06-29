import os
import random
import cv2
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
from scipy.ndimage import convolve1d
from moviepy.editor import AudioFileClip
from pydub import AudioSegment
from pydub.playback import play
from pathlib import Path

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
    "depth_zoom",         # immersive zoom
    "ken_burns",          # slow pan + zoom storytelling
    "film_grain",         # vintage cinematic texture
    "ripple",             # smooth vertical emotion wave
    "light_pulse",        # ambient brightness pulse
    "parallax_pan",       # subtle 3D camera motion
    "color_tint_shift",   # emotional warm–cool tone shift
    "wave_scan",
    'parallax_slide', 
    'tilted_perspective',
    'depth_swing',
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

from moviepy.editor import VideoClip, CompositeVideoClip
import numpy as np
import cv2
import random

def apply_image_transition(clip1, clip2, duration=TRANSITION_DURATION):
    clip1 = clip1.crossfadeout(duration)
    clip2 = clip2.crossfadein(duration).set_start(clip1.duration - duration)
    final = CompositeVideoClip([clip1, clip2])
    return final.set_duration(clip1.duration + clip2.duration - duration)


import numpy as np
from moviepy.editor import VideoClip, CompositeVideoClip, ColorClip

def apply_image_effect(clip, effect_name, duration, size):
    """Apply visual effects to an image clip."""
    w, h = size

    if effect_name == "parallax_slide":
        def zoom(t):
            return 1 + 0.05 * (t / duration)
        def pos(t):
            p = t / duration
            return (-w * 0.1 * p, -h * 0.05 * (1 - p))
        return clip.resize(zoom).set_position(pos)

    if effect_name == "tilted_perspective":
        def zoom(t):
            return 1 + 0.2 * (t / duration)
        def pos(t):
            p = t / duration
            return (-w * 0.08 * p, -h * 0.02 * p)
        return clip.resize(zoom).set_position(pos).rotate(lambda t: 2.0 * np.sin(2 * np.pi * t / duration))

    if effect_name == "depth_swing":
        def zoom(t):
            return 1 + 0.03 * np.sin(2 * np.pi * t / duration)
        def pos(t):
            return ('center', 'center')
        return clip.resize(zoom).rotate(lambda t: 2 * np.sin(2 * np.pi * t / duration)).set_position(pos)

    if effect_name == "depth_zoom":
        def zoom(t):
            return 1 + 0.3 * (t / duration)

        def pos(t):
            p = t / duration
            return (-w * 0.05 * p, -h * 0.05 * p)

        return clip.resize(zoom).set_position(pos)

    if effect_name == "ken_burns":
        def zoom(t):
            return 1 + 0.1 * (t / duration)

        def pos(t):
            p = t / duration
            return (-w * 0.02 * p, -h * 0.02 * p)

        return clip.resize(zoom).set_position(pos)

    if effect_name == "film_grain":
        def noise_frame(t):
            return (np.random.rand(h, w, 3) * 255).astype("uint8")

        grain = VideoClip(noise_frame, ismask=False).set_opacity(0.05).set_duration(duration)
        return CompositeVideoClip([clip, grain], size=size)

    if effect_name == "ripple":
        def smooth_vertical_ripple(get_frame, t):
            frame = get_frame(t)
            new_frame = np.copy(frame)
            band_height = int(0.8 * h)
            band_start = int(abs(np.sin(np.pi * t / duration)) * (h - band_height))

            for y in range(band_start, band_start + band_height):
                local_t = (y - band_start) / band_height
                strength = np.sin(np.pi * local_t) * np.sin(np.pi * t / duration)
                offset = int(np.sin(2 * np.pi * y / 60 + 3 * t) * strength * 10)
                for x in range(w):
                    src_x = np.clip(x + offset, 0, w - 1)
                    new_frame[y, x] = frame[y, src_x]

            return new_frame

        return clip.fl(smooth_vertical_ripple, apply_to=["video", "mask"]).set_duration(duration)

    if effect_name == "light_pulse":
        def cinematic_pulse(get_frame, t):
            frame = get_frame(t).astype("float32")

            # 🔁 Pulsing brightness: faster and more cinematic (2 cycles per duration)
            pulse = 0.9 + 0.1 * np.sin(4 * np.pi * t / duration)

            # 🌈 RGB color shift for mood (cool-warm oscillation)
            color_shift = np.array([
                1.0 + 0.05 * np.sin(2 * np.pi * t),   # Red
                1.0 + 0.03 * np.cos(2 * np.pi * t),   # Green
                1.0 + 0.04 * np.sin(2 * np.pi * t + np.pi / 2)  # Blue
            ]).reshape(1, 1, 3)

            # Apply pulse + color shift
            frame_shifted = frame * pulse * color_shift
            frame_shifted = np.clip(frame_shifted, 0, 255)

            # ✨ Bloom/Glow effect (soft blurred highlight)
            import cv2
            glow = (frame_shifted * 0.3).astype("uint8")
            glow = cv2.GaussianBlur(glow, (0, 0), sigmaX=4, sigmaY=4)

            enhanced = np.clip(frame_shifted + glow, 0, 255)

            return enhanced.astype("uint8")

        return clip.fl(cinematic_pulse, apply_to=["video", "mask"]).set_duration(duration)



    if effect_name == "parallax_pan":
        def pos(t):
            shift_x = -w * 0.01 * np.sin(np.pi * t / duration)
            shift_y = -h * 0.01 * np.cos(np.pi * t / duration)
            return (shift_x, shift_y)

        return clip.set_position(pos)

    if effect_name == "color_tint_shift":
        def tint_shift(get_frame, t):
            frame = get_frame(t).astype("float32")

            # Shift goes 0 → 1 → 0 across duration
            shift = 0.5 + 0.5 * np.sin(2 * np.pi * t / duration)

            # Target color to blend towards (cool blue here)
            target_color = np.array([100, 150, 255], dtype="float32")  # soft blue

            # Blend the original frame toward the target color
            tint = (1 - shift) * frame + shift * target_color
            return np.clip(tint, 0, 255).astype("uint8")

        return clip.fl(tint_shift, apply_to=["video", "mask"]).set_duration(duration)


    if effect_name == "wave_scan":
        def scan_mask(get_frame, t):
            frame = get_frame(t).astype("float32")
            h, w = frame.shape[:2]
            
            # Vertical coordinate normalized
            y = np.linspace(0, 1, h).reshape(-1, 1)
            
            # Dynamic pulse width (widen/narrow)
            pulse_variation = 0.01 + 0.005 * np.sin(2 * np.pi * t / duration)
            scan_pos = t / duration  # position of the scan wave
            band = np.exp(-((y - scan_pos) ** 2) / pulse_variation)

            # Flicker effect
            flicker = 0.85 + 0.15 * np.sin(8 * np.pi * t)
            scan_strength = band * 0.25 * flicker  # max +25% brightness with flicker

            # Expand to full frame
            scan_mask = np.repeat(scan_strength, w, axis=1)[:, :, None]

            # Tint color (bluish sci-fi)
            tint_color = np.array([180, 220, 255], dtype="float32")  # RGB
            frame_tinted = frame + (tint_color - frame) * scan_mask * 0.5
            enhanced = np.clip(frame_tinted * (1 + scan_mask), 0, 255)

            # --- Bloom/Glow effect ---
            glow = (frame * (scan_mask * 0.6)).astype("uint8")
            glow = cv2.GaussianBlur(glow, (0, 0), sigmaX=5, sigmaY=5)
            enhanced = np.clip(enhanced + glow, 0, 255)

            enhanced = convolve1d(enhanced, weights=[1, 2, 1], axis=0)
            enhanced = np.clip(enhanced / 4, 0, 255)

            return enhanced.astype("uint8")

        return clip.fl(scan_mask, apply_to=["video", "mask"]).set_duration(duration)

    return clip

def seamless_audio_loop(audio_path, duration, crossfade_ms=None):
    print(f"📥 Received request to loop audio: {audio_path}")
    print(f"⏱ Target duration: {duration:.2f} seconds")

    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"❌ Given music_path does not exist: {audio_path}")

    if not which("ffmpeg"):
        raise EnvironmentError("❌ ffmpeg not found — required for audio export. Install it and add to PATH.")

    print("✅ ffmpeg is available.")
    print("📖 Loading original audio...")
    original = AudioSegment.from_file(audio_path)
    print(f"🎵 Original duration: {len(original) / 1000:.2f} seconds")

    looped = AudioSegment.empty()
    original_len = len(original)

    if not crossfade_ms:
        crossfade_ms = min(300, int(original_len * 0.05))
    print(f"🔁 Using crossfade duration: {crossfade_ms} ms")

    print("🔄 Starting audio loop construction...")
    loop_count = 0
    while len(looped) < duration * 1000:
        loop_count += 1
        looped = looped + original if len(looped) == 0 else looped.append(original, crossfade=crossfade_ms)
    print(f"✅ Loop built with {loop_count} iteration(s), total length: {len(looped) / 1000:.2f} seconds")

    print("🎚 Applying fade-in and fade-out...")
    fade_duration = min(500, int(looped.duration_seconds * 100))
    print(f"🎧 Fade duration: {fade_duration} ms")
    looped = looped.fade_in(fade_duration).fade_out(fade_duration)

    temp_path = os.path.abspath("temp_looped_audio.mp3")
    print(f"💾 Exporting looped audio to: {temp_path}")

    try:
        looped.export(temp_path, format="mp3")
    except Exception as e:
        raise RuntimeError(f"❌ Export failed: {e}")

    if not os.path.exists(temp_path):
        raise FileNotFoundError(f"❌ Temp audio export failed at: {temp_path}")
    if os.path.getsize(temp_path) == 0:
        raise RuntimeError(f"❌ Exported file is empty: {temp_path}")

    print(f"✅ Looped audio successfully exported. Size: {os.path.getsize(temp_path)} bytes")
    return temp_path

def ffmpeg_safe_path(path):
    path = str(path)
    return f'"{path}"' if ' ' in path or '(' in path or ')' in path else path

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
            effect_name = image_effects[i].strip() if image_effects and i < len(image_effects) and image_effects[i].strip() else None
            if effect_name:
                img_clip = apply_image_effect(img_clip, effect_name, slide_duration, size)
                print(f"🖼 Slide {i}: Effect '{effect_name}' applied")
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

    temp_audio = None
    music_path = Path(music_path).resolve()
    if not music_path.exists():
        raise FileNotFoundError(f"❌ Path doesn't exist: {music_path}")
    
    if music_path:
        try:
            # Ensure music_path is a valid path string
            if isinstance(music_path, str):
                music_path = Path(music_path.strip('"').strip())
            else:
                music_path = Path(music_path)

            music_path = music_path.resolve()
            print(f"🎧 Creating looped audio from: {music_path}")

            if not music_path.exists():
                raise FileNotFoundError(f"❌ File does not exist: {music_path}")

            temp_audio = seamless_audio_loop(music_path, duration=final_video.duration)
            print(f"📁 Looped audio created at: {temp_audio}")

            audio = AudioFileClip(ffmpeg_safe_path(temp_audio))
            print(f"✅ Audio file exists: {os.path.exists(temp_audio)}")
            print(f"📏 Audio file size: {os.path.getsize(temp_audio)} bytes")
            final_video = final_video.set_audio(audio)
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
        
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)

