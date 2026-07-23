import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(__file__))
import _bootstrap  # noqa: F401
import fixtures
from wr import credential, nodes, upload_client, video_save


class FakeVideo:
    """A stand-in for a concrete ComfyUI VIDEO type (has ``save_to``)."""

    def __init__(self):
        self.saved = None

    def save_to(self, path, format=None, codec=None, metadata=None):
        self.saved = {"format": format, "codec": codec, "metadata": metadata}
        with open(path, "wb") as fh:
            fh.write(b"FAKEMP4BYTES")


class BaseVideoNoSaveTo:
    """A stand-in for the base VideoInput (no ``save_to`` — version floor)."""


class VideoMetadataShapeTests(unittest.TestCase):
    def test_metadata_puts_workflow_at_top_level_like_savevideo(self):
        # ComfyUI's SaveVideo does metadata.update(extra_pnginfo) then
        # metadata["prompt"]=prompt, and save_to writes each TOP-LEVEL key as a
        # container tag. Numonic's server-side video extractor scans for
        # top-level `workflow` + `prompt`; a nested {"extra_pnginfo": {...}}
        # would bury `workflow` and break extraction.
        prompt = fixtures.sample_prompt()
        extra = {"workflow": fixtures.sample_workflow()}
        meta = video_save.build_video_metadata(prompt, extra)
        self.assertIn("workflow", meta)
        self.assertIn("prompt", meta)
        self.assertNotIn("extra_pnginfo", meta)
        self.assertEqual(meta["workflow"]["last_node_id"], 12)

    def test_no_metadata_is_none(self):
        self.assertIsNone(video_save.build_video_metadata(None, None))

    def test_prompt_only_and_workflow_only(self):
        self.assertEqual(
            video_save.build_video_metadata({"a": 1}, None), {"prompt": {"a": 1}}
        )
        self.assertEqual(
            video_save.build_video_metadata(None, {"workflow": {"b": 2}}),
            {"workflow": {"b": 2}},
        )


class SaveVideoToTmpTests(unittest.TestCase):
    def test_encodes_to_tmp_and_passes_top_level_metadata(self):
        video = FakeVideo()
        path, mime = video_save.save_video_to_tmp(
            video,
            prompt=fixtures.sample_prompt(),
            extra_pnginfo={"workflow": fixtures.sample_workflow()},
            fmt="auto",
        )
        try:
            self.assertTrue(os.path.exists(path))
            self.assertEqual(mime, "video/mp4")
            # The metadata handed to save_to has top-level workflow + prompt.
            self.assertIn("workflow", video.saved["metadata"])
            self.assertIn("prompt", video.saved["metadata"])
        finally:
            video_save._safe_unlink(path)

    def test_missing_save_to_fails_loudly(self):
        with self.assertRaises(video_save.VideoUnsupportedError) as ctx:
            video_save.save_video_to_tmp(BaseVideoNoSaveTo())
        self.assertIn("Update ComfyUI", str(ctx.exception))

    def test_tmp_removed_if_save_to_raises(self):
        class Boom:
            def save_to(self, path, **kw):
                raise RuntimeError("encode failed")

        with self.assertRaises(RuntimeError):
            video_save.save_video_to_tmp(Boom())
        # No temp file should be left behind (cleaned in the except path).


class SaveVideoNodeTests(unittest.TestCase):
    def setUp(self):
        self._saved_key = os.environ.get(credential.API_KEY_ENV)
        os.environ[credential.API_KEY_ENV] = "napi_test"

    def tearDown(self):
        if self._saved_key is None:
            os.environ.pop(credential.API_KEY_ENV, None)
        else:
            os.environ[credential.API_KEY_ENV] = self._saved_key

    def test_end_to_end_uploads_and_deletes_temp(self):
        holder = {}
        real = video_save.save_video_to_tmp

        def spy(*args, **kwargs):
            path, mime = real(*args, **kwargs)
            holder["path"] = path
            return path, mime

        captured = {}

        def fake_upload(data, filename, mime_type, title=None, **kw):
            captured["data"] = data
            captured["mime"] = mime_type
            return {"gallery_url": "https://numonic.ai/app/assets/vid1"}

        with mock.patch.object(video_save, "save_video_to_tmp", spy), \
             mock.patch.object(nodes.video_save, "save_video_to_tmp", spy), \
             mock.patch.object(upload_client, "upload_asset", fake_upload), \
             mock.patch.object(nodes.upload_client, "upload_asset", fake_upload):
            out = nodes.SaveVideoToNumonic().save(
                FakeVideo(),
                prompt=fixtures.sample_prompt(),
                extra_pnginfo={"workflow": fixtures.sample_workflow()},
            )

        self.assertEqual(out["result"], ("https://numonic.ai/app/assets/vid1",))
        self.assertEqual(captured["data"], b"FAKEMP4BYTES")
        self.assertEqual(captured["mime"], "video/mp4")
        # the transient temp file is deleted after upload.
        self.assertFalse(os.path.exists(holder["path"]))

    def test_version_floor_surfaces_as_runtime_error(self):
        with self.assertRaises(RuntimeError) as ctx:
            nodes.SaveVideoToNumonic().save(BaseVideoNoSaveTo())
        self.assertIn("Update ComfyUI", str(ctx.exception))


class SaveImageNodeTests(unittest.TestCase):
    def setUp(self):
        self._saved_key = os.environ.get(credential.API_KEY_ENV)
        os.environ[credential.API_KEY_ENV] = "napi_test"

    def tearDown(self):
        if self._saved_key is None:
            os.environ.pop(credential.API_KEY_ENV, None)
        else:
            os.environ[credential.API_KEY_ENV] = self._saved_key

    def test_end_to_end_encodes_and_uploads_each_image(self):
        calls = []

        def fake_encode(image, prompt=None, extra_pnginfo=None):
            return b"PNG:" + bytes([image])

        def fake_upload(data, filename, mime_type, title=None, **kw):
            calls.append((data, mime_type, filename))
            return {"gallery_url": "https://numonic.ai/app/assets/%s" % filename}

        with mock.patch.object(nodes.image_encode, "tensor_to_png_bytes", fake_encode), \
             mock.patch.object(nodes.upload_client, "upload_asset", fake_upload):
            out = nodes.SaveImageToNumonic().save([1, 2])

        self.assertEqual(len(calls), 2)  # one upload per image in the batch
        self.assertEqual(calls[0][1], "image/png")
        self.assertTrue(out["result"][0].startswith("https://numonic.ai/app/assets/"))

    def test_missing_credential_raises_with_setup_guidance(self):
        os.environ.pop(credential.API_KEY_ENV, None)
        import tempfile

        saved_home = os.environ.get("HOME")
        os.environ["HOME"] = tempfile.mkdtemp()
        try:
            with self.assertRaises(credential.MissingCredentialError) as ctx:
                nodes.SaveImageToNumonic().save([1])
            self.assertIn("NUMONIC_API_KEY", str(ctx.exception))
        finally:
            if saved_home is not None:
                os.environ["HOME"] = saved_home


if __name__ == "__main__":
    unittest.main()
