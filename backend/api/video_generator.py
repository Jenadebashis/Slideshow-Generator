import os
import random
import gc
from moviepy.editor import *
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout
from moviepy.video.fx.colorx import colorx
from moviepy.audio.fx.audio_loop import audio_loop
from moviepy.config import change_settings

change_settings({
    "IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"
})

def apply_image_transition(clip1, clip2, duration=1):
    return concatenate_videoclips([
        clip1.crossfadeout(duration),
        clip2.crossfadein(duration)
    ], method="compose")

def generate_video(texts, image_paths, music_path, output_path, duration_per_slide=4, size=(720, 1280)):
    slides = []

    for i, text in enumerate(texts):
        image_path = image_paths[i % len(image_paths)]

        # Resize to fill height, then crop to center width
        img_clip = ImageClip(image_path).resize(height=size[1])
        img_clip = img_clip.crop(
            width=size[0], height=size[1],
            x_center=img_clip.w / 2, y_center=img_clip.h / 2
        ).set_duration(duration_per_slide)

        img_clip = colorx(img_clip, 0.4)  # Darken image for text focus

        txt_clip = TextClip(text, fontsize=40, color='white', size=size, method='caption') \
            .set_duration(duration_per_slide) \
            .set_position('center')

        slide = CompositeVideoClip([img_clip, txt_clip], size=size)
        slides.append(slide)

    if not slides:
        raise ValueError("No slides generated: check texts and image paths.")

    final_video = slides[0]
    for i in range(1, len(slides)):
        final_video = apply_image_transition(final_video, slides[i], duration=0.3)

    if music_path:
        audio = AudioFileClip(music_path)
        final_video = final_video.set_audio(audio_loop(audio, duration=final_video.duration))

    try:
        final_video.write_videofile(
            output_path,
            fps=24,
            audio=True,
            remove_temp=True,
            threads=4,
            logger=None
        )
    finally:
        if hasattr(final_video.audio, 'close'):
            try:
                final_video.audio.close()
            except:
                pass
        del final_video
        gc.collect()
