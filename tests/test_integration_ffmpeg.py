import unittest, tempfile, subprocess
from pathlib import Path
from unittest.mock import patch
from ytdubber.downloader import download_source
from ytdubber.tts import assemble_dub
from ytdubber.mixer import make_final_video
from ytdubber.utils import ffprobe_duration, WORK

class FFmpegIntegrationTests(unittest.TestCase):
    def test_local_video_extract_assemble_and_mix(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            src=d/'src.mp4'
            # Build a tiny real A/V file.
            subprocess.run([
                'ffmpeg','-y','-f','lavfi','-i','color=c=black:s=320x240:d=2:r=25',
                '-f','lavfi','-i','sine=frequency=220:duration=2','-shortest',
                '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)
            ],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            # Stage into a temp work dir: the real work/ belongs to live dub runs and
            # must not be written to (or cleaned up) by the test suite.
            with patch('ytdubber.downloader.WORK', d):
                video,audio=download_source(str(src))
            self.assertTrue(audio.exists())
            self.assertEqual(video.parent, d)
            # Two fake translated speech blocks.
            b1=d/'b1.wav'; b2=d/'b2.wav'
            for p,f in [(b1,440),(b2,660)]:
                subprocess.run(['ffmpeg','-y','-f','lavfi','-i',f'sine=frequency={f}:duration=0.4','-ar','24000',str(p)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            blocks=[
                {'id':1,'start':0.2,'end':0.6,'duration':0.4,'audio':str(b1)},
                {'id':2,'start':1.0,'end':1.4,'duration':0.4,'audio':str(b2)},
            ]
            dub=d/'dub.wav'; final=d/'final.mp4'
            assemble_dub(blocks,dub)
            make_final_video(video,dub,blocks,final,0.12)
            self.assertTrue(final.exists())
            self.assertGreater(ffprobe_duration(final),1.8)

if __name__ == '__main__': unittest.main()
