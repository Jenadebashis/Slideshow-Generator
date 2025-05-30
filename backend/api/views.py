from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import FileResponse, Http404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import os
from .video_generator import generate_video

@api_view(['POST'])
def create_slideshow(request):
    try:
        print("🔄 [START] Received POST request to create slideshow.")

        texts = request.data.getlist('texts')
        positions = request.data.getlist('positions')  # Same length as texts
        duration = int(request.data.get('duration', 4))
        images = request.FILES.getlist('images')
        darkening = float(request.data.get('darkening')) 
        music = request.FILES.get('music')

        print(f"📝 Texts received: {len(texts)}")
        print(f"🖼 Images received: {len(images)}")
        print(f"🎵 Music file received: {'Yes' if music else 'No'}")
        print(f"⏱ Duration per slide: {duration} seconds")

        if not texts or not images:
            print("❌ Missing texts or images.")
            return Response({"error": "Texts and images are required."}, status=400)

        image_paths = []
        for image in images:
            path = default_storage.save(f"media/{image.name}", ContentFile(image.read()))
            full_path = os.path.join(settings.MEDIA_ROOT, path)
            image_paths.append(full_path)
            print(f"✅ Image saved: {full_path}")

        music_path = None
        if music:
            music_path = os.path.join(settings.MEDIA_ROOT, default_storage.save(f"media/{music.name}", ContentFile(music.read())))
            print(f"🎶 Music saved: {music_path}")

        output_path = os.path.join(settings.MEDIA_ROOT, "final_video.mp4")
        print("⚙️ Calling generate_video function...")
        generate_video(texts, image_paths, music_path, output_path, duration_per_slide=duration, positions=positions, darkening=darkening)

        if not os.path.exists(output_path):
            print("❌ Video file was not created!")
            raise Http404("Video file not found.")

        print(f"📦 Video generated successfully: {output_path}")
        print("📤 Sending FileResponse with video...")

        filename = f"{texts[0][:20].strip().replace(' ', '_')}.mp4"
        print(f"📦 filename generated successfully: {filename}")
        return FileResponse(open(output_path, 'rb'), as_attachment=True, filename=filename, content_type='video/mp4')

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"🔥 Exception occurred: {str(e)}")
        return Response({"error": "Internal server error: " + str(e)}, status=500)
