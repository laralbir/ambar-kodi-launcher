import os

from ambar.application.skins import SkinService


def test_list_skins_empty_when_dir_missing(tmp_path):
    service = SkinService(str(tmp_path / "does-not-exist"))

    assert service.list_skins() == []


def test_list_skins_finds_folders_with_style_css(tmp_path):
    os.makedirs(tmp_path / "vaporwave")
    (tmp_path / "vaporwave" / "style.css").write_text("body{}")
    os.makedirs(tmp_path / "incomplete")  # sin style.css, no cuenta

    service = SkinService(str(tmp_path))

    assert service.list_skins() == ["vaporwave"]
