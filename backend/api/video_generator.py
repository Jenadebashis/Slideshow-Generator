import os
import random
import gc
from moviepy.editor import *
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout
from moviepy.video.fx.colorx import colorx
from moviepy.audio.fx.audio_loop import audio_loop
from moviepy.config import change_settings
from moviepy.video.fx import all as vfx

change_settings({
    "IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"
})

TRANSITION_DURATION = 0.3  # seconds for crossfades and text fades

TEXT_TRANSITIONS = [
    "fade",
    "slide_left",
    "slide_right",
    "slide_top",
    "slide_bottom",
    "zoom",
]

def apply_text_transition(clip, transition, duration):
    """Apply one of several animation effects to a text clip."""
    if transition == "fade":
        return clip.fx(fadein, duration).fx(fadeout, duration)
    if transition.startswith("slide_"):
        side = transition.split("_")[1]
        clip = clip.fx(vfx.slide_in, duration, side=side)
        return clip.fx(vfx.slide_out, duration, side=side)
    if transition == "zoom":
        def resize(t):
            if t < duration:
                return 0.3 + 0.7 * (t / duration)
            if t > clip.duration - duration:
                return 0.3 + 0.7 * (max(clip.duration - t, 0) / duration)
            return 1.0
        return clip.resize(resize)
    # Fallback
    return clip

def apply_image_transition(clip1, clip2, duration=TRANSITION_DURATION):
    return concatenate_videoclips([
        clip1.crossfadeout(duration),
        clip2.crossfadein(duration)
    ], method="compose")

def generate_video(texts, image_paths, music_path, output_path, duration_per_slide=4, size=(720, 1280), positions=None, durations=None, darkening=None):
    if positions is None:
        positions = []
    slides = []

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


        try:
            percent = float(position_percent)
            y_pos = int(size[1] * percent / 100.0)
            y_pos = max(40, min(y_pos, size[1] - 100))  # Clamp
            text_position = ('center', y_pos)
        except Exception as e:
            print(f"Invalid position: {e}")
            text_position = 'center'
        try:
            transition_name = available_transitions.pop() if available_transitions else random.choice(TEXT_TRANSITIONS)
            txt_clip = (
                TextClip(
                    text,
                    fontsize=40,
                    color='white',
                    font="Arial",  # or your font path
                    method='caption',
                    size=(size[0] - 100, None),
                    align='center'
                )
                .set_duration(slide_duration)
                .set_position(text_position)
            )
            txt_clip = apply_text_transition(txt_clip, transition_name, TRANSITION_DURATION)
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

        slide = CompositeVideoClip([img_clip, txt_clip], size=size)
        slides.append(slide)
        print(f"✅ Slide {i} composed successfully.\n")

    if not slides:
        raise ValueError("No slides generated: check texts and image paths.")

    final_video = slides[0]
    for i in range(1, len(slides)):
        final_video = apply_image_transition(final_video, slides[i], duration=TRANSITION_DURATION)

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
