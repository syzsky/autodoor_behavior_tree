"""VLM 截图编码回归测试（真实文件读取，非 mock）

背景：0.03 之前 _encode_image 存在"只读前 16 字节魔数、其余按 f.read() 续读"
的实现，导致上传给 VLM 的 base64 为残缺数据，模型无法解码图像，
生成坐标随机不可复现。当时相关测试均 mock 掉 _encode_image，未能拦截。

本文件用真实 PNG/JPEG/BMP/WEBP 字节流验证：
1. 返回的 base64 解码后必须与磁盘文件内容逐字节一致（全量数据）
2. MIME 探测必须基于真实魔数，而非文件扩展名
3. 读取失败时抛出 VLMAnalysisError 且信息包含路径
"""
import base64

import pytest

from bt_cli.ai.vlm_analyzer import VLMAnalyzer, VLMAnalysisError

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
BMP_MAGIC = b"BM"
WEBP_MAGIC = b"RIFF....WEBP"


def _make_file(tmp_path, name, head, body_size=256):
    p = tmp_path / name
    p.write_bytes(head + bytes(body_size))  # 魔数 + 任意主体数据
    return p


class TestEncodeImageFullData:
    """全量数据断言：解码后的 base64 必须等于原始文件字节"""

    def test_png_full_data(self, tmp_path):
        p = _make_file(tmp_path, "shot.png", PNG_MAGIC)
        mime, b64 = VLMAnalyzer()._encode_image(str(p))
        assert base64.b64decode(b64) == p.read_bytes()

    def test_jpeg_full_data(self, tmp_path):
        p = _make_file(tmp_path, "shot.jpg", JPEG_MAGIC)
        mime, b64 = VLMAnalyzer()._encode_image(str(p))
        assert base64.b64decode(b64) == p.read_bytes()
        assert mime == "image/jpeg"

    def test_bmp_full_data(self, tmp_path):
        p = _make_file(tmp_path, "shot.bmp", BMP_MAGIC)
        mime, b64 = VLMAnalyzer()._encode_image(str(p))
        assert base64.b64decode(b64) == p.read_bytes()
        assert mime == "image/bmp"

    def test_webp_full_data(self, tmp_path):
        p = _make_file(tmp_path, "shot.webp", WEBP_MAGIC)
        mime, b64 = VLMAnalyzer()._encode_image(str(p))
        assert base64.b64decode(b64) == p.read_bytes()
        assert mime == "image/webp"

    def test_unknown_magic_falls_back_to_png(self, tmp_path):
        p = _make_file(tmp_path, "shot.bin", b"\x00\x01\x02\x03")
        mime, b64 = VLMAnalyzer()._encode_image(str(p))
        assert mime == "image/png"
        assert base64.b64decode(b64) == p.read_bytes()


class TestEncodeImageErrors:
    """错误路径：文件不存在 / 不可读"""

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(VLMAnalysisError) as ei:
            VLMAnalyzer()._encode_image(str(tmp_path / "not_exist.png"))
        assert "not_exist.png" in str(ei.value)


class TestDetectMime:
    """魔数探测独立验证"""

    @pytest.mark.parametrize("head,expected", [
        (JPEG_MAGIC, "image/jpeg"),
        (PNG_MAGIC, "image/png"),
        (WEBP_MAGIC, "image/webp"),
        (BMP_MAGIC, "image/bmp"),
        (b"GIF89a", "image/png"),  # 未知魔数回退 png
    ])
    def test_detect(self, head, expected):
        assert VLMAnalyzer._detect_mime(head) == expected
