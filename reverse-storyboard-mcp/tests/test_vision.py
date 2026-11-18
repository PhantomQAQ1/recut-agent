"""Contract tests using a local transport fixture, never a paid model."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from reverse_storyboard import vision
from reverse_storyboard.models import Observation


class VisionTests(unittest.TestCase):
    def test_single_time_cannot_claim_motion(self):
        observed = Observation(confidence=0.9, action='向前走', camera_move='推', evidence_frames=[0])
        observed.enforce_evidence(3, 1)
        self.assertIsNone(observed.action)
        self.assertIsNone(observed.camera_move)
        with self.assertRaises(ValueError):
            Observation(confidence=0.5, evidence_frames=[3]).enforce_evidence(3, 2)

    def test_transport_validation_and_images(self):
        requests = []
        def handler(request):
            data = json.loads(request.content)
            requests.append(data)
            self.assertEqual(request.url.path, '/v1/chat/completions')
            if len(requests) == 1:
                content = '{}'
            else:
                content = json.dumps({'subject': '蓝色画面', 'confidence': 0.8, 'evidence_frames': [0, 1]})
            return httpx.Response(200, json={'choices': [{'message': {'content': content}}]})
        client_class = httpx.AsyncClient
        def client(**kwargs):
            return client_class(transport=httpx.MockTransport(handler), **kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / 'frame.jpg'
            image.write_bytes(b'fixture-jpeg')
            shot = {'id': 'shot_001', 'start': 0, 'end': 2,
                    'frames': [{'path': str(image), 'timestamp': 0}, {'path': str(image), 'timestamp': 1}]}
            env = {'STORYBOARD_VISION_BASE_URL': 'https://fixture.example/v1',
                   'STORYBOARD_VISION_MODEL': 'fixture', 'STORYBOARD_VISION_API_KEY': 'fixture-secret'}
            with patch.dict(os.environ, env), patch.object(vision.httpx, 'AsyncClient', client):
                result = asyncio.run(vision.analyze(shot))
        self.assertEqual(result['subject'], '蓝色画面')
        self.assertEqual(len(requests), 2)
        self.assertEqual(sum(c['type'] == 'image_url' for c in requests[0]['messages'][1]['content']), 2)

    def test_single_cited_frame_cannot_claim_motion(self):
        response = {'confidence': 0.9, 'evidence_frames': [0], 'action': '向前走', 'camera_move': '推镜'}
        client_class = httpx.AsyncClient
        def handler(request):
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(response)}}]})
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / 'frame.jpg'
            image.write_bytes(b'fixture')
            shot = {'id': 's', 'start': 0, 'end': 2, 'frames': [
                {'path': str(image), 'timestamp': 0}, {'path': str(image), 'timestamp': 1}]}
            env = {'STORYBOARD_VISION_BASE_URL': 'https://fixture.example/v1',
                   'STORYBOARD_VISION_MODEL': 'fixture', 'STORYBOARD_VISION_API_KEY': 'secret'}
            with patch.dict(os.environ, env), patch.object(vision.httpx, 'AsyncClient',
                    lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw)):
                result = asyncio.run(vision.analyze(shot))
        self.assertIsNone(result['action'])
        self.assertIsNone(result['camera_move'])

    def test_http_error_does_not_expose_response_body(self):
        def handler(request):
            return httpx.Response(401, text='DO_NOT_EXPOSE_SECRET')
        client_class = httpx.AsyncClient
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / 'frame.jpg'
            image.write_bytes(b'fixture')
            shot = {'id': 's', 'start': 0, 'end': 1, 'frames': [{'path': str(image), 'timestamp': 0}]}
            env = {'STORYBOARD_VISION_BASE_URL': 'https://fixture.example/v1',
                   'STORYBOARD_VISION_MODEL': 'fixture', 'STORYBOARD_VISION_API_KEY': 'secret'}
            with patch.dict(os.environ, env), patch.object(vision.httpx, 'AsyncClient',
                    lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw)):
                with self.assertRaisesRegex(RuntimeError, '^Vision endpoint returned HTTP 401$'):
                    asyncio.run(vision.analyze(shot))
