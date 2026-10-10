"""配置加载：默认 → 文件 → 环境变量 → overrides。

凭据
----
``api_key`` 的优先级::

    $JEV2_API_KEY  >  opencode auth.json 的 opencode-go provider

**永不落明文**：``Config.to_dict()`` 里恒为 ``"***"``，
日志和产物里出现的 key 都是掩码后的。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ..core.errors import ConfigError
from .schema import SCHEMA_VERSION, Config

ENV_PREFIX = "JEV2_"

#: config.toml 的候选位置（先 CWD 后仓库根，见 resolve_path）
CONFIG_CANDIDATES = ("jev2.toml", "config.toml", "jev2/config.toml")

#: 从本包位置向上找到仓库根。本文件在 ``<repo>/jev2/src/jev2/config/__init__.py``。
REPO_ROOT = Path(__file__).resolve().parents[4]

#: opencode 凭据文件候选位置
AUTH_CANDIDATES = (
    Path.home() / ".local" / "share" / "opencode" / "auth.json",
    Path.home() / ".config" / "opencode" / "auth.json",
    Path(os.environ.get("APPDATA", "~")) / "opencode" / "auth.json",
)

#: 这些 provider 名下的 key 可用于 OpenCode Zen 网关（按顺序尝试）
ZEN_PROVIDERS = ("opencode-go", "opencode", "zen")


def resolve_path(p: Path, *, root_first: bool = False) -> Path:
    """把相对路径解析成绝对路径。

    Parameters
    ----------
    root_first
        ``True`` 时**优先按仓库根解析**（找不到才退回 CWD）。
        配置文件里的路径用这个 —— 配置随仓库走，语义应当与仓库绑定。

        ``False``（默认）时优先按 CWD 解析，适合命令行传入的路径
        （``--out ./tmp`` 显然指当前目录）。

    为什么需要这个
    --------------
    工具既能从仓库根跑（``python -m jev2 ...``），也能从 ``jev2/`` 跑
    （``python -m pytest``）。不区分的话 ``jev2/out`` 在后者会变成
    ``jev2/jev2/out`` —— 实测踩过，生成了一个嵌套目录。

    返回 CWD 相对路径还是仓库根相对路径，取决于哪个存在；
    两条都不存在时按 ``root_first`` 决定默认值，
    不去猜「路径不存在」这件事（调用方仍能自己判断）。
    """
    p = Path(p)
    if p.is_absolute():
        return p

    cwd_rel = p
    root_rel = REPO_ROOT / p

    if root_first:
        if root_rel.exists():
            return root_rel
        if cwd_rel.exists():
            return cwd_rel
        return root_rel          # 都不存在 → 按仓库根（配置随仓库走）
    if cwd_rel.exists():
        return cwd_rel
    if root_rel.exists():
        return root_rel
    return cwd_rel


def resolve_api_key() -> str:
    """按优先级找 key。找不到返回空串（由调用方决定是否报错）。"""
    k = os.environ.get(f"{ENV_PREFIX}API_KEY", "").strip()
    if k:
        return k

    for p in AUTH_CANDIDATES:
        if not p.is_file():
            continue
        try:
            auth = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(auth, dict):
            continue
        for name in ZEN_PROVIDERS:
            v = auth.get(name)
            if isinstance(v, dict) and v.get("key"):
                return str(v["key"])
        # 兜底：任何带 key 的 provider（provider 改名了也不至于全挂）
        for v in auth.values():
            if isinstance(v, dict) and v.get("key"):
                return str(v["key"])
    return ""


def mask(key: str) -> str:
    """掩码显示。日志里只出现这个形式。"""
    if not key:
        return "<空>"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}(len={len(key)})"


def _read_toml(path: Path) -> dict[str, Any]:
    """读 TOML。Python 3.11+ 自带 tomllib；缺失则跳过（配置文件可选）。"""
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:  # pragma: no cover - 3.11+ 必有
        return {}
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"配置文件解析失败 {path}: {exc}") from exc


def find_config_file(explicit: Path | str | None = None) -> Path | None:
    if explicit:
        p = resolve_path(Path(explicit))
        if not p.is_file():
            raise ConfigError(f"配置文件不存在: {p}")
        return p
    env = os.environ.get(f"{ENV_PREFIX}CONFIG", "").strip()
    if env:
        p = resolve_path(Path(env))
        if not p.is_file():
            raise ConfigError(f"$JEV2_CONFIG 指向的文件不存在: {p}")
        return p
    for name in CONFIG_CANDIDATES:
        p = resolve_path(Path(name))
        if p.is_file():
            return p
    return None


def _apply_env(raw: dict[str, Any]) -> dict[str, Any]:
    """把 ``JEV2_*`` 环境变量覆盖进 raw。

    只处理少数几个常用项 —— 全字段都从环境变量配是反模式，
    真需要复杂覆盖就直接改配置文件。
    """
    m = {
        "JEV2_DATA_ROOT": ("paths", "data_root"),
        "JEV2_OUT_DIR": ("paths", "out_dir"),
        "JEV2_MODEL": ("semantic", "model"),
        "JEV2_ENDPOINT": ("semantic", "endpoint"),
    }
    for env_key, (section, field) in m.items():
        v = os.environ.get(env_key, "").strip()
        if not v:
            continue
        raw.setdefault(section, {})[field] = v

    # 语义层总开关：CI 里想只跑信号层时用
    if os.environ.get("JEV2_NO_SEMANTIC", "").strip() in ("1", "true", "yes"):
        raw.setdefault("semantic", {})["enabled"] = False
    return raw


def config_hash(cfg: Config) -> str:
    """配置指纹（不含 key）。

    进产物：改了阈值之后跑出来的结果与旧结果能区分开，
    不会出现「同一份 scores.jsonl 里混着两套阈值的判定」却看不出来。
    """
    d = cfg.to_dict()
    d.pop("api_key", None)
    blob = json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def load_config(*, path: Path | str | None = None,
                overrides: dict[str, Any] | None = None,
                require_key: bool = False) -> Config:
    """加载配置。

    Parameters
    ----------
    path
        显式指定配置文件；``None`` 则按候选列表自动找。
    overrides
        最高优先级的覆盖（通常是 CLI 参数）。
    require_key
        需要调用模型时传 True —— 缺 key 立刻报错，而不是跑到一半才炸。

    Raises
    ------
    ConfigError
        配置非法，或 ``require_key=True`` 但找不到 key。
    """
    raw: dict[str, Any] = {}
    cfg_path = find_config_file(path)
    if cfg_path:
        raw = _read_toml(cfg_path)
    raw = _apply_env(raw)
    if overrides:
        for k, v in overrides.items():
            if v is None:
                continue
            if isinstance(v, dict) and isinstance(raw.get(k), dict):
                raw[k].update(v)
            else:
                raw[k] = v

    cfg = Config.from_dict(raw)

    # 校验
    if cfg.schema_version > SCHEMA_VERSION:
        raise ConfigError(
            f"配置文件 schema_version={cfg.schema_version} "
            f"比程序支持的 {SCHEMA_VERSION} 新。请升级 jev2。"
        )
    if not 0.0 <= cfg.fuse.low < cfg.fuse.high <= 1.0:
        raise ConfigError(
            f"阈值非法: low={cfg.fuse.low} high={cfg.fuse.high}，"
            "要求 0 ≤ low < high ≤ 1"
        )
    if cfg.fuse.l2_aggregate not in ("mean", "max", "median"):
        raise ConfigError(
            f"l2_aggregate={cfg.fuse.l2_aggregate!r} 不合法，"
            "只能是 mean / max / median"
        )

    # 配置里的路径按**仓库根**解析（root_first）—— 配置随仓库走，
    # 语义应该与仓库绑定，不该随调用时的 CWD 漂移。
    cfg.paths.data_root = resolve_path(cfg.paths.data_root, root_first=True)
    cfg.paths.out_dir = resolve_path(cfg.paths.out_dir, root_first=True)

    if require_key:
        cfg.api_key = resolve_api_key()
        if not cfg.api_key:
            raise ConfigError(
                "找不到 API key。两条路：\n"
                f"  1. 设置环境变量 $env:{ENV_PREFIX}API_KEY\n"
                "  2. 登录 opencode（凭据在 ~/.local/share/opencode/auth.json）"
            )
    return cfg


__all__ = [
    "ENV_PREFIX", "SCHEMA_VERSION", "REPO_ROOT",
    "load_config", "resolve_path", "resolve_api_key",
    "config_hash", "mask", "find_config_file", "Config",
]
