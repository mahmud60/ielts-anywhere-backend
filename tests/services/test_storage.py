import pytest
from unittest.mock import patch, MagicMock
from app.services.storage import upload_audio, delete_audio, get_r2_client
from app.core.config import settings

@patch("app.services.storage.boto3.client")
def test_get_r2_client(mock_boto_client):
    get_r2_client()
    assert mock_boto_client.called
    args, kwargs = mock_boto_client.call_args
    assert args[0] == "s3"
    assert "r2.cloudflarestorage.com" in kwargs["endpoint_url"]

@patch("app.services.storage.get_r2_client")
def test_upload_audio(mock_get_client):
    mock_s3 = MagicMock()
    mock_get_client.return_value = mock_s3

    with patch.object(settings, "R2_PUBLIC_URL", "https://pub.url"):
        url = upload_audio(b"fake_bytes", "test.mp3")
        assert url.startswith("https://pub.url/audio/")
        assert url.endswith(".mp3")
        assert mock_s3.put_object.called

@patch("app.services.storage.get_r2_client")
def test_delete_audio(mock_get_client):
    mock_s3 = MagicMock()
    mock_get_client.return_value = mock_s3

    with patch.object(settings, "R2_PUBLIC_URL", "https://pub.url"):
        delete_audio("https://pub.url/audio/test.mp3")
        assert mock_s3.delete_object.called
        args, kwargs = mock_s3.delete_object.call_args
        assert kwargs["Key"] == "audio/test.mp3"

def test_delete_audio_invalid_url():
    with patch("app.services.storage.get_r2_client") as mock_get_client:
        delete_audio("")
        assert not mock_get_client.called
