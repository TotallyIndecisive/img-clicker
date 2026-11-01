import io
import json
import urllib.error
from unittest.mock import patch

import imgc


class Response(io.BytesIO):
    pass


def version_file(version):
    return Response(f'[project]\nversion = "{version}"\n'.encode())


def setup_cache(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    monkeypatch.delenv('IMGC_NO_UPDATE_CHECK', raising=False)


def test_update_notice_and_cached_check(monkeypatch, tmp_path, capsys):
    setup_cache(monkeypatch, tmp_path)
    with patch('imgc.urllib.request.urlopen', return_value=version_file('1.2.0')) as request:
        imgc.check_for_updates()
        output = capsys.readouterr().err
        assert '1.2.0 is available' in output
        assert imgc.UPDATE_COMMAND in output
        imgc.check_for_updates()
        assert '1.2.0 is available' in capsys.readouterr().err
        request.assert_called_once()


def test_current_and_older_versions_do_not_notify(monkeypatch, tmp_path, capsys):
    setup_cache(monkeypatch, tmp_path)
    for version in (imgc.VERSION, '0.9.0'):
        imgc.update_cache_path().unlink(missing_ok=True)
        with patch('imgc.urllib.request.urlopen', return_value=version_file(version)):
            imgc.check_for_updates()
        assert capsys.readouterr().err == ''


def test_offline_and_bad_data_do_not_break_command(monkeypatch, tmp_path, capsys):
    setup_cache(monkeypatch, tmp_path)
    with patch('imgc.urllib.request.urlopen', side_effect=urllib.error.URLError('offline')) as request:
        imgc.check_for_updates()
        imgc.check_for_updates()
        request.assert_called_once()
    assert capsys.readouterr().err == ''
    imgc.update_cache_path().write_text('{invalid', encoding='utf-8')
    with patch('imgc.urllib.request.urlopen', return_value=Response(b'not toml')):
        imgc.check_for_updates()
    assert capsys.readouterr().err == ''


def test_cached_notice_survives_offline_retry(monkeypatch, tmp_path, capsys):
    setup_cache(monkeypatch, tmp_path)
    path = imgc.update_cache_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'checked_at': 0, 'latest': '9.0.0'}))
    with patch('imgc.urllib.request.urlopen', side_effect=TimeoutError()):
        imgc.check_for_updates()
    assert '9.0.0 is available' in capsys.readouterr().err


def test_disabled_and_help_integration(monkeypatch, tmp_path, capsys):
    setup_cache(monkeypatch, tmp_path)
    monkeypatch.setenv('IMGC_NO_UPDATE_CHECK', '1')
    with patch('imgc.urllib.request.urlopen') as request:
        imgc.check_for_updates()
    request.assert_not_called()
    monkeypatch.delenv('IMGC_NO_UPDATE_CHECK')
    with patch('imgc.urllib.request.urlopen', return_value=version_file('9.0.0')):
        monkeypatch.setattr('sys.argv', ['imgc', 'help'])
        assert imgc.cli() == 0
    captured = capsys.readouterr()
    assert '9.0.0 is available' in captured.err
    assert 'usage: imgc' in captured.out
