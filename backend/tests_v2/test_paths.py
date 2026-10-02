"""Phase A: path resolution for development and future frozen (packaged) mode.

Key isolation note
------------------
``app2.config`` resolves ``DATA_DIR``/``DB_PATH``/``BACKUP_DIR`` at **import
time** (module-level constants).  Setting ``sys.frozen`` alone therefore does
nothing: the module must be *re-imported* for a new resolution to happen, and
any module holding a reference to the old values (notably ``app2.db``, which
builds its engine from ``config.DB_URL`` at import time) would keep using them.

So these tests drive the pure helpers (``is_frozen``, ``bundle_dir``,
``user_data_dir``, ``static_dir``) directly with monkeypatching, and use a
**subprocess** for the cases that must observe genuinely fresh module-level
state.  Every test works in a temporary directory; the real project databases
are never opened.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app2 import config

BACKEND_DIR = Path(__file__).resolve().parents[1]
BUNDLED_INDEX = "index.html"


def _run_python(code: str, env_overrides: dict[str, str]) -> str:
    """Run a snippet in a *fresh* interpreter with an isolated environment.

    ``TRADEQUEST2_*`` variables inherited from the pytest process (conftest
    points the v2 suite at a temporary database) are stripped first, so each
    snippet starts from the documented defaults unless it opts in explicitly.
    """
    env = os.environ.copy()
    for name in list(env):
        if name.startswith("TRADEQUEST2_"):
            del env[name]
    env.update(env_overrides)
    env["PYTHONPATH"] = str(BACKEND_DIR)
    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"snippet failed:\n{proc.stdout}\n{proc.stderr}"
    return proc.stdout


def _value(text: str, key: str) -> str:
    for line in text.splitlines():
        if line.startswith(key + " "):
            return line[len(key) + 1:].strip()
    raise AssertionError(f"{key} not found in output:\n{text}")


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _bundle_files(bundle: Path) -> list[Path]:
    """Files in the simulated bundle, ignoring the fixture's own index.html."""
    return [p for p in bundle.rglob("*") if p.is_file() and p.name != BUNDLED_INDEX]


@pytest.fixture()
def frozen_env(tmp_path):
    """Simulated frozen runtime: a disposable bundle + a per-user data dir."""
    bundle = tmp_path / "_MEIPASS"
    (bundle / "frontend_v2" / "dist" / "assets").mkdir(parents=True)
    (bundle / "frontend_v2" / "dist" / BUNDLED_INDEX).write_text(
        "<html>frozen</html>", encoding="utf-8"
    )
    localapp = tmp_path / "LocalAppData"
    localapp.mkdir()
    return {"bundle": bundle, "localappdata": localapp}


def _simulate_frozen(monkeypatch, frozen_env):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(frozen_env["bundle"]), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(frozen_env["localappdata"]))
    monkeypatch.delenv("TRADEQUEST2_STATIC_DIR", raising=False)


# ==========================================================================
# 1. development mode resolves exactly what it did before Phase A
# ==========================================================================
# ==========================================================================
# 2/3. frozen mode: assets from the bundle, writable data outside it
# ==========================================================================
def test_frozen_assets_resolve_from_bundle(frozen_env, monkeypatch):
    _simulate_frozen(monkeypatch, frozen_env)
    assert config.is_frozen() is True
    assert config.bundle_dir() == frozen_env["bundle"]
    # read-only assets come from the bundle ...
    assert config.static_dir() == frozen_env["bundle"] / "frontend_v2" / "dist"
    # ... while writable data goes to the per-user directory
    assert config.user_data_dir() == frozen_env["localappdata"] / "TradeQuest"


def test_frozen_bundle_dir_without_meipass_uses_executable(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    assert config.bundle_dir() == Path(sys.executable).resolve().parent


def test_frozen_module_level_paths_outside_bundle(frozen_env):
    """A fresh interpreter must resolve writable paths outside the bundle."""
    out = _run_python(
        """
        import sys, os
        sys.frozen = True
        sys._MEIPASS = os.environ["FAKE_MEIPASS"]
        from app2 import config
        print("DATA_DIR", config.DATA_DIR)
        print("DB_PATH", config.DB_PATH)
        print("BACKUP_DIR", config.BACKUP_DIR)
        print("STATIC", config.static_dir())
        print("HOST", config.HOST)
        """,
        {
            "FAKE_MEIPASS": str(frozen_env["bundle"]),
            "LOCALAPPDATA": str(frozen_env["localappdata"]),
        },
    )
    user_root = frozen_env["localappdata"] / "TradeQuest"
    assert Path(_value(out, "DATA_DIR")) == user_root
    assert Path(_value(out, "DB_PATH")) == user_root / "tradequest_v2.db"
    assert Path(_value(out, "BACKUP_DIR")) == user_root / "backups"
    assert Path(_value(out, "STATIC")) == frozen_env["bundle"] / "frontend_v2" / "dist"
    assert _value(out, "HOST") == "127.0.0.1"


def test_frozen_writable_paths_outside_bundle_and_install(frozen_env):
    """4. DB and backups must never live in the bundle or install directory."""
    out = _run_python(
        """
        import sys, os
        sys.frozen = True
        sys._MEIPASS = os.environ["FAKE_MEIPASS"]
        from app2 import config
        print("DATA_DIR", config.DATA_DIR)
        print("DB_PATH", config.DB_PATH)
        print("BACKUP_DIR", config.BACKUP_DIR)
        """,
        {
            "FAKE_MEIPASS": str(frozen_env["bundle"]),
            "LOCALAPPDATA": str(frozen_env["localappdata"]),
        },
    )
    bundle = frozen_env["bundle"]
    install = frozen_env["localappdata"].parent / "ProgramFiles" / "TradeQuest"
    for key in ("DATA_DIR", "DB_PATH", "BACKUP_DIR"):
        path = Path(_value(out, key))
        assert not _is_within(path, bundle), f"{key} inside bundle"
        assert not _is_within(path, install), f"{key} inside install dir"


# ==========================================================================
# 5. a fresh database is created only in a disposable directory
# ==========================================================================
def test_frozen_initialize_db_creates_db_in_user_dir_only(frozen_env):
    out = _run_python(
        """
        import sys, os
        sys.frozen = True
        sys._MEIPASS = os.environ["FAKE_MEIPASS"]
        import app2.models  # noqa: F401  (registers tables for create_all)
        from app2.db import initialize_db
        print("FRESH", initialize_db())
        from app2 import config
        print("DB_PATH", config.DB_PATH)
        print("DB_EXISTS", config.DB_PATH.is_file())
        print("BACKUPS_EXISTS", config.BACKUP_DIR.is_dir())
        """,
        {
            "FAKE_MEIPASS": str(frozen_env["bundle"]),
            "LOCALAPPDATA": str(frozen_env["localappdata"]),
        },
    )
    assert _value(out, "FRESH") == "True"
    assert _value(out, "DB_EXISTS") == "True"
    assert _value(out, "BACKUPS_EXISTS") == "True"
    expected = frozen_env["localappdata"] / "TradeQuest" / "tradequest_v2.db"
    assert Path(_value(out, "DB_PATH")) == expected
    assert expected.is_file()
    assert _bundle_files(frozen_env["bundle"]) == []


def test_development_initialize_db_uses_disposable_dir(tmp_path):
    """With TRADEQUEST2_DB set, initialisation only touches that directory."""
    target = tmp_path / "sub" / "journal.db"
    out = _run_python(
        """
        import app2.models  # noqa: F401  (registers tables for create_all)
        from app2.db import initialize_db
        print("FRESH", initialize_db())
        from app2 import config
        print("DB_PATH", config.DB_PATH)
        print("DB_EXISTS", config.DB_PATH.is_file())
        """,
        {"TRADEQUEST2_DB": str(target)},
    )
    assert _value(out, "FRESH") == "True"
    assert Path(_value(out, "DB_PATH")) == target.resolve()
    assert target.is_file()
def test_development_mode_paths_unchanged():
    # NOTE: tests_v2/conftest.py sets TRADEQUEST2_DB to a temporary database
    # *before* app2.config is imported, so the module-level DB_PATH in this
    # process is intentionally the throw-away one.  PROJECT_ROOT / DATA_DIR /
    # static_dir / HOST are unaffected by that override and are asserted
    # in-process; the DB defaults are asserted in a clean subprocess below.
    assert config.is_frozen() is False
    assert config.bundle_dir() is None
    assert config.PROJECT_ROOT == Path(config.__file__).resolve().parents[2]
    assert config.DATA_DIR == config.PROJECT_ROOT / "data"
    assert config.static_dir() == config.PROJECT_ROOT / "frontend_v2" / "dist"


def test_development_mode_default_database_paths():
    """With no env overrides, dev mode keeps <project>/data as before Phase A."""
    out = _run_python(
        """
        from app2 import config
        print("DATA_DIR", config.DATA_DIR)
        print("DB_PATH", config.DB_PATH)
        print("DB_URL", config.DB_URL)
        print("BACKUP_DIR", config.BACKUP_DIR)
        """,
        {},
    )
    project_root = BACKEND_DIR.parent
    assert Path(_value(out, "DATA_DIR")) == project_root / "data"
    assert Path(_value(out, "DB_PATH")) == project_root / "data" / "tradequest_v2.db"
    assert Path(_value(out, "BACKUP_DIR")) == project_root / "data" / "backups"
    # the DB itself is never opened here - only paths are printed


def test_development_data_dir_stays_inside_project():
    assert _is_within(config.DATA_DIR, config.PROJECT_ROOT)


def test_backend_stays_loopback_only():
    assert config.HOST == "127.0.0.1"
# ==========================================================================
# 6. environment-variable overrides behave as documented
# ==========================================================================
def test_db_override_wins_in_development(tmp_path):
    target = tmp_path / "custom.db"
    out = _run_python(
        """
        from app2 import config
        print("DB_PATH", config.DB_PATH)
        print("DB_URL", config.DB_URL)
        print("BACKUP_DIR", config.BACKUP_DIR)
        """,
        {"TRADEQUEST2_DB": str(target), "TRADEQUEST2_DB_URL": ""},
    )
    assert Path(_value(out, "DB_PATH")) == target.resolve()
    assert _value(out, "DB_URL") == f"sqlite:///{target.resolve()}"
    assert Path(_value(out, "BACKUP_DIR")) == target.resolve().parent / "backups"


def test_db_url_override_wins_over_db_path(tmp_path):
    url = "sqlite:///" + (tmp_path / "url.db").as_posix().lstrip("/")
    out = _run_python(
        """
        from app2 import config
        print("DB_URL", config.DB_URL)
        """,
        {"TRADEQUEST2_DB_URL": url, "TRADEQUEST2_DB": str(tmp_path / "p.db")},
    )
    assert _value(out, "DB_URL") == url


def test_db_override_still_wins_in_frozen_mode(frozen_env, tmp_path):
    target = tmp_path / "frozen-custom.db"
    out = _run_python(
        """
        import sys, os
        sys.frozen = True
        sys._MEIPASS = os.environ["FAKE_MEIPASS"]
        from app2 import config
        print("DB_PATH", config.DB_PATH)
        print("BACKUP_DIR", config.BACKUP_DIR)
        """,
        {
            "FAKE_MEIPASS": str(frozen_env["bundle"]),
            "LOCALAPPDATA": str(frozen_env["localappdata"]),
            "TRADEQUEST2_DB": str(target),
        },
    )
    assert Path(_value(out, "DB_PATH")) == target.resolve()
    assert Path(_value(out, "BACKUP_DIR")) == target.resolve().parent / "backups"


def test_static_dir_override_wins_in_frozen_mode(frozen_env, monkeypatch, tmp_path):
    custom = tmp_path / "custom-dist"
    custom.mkdir()
    _simulate_frozen(monkeypatch, frozen_env)
    monkeypatch.setenv("TRADEQUEST2_STATIC_DIR", str(custom))
    assert config.static_dir() == custom.resolve()


def test_blank_static_dir_override_uses_mode_default(frozen_env, monkeypatch):
    _simulate_frozen(monkeypatch, frozen_env)
    monkeypatch.setenv("TRADEQUEST2_STATIC_DIR", "   ")
    assert config.static_dir() == frozen_env["bundle"] / "frontend_v2" / "dist"


def test_static_dir_override_works_in_development(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv("TRADEQUEST2_STATIC_DIR", str(tmp_path))
    assert config.static_dir() == tmp_path.resolve()


def test_screenshot_dirs_still_read_at_call_time(monkeypatch, tmp_path):
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS",
                       f"{tmp_path}{os.pathsep}C:/other")
    assert config.screenshot_allowed_dirs() == [str(tmp_path), "C:/other"]


def test_blank_screenshot_dirs_fails_closed(monkeypatch):
    monkeypatch.setenv("TRADEQUEST2_SCREENSHOT_DIRS", "")
    assert config.screenshot_allowed_dirs() == []


# ==========================================================================
# 7. a missing or invalid user-data location fails loudly and safely
# ==========================================================================
@pytest.mark.parametrize("bad", ["", "   "])
def test_missing_localappdata_raises_actionable_error(frozen_env, monkeypatch, bad):
    _simulate_frozen(monkeypatch, frozen_env)
    monkeypatch.setenv("LOCALAPPDATA", bad)
    with pytest.raises(config.ConfigError) as excinfo:
        config.user_data_dir()
    message = str(excinfo.value)
    assert "LOCALAPPDATA" in message
    assert "TRADEQUEST2_DB" in message  # actionable escape hatch


def test_relative_localappdata_is_rejected(frozen_env, monkeypatch):
    _simulate_frozen(monkeypatch, frozen_env)
    monkeypatch.setenv("LOCALAPPDATA", "relative/AppData")
    with pytest.raises(config.ConfigError) as excinfo:
        config.user_data_dir()
    assert "absolute" in str(excinfo.value)


def test_startup_without_localappdata_aborts_without_writing(frozen_env):
    """A frozen start with no LOCALAPPDATA must abort, not create a temp DB."""
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys\n"
         "sys.frozen = True\n"
         f"sys._MEIPASS = {str(frozen_env['bundle'])!r}\n"
         "from app2 import config\n"],
        cwd=str(BACKEND_DIR),
        env={**os.environ, "PYTHONPATH": str(BACKEND_DIR), "LOCALAPPDATA": ""},
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode != 0
    assert "ConfigError" in proc.stderr
    assert "LOCALAPPDATA" in proc.stderr
    assert _bundle_files(frozen_env["bundle"]) == []


def test_localappdata_error_is_catchable_as_runtime_error(frozen_env, monkeypatch):
    _simulate_frozen(monkeypatch, frozen_env)
    monkeypatch.setenv("LOCALAPPDATA", "")
    assert issubclass(config.ConfigError, RuntimeError)
    with pytest.raises(RuntimeError) as excinfo:
        config.user_data_dir()
    assert isinstance(excinfo.value, config.ConfigError)


def test_user_data_dir_resolution_alone_creates_nothing(frozen_env, monkeypatch):
    """Resolving the path must not touch the filesystem; DATA_DIR does that."""
    _simulate_frozen(monkeypatch, frozen_env)
    target = frozen_env["localappdata"] / "TradeQuest"
    assert config.user_data_dir() == target
    assert not target.exists()