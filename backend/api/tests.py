from django.test import TestCase
from django.conf import settings
from unittest.mock import patch
import os

from .video_generator import generate_video


class VideoGeneratorTests(TestCase):
    @patch('moviepy.video.VideoClip.VideoClip.write_videofile')
    def test_generate_video_with_image_effect(self, mock_write):
        image_path = os.path.join(settings.BASE_DIR, 'media', 'pic 10.webp')
        if not os.path.exists(image_path):
            self.skipTest('Sample image not found')
        generate_video(
            ['hello'],
            [image_path],
            None,
            'out.mp4',
            durations=[1],
            image_effects=['ken_burns'],
        )
        self.assertTrue(mock_write.called)
