import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import imgc
from detector import centered_region


SCRIPT = Path(imgc.__file__).resolve()


def invoke(tmp_path, *args):
    env = os.environ.copy()
    env['XDG_CONFIG_HOME'] = str(tmp_path / 'config')
    env['XDG_DATA_HOME'] = str(tmp_path / 'data')
    return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, text=True, capture_output=True)


def test_setting_survives_separate_processes(tmp_path):
    assert '1160x650' in invoke(tmp_path, 'show').stdout
    result = invoke(tmp_path, 'set', 'res', '1920x1080')
    assert result.returncode == 0, result.stderr
    assert '1920x1080' in invoke(tmp_path, 'show').stdout
    assert json.loads((tmp_path / 'config/img-clicker/config.json').read_text())['resolution'] == [1920, 1080]
    assert invoke(tmp_path, 'set', 'res', '800X600').returncode == 0
    assert '800x600' in invoke(tmp_path, 'show').stdout


@pytest.mark.parametrize('value', ['0x1080', '1920x0', '-10x100', '100', '100x100x1', 'foo', '1.5x2'])
def test_invalid_settings_do_not_overwrite(tmp_path, value):
    assert invoke(tmp_path, 'set', 'res', '1200x700').returncode == 0
    result = invoke(tmp_path, 'set', 'res', value)
    assert result.returncode != 0
    assert '1200x700' in invoke(tmp_path, 'show').stdout


def test_help_includes_configuration(tmp_path):
    assert 'imgc set res 1920x1080' in invoke(tmp_path, 'help').stdout
    assert 'WIDTHxHEIGHT' in invoke(tmp_path, 'help', 'set').stdout or 'WIDTHxHEIGHT' in invoke(tmp_path, 'set', 'res', '--help').stdout
    assert 'saved' in invoke(tmp_path, 'help', 'start').stdout


def test_centered_calculation_for_custom_region():
    monitor = {'left': -1920, 'top': 100, 'width': 1920, 'height': 1080}
    assert centered_region(monitor, 1920, 1080) == monitor
    assert centered_region(monitor, 1000, 400) == {'left': -1460, 'top': 440, 'width': 1000, 'height': 400}
    with pytest.raises(ValueError, match='fit'):
        centered_region(monitor, 1921, 1080)


def test_start_uses_saved_and_per_run_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    imgc.save_resolution((1920, 1080))
    runner = Mock()
    monkeypatch.setitem(sys.modules, 'main', SimpleNamespace(find_target=Mock(return_value='target.png'), run=runner))
    monkeypatch.setattr(sys, 'argv', ['imgc', 'start', '--dry-run'])
    assert imgc.cli() == 0
    assert runner.call_args.kwargs['region_width'] == 1920
    assert runner.call_args.kwargs['region_height'] == 1080
    monkeypatch.setattr(sys, 'argv', ['imgc', 'start', '--dry-run', '--region-width', '800'])
    assert imgc.cli() == 0
    assert runner.call_args.kwargs['region_width'] == 800
    assert runner.call_args.kwargs['region_height'] == 1080
    assert imgc.get_resolution(imgc.read_config()) == (1920, 1080)


def test_config_errors_and_preserve_other_settings(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    path = imgc.config_path()
    path.parent.mkdir(parents=True)
    path.write_text('{"other": 42}', encoding='utf-8')
    imgc.save_resolution((800, 600))
    assert imgc.read_config() == {'other': 42, 'resolution': [800, 600]}
    path.write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError, match='Invalid configuration'):
        imgc.read_config()
    with pytest.raises(ValueError, match='Invalid resolution'):
        imgc.get_resolution({'resolution': [True, -1]})
