import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    """Load a small, shell-independent subset of dotenv syntax."""
    env_path = Path(path)
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is None:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_dotenv(str(Path(__file__).with_name(".env")))

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
from sci import Automata, Tester, OBS, Presets
from sci import AllInOne, AIOAgent
from sci import SeeAct, PlannerAgent, GrounderAgent
from sci import Disentangled, CoderAgent, ActorAgent


def key_bank_settings() -> tuple[str, str, str]:
    """Return an OpenAI-compatible endpoint, key, and model from a key bank."""
    key_bank_path = os.environ.get("KEY_BANK_PATH", "").strip()
    if not key_bank_path:
        raise ValueError("KEY_BANK_PATH is not configured")

    path = Path(key_bank_path).expanduser()
    try:
        bank = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read key bank: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"key bank is not valid JSON: {path}") from exc

    entries = bank.get("keys", {})
    if not isinstance(entries, dict) or not entries:
        raise ValueError("key bank contains no entries")

    entry_name = os.environ.get("KEY_BANK_ENTRY", "").strip()
    if not entry_name:
        entry_name = next(
            (
                name for name, value in entries.items()
                if isinstance(value, dict) and value.get("status") == "working"
            ),
            next(iter(entries)),
        )
    if entry_name not in entries or not isinstance(entries[entry_name], dict):
        raise ValueError(f"key-bank entry does not exist: {entry_name}")

    entry = entries[entry_name]
    api_key = str(entry.get("api_key") or "").strip()
    base_url = str(entry.get("base_url") or "").strip().rstrip("/")
    models = entry.get("working_models") or []
    model_name = os.environ.get("KEY_BANK_MODEL", "").strip()
    if not model_name and isinstance(models, list) and models:
        model_name = str(models[0]).strip()
    if not api_key or not base_url or not model_name:
        raise ValueError(
            f"key-bank entry {entry_name!r} needs api_key, base_url, and a model"
        )

    if not base_url.endswith("/chat/completions"):
        base_url += "/chat/completions"
    return base_url, api_key, model_name


def key_bank(cls):
    base_url, api_key, model_name = key_bank_settings()
    return Automata(
        model_style="openai",
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
        proxy=os.environ.get("HTTPX_PROXY") or None,
        top_p=None,
        temperature=0,
        overflow_style="openai_gpt",
        mirror_system_to_user=True,
    )(cls)

# commercial models
gpt_4o = lambda cls: Automata(
    model_style="openai",
    base_url="https://api.openai.com/v1/chat/completions",
    model_name="gpt-4o-2024-08-06",
    api_key=os.environ["OPENAI_API_KEY"],
    proxy=os.environ.get("HTTPX_PROXY") or None,
    overflow_style="openai_gpt"
)(cls)

gpt_5 = lambda cls: Automata(
    model_style="openai",
    base_url="https://api.openai.com/v1/chat/completions",
    model_name="gpt-5-2025-08-07",
    api_key=os.environ["OPENAI_API_KEY"],
    proxy=os.environ.get("HTTPX_PROXY") or None,
    max_tokens=None,
    top_p=None,
    temperature=None,
    reason_effort="high",
    overflow_style="openai_gpt"
)(cls)

gpt_o3 = lambda cls: Automata(
    model_style="openai",
    base_url="https://api.openai.com/v1/chat/completions",
    model_name="o3-mini-2025-01-31",
    api_key=os.environ["OPENAI_API_KEY"],
    proxy=os.environ.get("HTTPX_PROXY") or None,
    max_tokens=None,
    top_p=None,
    overflow_style="openai_gpt"
)(cls)

gemini_2 = lambda cls: Automata(
    model_style="openai",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    model_name="gemini-2.0-flash-exp",
    api_key=os.environ["GOOGLE_API_KEY"],
    proxy=os.environ.get("HTTPX_PROXY") or None,
    overflow_style="openai_gpt"
)(cls)

claude_3 = lambda cls: Automata(
    model_style="anthropic",
    base_url="https://api.anthropic.com/v1/messages",
    model_name="claude-3-7-sonnet-20250219",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    proxy=os.environ.get("HTTPX_PROXY") or None,
    version=os.environ.get("ANTHROPIC_VERSION", "2023-06-01"),
    overflow_style="anthropic"
)(cls)

# open-source models
qwen25_vl = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["QWEN_VL_URL"],
    model_name=os.environ["QWEN_VL_NAME"],
    overflow_style="openai_lmdeploy",
    hide_text=True
)(cls)

intern_vl = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["INTERN_VL_URL"],
    model_name=os.environ["INTERN_VL_NAME"],
    overflow_style="openai_lmdeploy",
    hide_text=True
)(cls)

qvq = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["QVQ_VL_URL"],
    model_name=os.environ["QVQ_VL_NAME"],
    overflow_style="openai_lmdeploy",
    hide_text=True
)(cls)

# grounding models
os_atlas = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["OS_ACT_URL"],
    model_name=os.environ["OS_ACT_NAME"],
    overflow_style="openai_lmdeploy",
    code_style="atlas"
)(cls)

gui_actor = lambda cls: Automata(
    model_style="gui_actor",
    base_url=os.environ["GUI_ACTOR_URL"],
    model_name=os.environ["GUI_ACTOR_NAME"],
    code_style="gui_actor"
)(cls)

uground = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["UGROUND_URL"],
    model_name=os.environ["UGROUND_NAME"],
    overflow_style="openai_lmdeploy",
    code_style="uground"
)(cls)

tars_dpo = lambda cls: Automata(
    model_style="openai",
    base_url=os.environ["TARS_DPO_URL"],
    model_name=os.environ["TARS_DPO_NAME"],
    overflow_style="openai_lmdeploy",
    code_style="uground"
)(cls)


MODELS = {
    "key_bank": key_bank,
    "gpt_4o": gpt_4o,
    "gpt_5": gpt_5,
    "gpt_o3": gpt_o3,
    "gemini_2": gemini_2,
    "claude_3": claude_3,
    "qwen25_vl": qwen25_vl,
    "intern_vl": intern_vl,
    "qvq": qvq,
}

MODEL_ENV = {
    "key_bank": ("KEY_BANK_PATH",),
    "gpt_4o": ("OPENAI_API_KEY",),
    "gpt_5": ("OPENAI_API_KEY",),
    "gpt_o3": ("OPENAI_API_KEY",),
    "gemini_2": ("GOOGLE_API_KEY",),
    "claude_3": ("ANTHROPIC_API_KEY",),
    "qwen25_vl": ("QWEN_VL_URL", "QWEN_VL_NAME"),
    "intern_vl": ("INTERN_VL_URL", "INTERN_VL_NAME"),
    "qvq": ("QVQ_VL_URL", "QVQ_VL_NAME"),
}

RAW_APP_ENV = {
    "Lean": ("LEAN_LIB_PATH",),
    "KAlgebra": ("KALG_BIN_PATH", "QT6_LIB_PATH"),
    "Celestia": ("CELE_BIN_PATH", "QT6_LIB_PATH"),
    "GrassGIS": ("GIS_BIN_PATH", "FFI_LIB_PATH"),
}

OBSERVATIONS = {
    "screenshot": OBS.screenshot,
    "a11y_tree": OBS.a11y_tree,
    "set_of_marks": OBS.set_of_marks,
}


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def task_configs(tasks_path: str) -> list[dict]:
    root = Path(tasks_path)
    paths = [root] if root.is_file() else root.rglob("*.json")
    configs = []
    for path in paths:
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(config, dict):
            configs.append(config)
    return configs


def configuration_issues(args: argparse.Namespace) -> list[str]:
    issues = []
    tasks_path = Path(args.tasks).expanduser()
    if not tasks_path.exists():
        issues.append(f"task path does not exist: {tasks_path}")
        configs = []
    else:
        configs = task_configs(args.tasks)
        if not configs:
            issues.append(f"task path contains no valid JSON tasks: {tasks_path}")
        expected_sort = "VM" if args.mode in {"vm", "docker"} else "Raw"
        unexpected_sorts = sorted({
            str(config.get("sort")) for config in configs
            if config.get("sort") != expected_sort
        })
        if unexpected_sorts:
            issues.append(
                f"{args.mode} mode cannot run task sort(s): "
                + ", ".join(unexpected_sorts)
            )

    for name in MODEL_ENV[args.model]:
        if not os.environ.get(name):
            issues.append(f"missing environment variable: {name}")

    if args.model == "key_bank" and os.environ.get("KEY_BANK_PATH"):
        try:
            key_bank_settings()
        except ValueError as exc:
            issues.append(str(exc))

    if args.mode == "vm":
        if not args.vm_path:
            issues.append("missing VM_PATH (or --vm-path)")
        elif not Path(args.vm_path).expanduser().exists():
            issues.append(f"VM path does not exist: {args.vm_path}")
        if shutil.which("vmrun") is None:
            issues.append("vmrun is not installed or not on PATH")
    elif args.mode == "docker":
        docker_binary = os.environ.get("DOCKER_BINARY", "docker")
        if shutil.which(docker_binary) is None:
            issues.append(f"Docker CLI is not installed: {docker_binary}")
        if not args.docker_image:
            issues.append("missing DOCKER_IMAGE (or --docker-image)")
        elif shutil.which(docker_binary) is not None:
            try:
                inspected = subprocess.run(
                    [
                        docker_binary, "image", "inspect", "--format",
                        "{{json .}}", args.docker_image,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if inspected.returncode != 0:
                    issues.append(f"Docker image does not exist: {args.docker_image}")
                else:
                    metadata = json.loads(inspected.stdout)
                    if metadata.get("Architecture") != "amd64":
                        issues.append("ScienceBoard Docker image must be amd64")
                    labels = metadata.get("Config", {}).get("Labels") or {}
                    if labels.get("org.scienceboard.version") != "0.1":
                        issues.append(
                            "Docker image is missing ScienceBoard version label 0.1"
                        )
                    if (
                        labels.get("org.scienceboard.distribution")
                        != "sanitized-flat"
                    ):
                        issues.append(
                            "Docker image must be a sanitized-flat distribution"
                        )
            except subprocess.TimeoutExpired:
                issues.append("Docker daemon did not answer image inspection")
            except json.JSONDecodeError:
                issues.append("Docker returned invalid image metadata")
    else:
        raw_apps = {
            config["type"] for config in configs
            if config.get("sort") == "Raw" and isinstance(config.get("type"), str)
        }
        for app in sorted(raw_apps):
            for name in RAW_APP_ENV.get(app, ()):
                if not os.environ.get(name):
                    issues.append(f"{app} Raw tasks require: {name}")
            if app == "Lean" and shutil.which("lake") is None:
                issues.append("Lean Raw tasks require lake on PATH (install Lean via elan)")

    return issues


def parse_args() -> argparse.Namespace:
    configured_mode = os.environ.get("SCI_MODE", "raw").lower()
    configured_model = os.environ.get("SCI_MODEL", "gpt_4o")

    parser = argparse.ArgumentParser(description="Run one configured ScienceBoard evaluation.")
    parser.add_argument(
        "--mode", choices=("raw", "vm", "docker"), default=configured_mode
    )
    parser.add_argument("--model", choices=tuple(MODELS), default=configured_model)
    parser.add_argument("--tasks")
    parser.add_argument("--logs")
    parser.add_argument("--vm-path", default=os.environ.get("VM_PATH"))
    parser.add_argument(
        "--docker-image", default=os.environ.get("DOCKER_IMAGE")
    )
    parser.add_argument(
        "--observation",
        choices=tuple(OBSERVATIONS),
        action="append",
        help="Desktop observation type; repeat to combine types (default: screenshot).",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=env_bool("SCI_HEADLESS", True),
    )
    parser.add_argument(
        "--ignore",
        action=argparse.BooleanOptionalAction,
        default=env_bool("SCI_IGNORE", True),
        help="Skip tasks that already have a result.out log.",
    )
    parser.add_argument("--debug", action="store_true", help="Complete tasks manually.")
    parser.add_argument("--check", action="store_true", help="Validate configuration without running tasks.")
    args = parser.parse_args()
    if args.mode not in {"raw", "vm", "docker"}:
        parser.error(f"invalid SCI_MODE: {args.mode!r}")
    if args.model not in MODELS:
        parser.error(f"invalid SCI_MODEL: {args.model!r}")
    if args.tasks is None:
        configured_tasks = os.environ.get("SCI_TASKS_PATH")
        args.tasks = configured_tasks if args.mode == configured_mode and configured_tasks \
            else f"./tasks/{'VM' if args.mode in {'vm', 'docker'} else 'Raw'}"
    if args.logs is None:
        configured_logs = os.environ.get("SCI_LOGS_PATH")
        args.logs = configured_logs if args.mode == configured_mode and configured_logs \
            else f"./logs/{args.model}-{args.mode}"
    return args


def main() -> int:
    args = parse_args()
    issues = configuration_issues(args)
    if issues:
        print("ScienceBoard configuration is incomplete:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        print("Copy .env.example to .env and fill the relevant values.", file=sys.stderr)
        return 2

    if args.check:
        print("ScienceBoard configuration check passed.")
        return 0

    observation_names = args.observation or ["screenshot"]
    community = AllInOne(MODELS[args.model](AIOAgent))
    desktop_path = (
        args.vm_path if args.mode == "vm"
        else args.docker_image if args.mode == "docker"
        else None
    )
    manager_factory = (
        Presets.spawn_docker_managers
        if args.mode == "docker"
        else Presets.spawn_managers
    )
    Tester(
        tasks_path=args.tasks,
        logs_path=args.logs,
        community=community,
        vm_path=desktop_path,
        obs_types={OBSERVATIONS[name] for name in observation_names},
        headless=args.headless,
        ignore=args.ignore,
        debug=args.debug,
        handle_managers=manager_factory,
    )()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
