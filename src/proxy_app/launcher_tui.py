# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mirrowel

"""
LLM API 密钥代理的交互式 TUI 启动器。
提供基于 Rich 的界面，用于配置和执行。
"""

import json
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.panel import Panel
from rich.text import Text
from dotenv import load_dotenv, set_key

from proxy_app.i18n import t, t_list

console = Console()


def _get_env_file() -> Path:
    """
    Get .env file path (lightweight - no heavy imports).

    Returns:
        Path to .env file - EXE directory if frozen, else current working directory
    """
    if getattr(sys, "frozen", False):
        # Running as PyInstaller EXE - use EXE's directory
        return Path(sys.executable).parent / ".env"
    # Running as script - use current working directory
    return Path.cwd() / ".env"


def clear_screen(subtitle: str = ""):
    """
    Cross-platform terminal clear with optional header.

    Uses native OS commands instead of ANSI escape sequences:
    - Windows (conhost & Windows Terminal): cls
    - Unix-like systems (Linux, Mac): clear

    Args:
        subtitle: If provided, displays a header panel with this subtitle.
                  If empty/None, just clears the screen.
    """
    os.system("cls" if os.name == "nt" else "clear")
    if subtitle:
        console.print(
            Panel(
                f"[bold cyan]{subtitle}[/bold cyan]",
                title=t("app_title"),
            )
        )


class LauncherConfig:
    """Manages launcher_config.json (host, port, logging only)"""

    def __init__(self, config_path: Path = Path("launcher_config.json")):
        self.config_path = config_path
        self.defaults = {
            "host": "127.0.0.1",
            "port": 8000,
            "enable_request_logging": False,
            "enable_raw_logging": False,
        }
        self.config = self.load()

    def load(self) -> dict:
        """Load config from file or create with defaults."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in self.defaults.items():
                    if key not in config:
                        config[key] = value
                return config
            except (json.JSONDecodeError, IOError):
                return self.defaults.copy()
        return self.defaults.copy()

    def save(self):
        """Save current config to file."""
        import datetime

        self.config["last_updated"] = datetime.datetime.now().isoformat()
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            console.print(f"[red]Error saving config: {e}[/red]")

    def update(self, **kwargs):
        """Update config values."""
        self.config.update(kwargs)
        self.save()

    @staticmethod
    def update_proxy_api_key(new_key: str):
        """Update PROXY_API_KEY in .env only"""
        env_file = _get_env_file()
        set_key(str(env_file), "PROXY_API_KEY", new_key)
        load_dotenv(dotenv_path=env_file, override=True)


class SettingsDetector:
    """Detects settings from .env for display"""

    @staticmethod
    def _load_local_env() -> dict:
        """Load environment variables from local .env file only"""
        env_file = _get_env_file()
        env_dict = {}
        if not env_file.exists():
            return env_dict
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key, value = key.strip(), value.strip()
                        if value and value[0] in ('"', "'") and value[-1] == value[0]:
                            value = value[1:-1]
                        env_dict[key] = value
        except (IOError, OSError):
            pass
        return env_dict

    @staticmethod
    def get_all_settings() -> dict:
        """Returns comprehensive settings overview (includes provider_settings which triggers heavy imports)"""
        return {
            "credentials": SettingsDetector.detect_credentials(),
            "custom_bases": SettingsDetector.detect_custom_api_bases(),
            "model_definitions": SettingsDetector.detect_model_definitions(),
            "concurrency_limits": SettingsDetector.detect_concurrency_limits(),
            "model_filters": SettingsDetector.detect_model_filters(),
            "provider_settings": SettingsDetector.detect_provider_settings(),
        }

    @staticmethod
    def get_basic_settings() -> dict:
        """Returns basic settings overview without provider_settings (avoids heavy imports)"""
        return {
            "credentials": SettingsDetector.detect_credentials(),
            "custom_bases": SettingsDetector.detect_custom_api_bases(),
            "model_definitions": SettingsDetector.detect_model_definitions(),
            "concurrency_limits": SettingsDetector.detect_concurrency_limits(),
            "model_filters": SettingsDetector.detect_model_filters(),
        }

    @staticmethod
    def detect_credentials() -> dict:
        """Detect API keys and OAuth credentials"""
        import re
        from pathlib import Path

        providers = {}

        # Scan for API keys
        env_vars = SettingsDetector._load_local_env()
        for key, value in env_vars.items():
            if "_API_KEY" in key and key != "PROXY_API_KEY":
                provider = key.split("_API_KEY")[0].lower()
                if provider not in providers:
                    providers[provider] = {"api_keys": 0, "oauth": 0, "custom": False}
                providers[provider]["api_keys"] += 1

        # Scan for file-based OAuth credentials
        oauth_dir = Path("oauth_creds")
        if oauth_dir.exists():
            for file in oauth_dir.glob("*_oauth_*.json"):
                provider = file.name.split("_oauth_")[0]
                if provider not in providers:
                    providers[provider] = {"api_keys": 0, "oauth": 0, "custom": False}
                providers[provider]["oauth"] += 1

        # Scan for env-based OAuth credentials
        # Maps provider name to the ENV_PREFIX used by the provider
        # (duplicated from credential_manager to avoid heavy imports)
        env_oauth_providers = {
            "gemini_cli": "GEMINI_CLI",
            "antigravity": "ANTIGRAVITY",
            "qwen_code": "QWEN_CODE",
            "iflow": "IFLOW",
        }

        for provider, env_prefix in env_oauth_providers.items():
            oauth_count = 0

            # Check numbered credentials (PROVIDER_N_ACCESS_TOKEN pattern)
            numbered_pattern = re.compile(rf"^{env_prefix}_(\d+)_ACCESS_TOKEN$")
            for key in env_vars.keys():
                match = numbered_pattern.match(key)
                if match:
                    index = match.group(1)
                    refresh_key = f"{env_prefix}_{index}_REFRESH_TOKEN"
                    if refresh_key in env_vars and env_vars[refresh_key]:
                        oauth_count += 1

            # Check legacy single credential (if no numbered found)
            if oauth_count == 0:
                access_key = f"{env_prefix}_ACCESS_TOKEN"
                refresh_key = f"{env_prefix}_REFRESH_TOKEN"
                if env_vars.get(access_key) and env_vars.get(refresh_key):
                    oauth_count = 1

            if oauth_count > 0:
                if provider not in providers:
                    providers[provider] = {"api_keys": 0, "oauth": 0, "custom": False}
                providers[provider]["oauth"] += oauth_count

        # Mark custom providers (have API_BASE set)
        for provider in providers:
            if os.getenv(f"{provider.upper()}_API_BASE"):
                providers[provider]["custom"] = True

        return providers

    @staticmethod
    def detect_custom_api_bases() -> dict:
        """Detect custom API base URLs (not in hardcoded map)"""
        from proxy_app.provider_urls import PROVIDER_URL_MAP

        bases = {}
        env_vars = SettingsDetector._load_local_env()
        for key, value in env_vars.items():
            if key.endswith("_API_BASE"):
                provider = key.replace("_API_BASE", "").lower()
                # Only include if NOT in hardcoded map
                if provider not in PROVIDER_URL_MAP:
                    bases[provider] = value
        return bases

    @staticmethod
    def detect_model_definitions() -> dict:
        """Detect provider model definitions"""
        models = {}
        env_vars = SettingsDetector._load_local_env()
        for key, value in env_vars.items():
            if key.endswith("_MODELS"):
                provider = key.replace("_MODELS", "").lower()
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        models[provider] = len(parsed)
                    elif isinstance(parsed, list):
                        models[provider] = len(parsed)
                except (json.JSONDecodeError, ValueError):
                    pass
        return models

    @staticmethod
    def detect_concurrency_limits() -> dict:
        """Detect max concurrent requests per key"""
        limits = {}
        env_vars = SettingsDetector._load_local_env()
        for key, value in env_vars.items():
            if key.startswith("MAX_CONCURRENT_REQUESTS_PER_KEY_"):
                provider = key.replace("MAX_CONCURRENT_REQUESTS_PER_KEY_", "").lower()
                try:
                    limits[provider] = int(value)
                except (json.JSONDecodeError, ValueError):
                    pass
        return limits

    @staticmethod
    def detect_model_filters() -> dict:
        """Detect active model filters (basic info only: defined or not)"""
        filters = {}
        env_vars = SettingsDetector._load_local_env()
        for key, value in env_vars.items():
            if key.startswith("IGNORE_MODELS_") or key.startswith("WHITELIST_MODELS_"):
                filter_type = "ignore" if key.startswith("IGNORE") else "whitelist"
                provider = key.replace(f"{filter_type.upper()}_MODELS_", "").lower()
                if provider not in filters:
                    filters[provider] = {"has_ignore": False, "has_whitelist": False}
                if filter_type == "ignore":
                    filters[provider]["has_ignore"] = True
                else:
                    filters[provider]["has_whitelist"] = True
        return filters

    @staticmethod
    def detect_provider_settings() -> dict:
        """Detect provider-specific settings (Antigravity, Gemini CLI)"""
        try:
            from proxy_app.settings_tool import PROVIDER_SETTINGS_MAP
        except ImportError:
            # Fallback for direct execution or testing
            from .settings_tool import PROVIDER_SETTINGS_MAP

        provider_settings = {}
        env_vars = SettingsDetector._load_local_env()

        for provider, definitions in PROVIDER_SETTINGS_MAP.items():
            modified_count = 0
            for key, definition in definitions.items():
                env_value = env_vars.get(key)
                if env_value is not None:
                    # Check if value differs from default
                    default = definition.get("default")
                    setting_type = definition.get("type", "str")

                    try:
                        if setting_type == "bool":
                            current = env_value.lower() in ("true", "1", "yes")
                        elif setting_type == "int":
                            current = int(env_value)
                        else:
                            current = env_value

                        if current != default:
                            modified_count += 1
                    except (ValueError, AttributeError):
                        pass

            if modified_count > 0:
                provider_settings[provider] = modified_count

        return provider_settings


class LauncherTUI:
    """Main launcher interface"""

    def __init__(self):
        self.console = Console()
        self.config = LauncherConfig()
        self.running = True
        self.env_file = _get_env_file()
        # Load .env file to ensure environment variables are available
        load_dotenv(dotenv_path=self.env_file, override=True)

    def needs_onboarding(self) -> bool:
        """Check if onboarding is needed"""
        return not self.env_file.exists() or not os.getenv("PROXY_API_KEY")

    def run(self):
        """Main TUI loop"""
        while self.running:
            self.show_main_menu()

    def show_main_menu(self):
        """Display main menu and handle selection"""
        clear_screen()

        # Detect basic settings (excludes provider_settings to avoid heavy imports)
        settings = SettingsDetector.get_basic_settings()
        credentials = settings["credentials"]
        custom_bases = settings["custom_bases"]

        # Check if setup is needed
        show_warning = self.needs_onboarding()

        # Build title with GitHub link
        self.console.print(
            Panel.fit(
                "[bold cyan]" + t("launcher_title") + "[/bold cyan]",
                border_style="cyan",
            )
        )
        self.console.print(
            t("launcher_github")
        )

        # Show warning if .env file doesn't exist
        if show_warning:
            self.console.print()
            self.console.print(
                Panel(
                    Text.from_markup(
                        t("setup_required_body")
                    ),
                    border_style="yellow",
                    expand=False,
                )
            )
        # Show security warning if PROXY_API_KEY is missing (but .env exists)
        elif not os.getenv("PROXY_API_KEY"):
            self.console.print()
            self.console.print(
                Panel(
                    Text.from_markup(
                        t("security_warning_body")
                    ),
                    border_style="red",
                    expand=False,
                )
            )

        # Show config
        self.console.print()
        self.console.print("[bold]" + t("proxy_config_title") + "[/bold]")
        self.console.print("━" * 70)
        self.console.print(f"   主机地址：          {self.config.config['host']}")
        self.console.print(f"   端口：              {self.config.config['port']}")
        self.console.print(
            f"   事务日志：          {'✅ 已启用' if self.config.config['enable_request_logging'] else '❌ 已禁用'}"
        )
        self.console.print(
            f"   原始I/O日志：       {'✅ 已启用' if self.config.config.get('enable_raw_logging', False) else '❌ 已禁用'}"
        )

        # Show actual API key value
        proxy_key = os.getenv("PROXY_API_KEY")
        if proxy_key:
            self.console.print(f"   代理 API 密钥：     {proxy_key}")
        else:
            self.console.print("   代理 API 密钥：     " + t("proxy_api_key_not_set"))

        # Show status summary
        self.console.print()
        self.console.print("[bold]" + t("status_summary_title") + "[/bold]")
        self.console.print("━" * 70)
        provider_count = len(credentials)
        custom_count = len(custom_bases)

        self.console.print(f"   供应商：             {provider_count} 个已配置")
        self.console.print(f"   自定义供应商：       {custom_count} 个已配置")
        # Note: provider_settings detection is deferred to avoid heavy imports on startup
        has_advanced = bool(
            settings["model_definitions"]
            or settings["concurrency_limits"]
            or settings["model_filters"]
        )
        self.console.print(
            f"   高级设置：           {'活跃 (在菜单4中查看)' if has_advanced else '无 (在菜单4中查看详情)'}"
        )

        # Show menu
        self.console.print()
        self.console.print("━" * 70)
        self.console.print()
        self.console.print("[bold]🎯 主菜单[/bold]")
        self.console.print()
        if show_warning:
            self.console.print("   " + t("menu_run_proxy"))
            self.console.print("   " + t("menu_config_proxy"))
            self.console.print(
                "   " + t("menu_manage_creds_start")
            )
        else:
            self.console.print("   " + t("menu_run_proxy"))
            self.console.print("   " + t("menu_config_proxy"))
            self.console.print("   " + t("menu_manage_creds"))

        self.console.print("   " + t("menu_view_provider"))
        self.console.print("   " + t("menu_view_quota"))
        self.console.print("   " + t("menu_reload_config"))
        self.console.print("   " + t("menu_about"))
        self.console.print("   " + t("menu_exit"))

        self.console.print()
        self.console.print("━" * 70)
        self.console.print()

        choice = Prompt.ask(
            t("select_option"),
            choices=["1", "2", "3", "4", "5", "6", "7", "8"],
            show_choices=False,
        )

        if choice == "1":
            self.run_proxy()
        elif choice == "2":
            self.show_config_menu()
        elif choice == "3":
            self.launch_credential_tool()
        elif choice == "4":
            self.show_provider_settings_menu()
        elif choice == "5":
            self.launch_quota_viewer()
        elif choice == "6":
            load_dotenv(dotenv_path=_get_env_file(), override=True)
            self.config = LauncherConfig()  # Reload config
            self.console.print(t("config_reloaded"))
        elif choice == "7":
            self.show_about()
        elif choice == "8":
            self.running = False
            sys.exit(0)

    def confirm_setting_change(self, setting_name: str, warning_lines: list) -> bool:
        """
        显示警告并要求 Y/N（区分大小写）确认。
        持续提示直到用户输入 'Y' 或 'N'。
        仅当用户输入 'Y' 时返回 True。
        """
        clear_screen()
        self.console.print()
        self.console.print(
            Panel(
                Text.from_markup(
                    f"[bold yellow]⚠️  警告：您即将更改 {setting_name}[/bold yellow]\n\n"
                    + "\n".join(warning_lines)
                    + "\n\n[bold]如果您不确定是否要更改 - 请不要更改。[/bold]"
                ),
                border_style="yellow",
                expand=False,
            )
        )

        while True:
            response = Prompt.ask(
                t("confirm_yn")
            )
            if response == "Y":
                return True
            elif response == "N":
                self.console.print(t("operation_cancelled"))
                return False
            else:
                self.console.print(
                    t("please_enter_yn")
                )

    def show_config_menu(self):
        """显示配置子菜单"""
        while True:
            clear_screen()

            self.console.print(
                Panel.fit(
                    "[bold cyan]⚙️  代理配置[/bold cyan]", border_style="cyan"
                )
            )

            self.console.print()
            self.console.print("[bold]📋 当前设置[/bold]")
            self.console.print("━" * 70)
            self.console.print(f"   主机地址：          {self.config.config['host']}")
            self.console.print(f"   端口：              {self.config.config['port']}")
            self.console.print(
                f"   事务日志：          {'✅ 已启用' if self.config.config['enable_request_logging'] else '❌ 已禁用'}"
            )
            self.console.print(
                f"   原始I/O日志：       {'✅ 已启用' if self.config.config.get('enable_raw_logging', False) else '❌ 已禁用'}"
            )
            self.console.print(
                f"   代理 API 密钥：     {'✅ 已设置' if os.getenv('PROXY_API_KEY') else '❌ 未设置'}"
            )

            self.console.print()
            self.console.print("━" * 70)
            self.console.print()
            self.console.print("[bold]⚙️  配置选项[/bold]")
            self.console.print()
            self.console.print("   " + t("config_set_host"))
            self.console.print("   " + t("config_set_port"))
            self.console.print("   " + t("config_set_api_key"))
            self.console.print("   " + t("config_toggle_trans_log"))
            self.console.print("   " + t("config_toggle_raw_log"))
            self.console.print("   " + t("config_reset_defaults"))
            self.console.print("   " + t("config_back"))

            self.console.print()
            self.console.print("━" * 70)
            self.console.print()

            choice = Prompt.ask(
                t("select_option"),
                choices=["1", "2", "3", "4", "5", "6", "7"],
                show_choices=False,
            )

            if choice == "1":
                # Show warning and require confirmation
                confirmed = self.confirm_setting_change(
                    t("warn_host_ip"),
                    t_list("warn_host_lines"),
                )
                if not confirmed:
                    continue

                new_host = Prompt.ask(
                    t("enter_new_host"), default=self.config.config["host"]
                )
                self.config.update(host=new_host)
                self.console.print(t("host_updated", host=new_host))
            elif choice == "2":
                # Show warning and require confirmation
                confirmed = self.confirm_setting_change(
                    t("warn_port"),
                    t_list("warn_port_lines"),
                )
                if not confirmed:
                    continue

                new_port = IntPrompt.ask(
                    t("enter_new_port"), default=self.config.config["port"]
                )
                if 1 <= new_port <= 65535:
                    self.config.update(port=new_port)
                    self.console.print(
                        t("port_updated", port=new_port)
                    )
                else:
                    self.console.print(t("port_invalid"))
            elif choice == "3":
                # Show warning and require confirmation
                confirmed = self.confirm_setting_change(
                    t("warn_proxy_key"),
                    t_list("warn_proxy_key_lines"),
                )
                if not confirmed:
                    continue

                current = os.getenv("PROXY_API_KEY", "")
                new_key = Prompt.ask(
                    t("enter_new_api_key"),
                    default=current,
                )

                if new_key != current:
                    # If setting to empty, show additional warning
                    if not new_key:
                        self.console.print(
                            t("auth_will_be_disabled")
                        )
                        Prompt.ask(t("press_enter"), default="")

                    LauncherConfig.update_proxy_api_key(new_key)

                    if new_key:
                        self.console.print(
                            t("api_key_updated")
                        )
                        self.console.print(t("api_key_updated_in_env"))
                    else:
                        self.console.print(
                            t("api_key_cleared")
                        )
                        self.console.print(t("api_key_updated_in_env"))
                else:
                    self.console.print(t("no_changes_made"))
            elif choice == "4":
                current = self.config.config["enable_request_logging"]
                self.config.update(enable_request_logging=not current)
                self.console.print(
                    t("trans_log_toggled", status="启用" if not current else "禁用")
                )
            elif choice == "5":
                current = self.config.config.get("enable_raw_logging", False)
                self.config.update(enable_raw_logging=not current)
                self.console.print(
                    t("raw_log_toggled", status="启用" if not current else "禁用")
                )
            elif choice == "6":
                # Reset to Default Settings
                # Define defaults
                default_host = "127.0.0.1"
                default_port = 8000
                default_logging = False
                default_raw_logging = False
                default_api_key = "VerysecretKey"

                # Get current values
                current_host = self.config.config["host"]
                current_port = self.config.config["port"]
                current_logging = self.config.config["enable_request_logging"]
                current_raw_logging = self.config.config.get(
                    "enable_raw_logging", False
                )
                current_api_key = os.getenv("PROXY_API_KEY", "")

                # Build comparison table
                warning_lines = [
                    t("reset_defaults_warning"),
                    "",
                    "[bold]   设置              当前值                →  默认值[/bold]",
                    "   " + "─" * 62,
                    f"   主机 IP             {current_host:20} →  {default_host}",
                    f"   端口                {str(current_port):20} →  {default_port}",
                    f"   事务日志            {'已启用':20} →  已禁用"
                    if current_logging
                    else f"   事务日志            {'已禁用':20} →  已禁用",
                    f"   原始I/O日志         {'已启用':20} →  已禁用"
                    if current_raw_logging
                    else f"   原始I/O日志         {'已禁用':20} →  已禁用",
                    f"   代理 API 密钥       {current_api_key[:20]:20} →  {default_api_key}",
                    "",
                    "[bold red]⚠️  这可能导致使用当前设置的应用程序连接失败！[/bold red]",
                ]

                confirmed = self.confirm_setting_change(
                    "设置（恢复默认值）", warning_lines
                )
                if not confirmed:
                    continue

                # Apply defaults
                self.config.update(
                    host=default_host,
                    port=default_port,
                    enable_request_logging=default_logging,
                    enable_raw_logging=default_raw_logging,
                )
                LauncherConfig.update_proxy_api_key(default_api_key)

                self.console.print(
                    t("all_settings_reset")
                )
                self.console.print(f"   主机：              {default_host}")
                self.console.print(f"   端口：              {default_port}")
                self.console.print(f"   事务日志：          已禁用")
                self.console.print(f"   原始I/O日志：       已禁用")
                self.console.print(f"   代理 API 密钥：     {default_api_key}")
            elif choice == "7":
                break

    def show_provider_settings_menu(self):
        """显示供应商/高级设置（只读 + 启动工具）"""
        clear_screen()

        # Use basic settings to avoid heavy imports - provider_settings deferred to Settings Tool
        settings = SettingsDetector.get_basic_settings()

        credentials = settings["credentials"]
        custom_bases = settings["custom_bases"]
        model_defs = settings["model_definitions"]
        concurrency = settings["concurrency_limits"]
        filters = settings["model_filters"]

        self.console.print(
            Panel.fit(
                "[bold cyan]📊 供应商与高级设置[/bold cyan]",
                border_style="cyan",
            )
        )

        # Configured Providers
        self.console.print()
        self.console.print("[bold]📊 已配置的供应商[/bold]")
        self.console.print("━" * 70)
        if credentials:
            for provider, info in credentials.items():
                provider_name = provider.title()
                parts = []
                if info["api_keys"] > 0:
                    parts.append(
                        f"{info['api_keys']} 个 API 密钥"
                    )
                if info["oauth"] > 0:
                    parts.append(
                        f"{info['oauth']} 个 OAuth 凭据"
                    )

                display = " + ".join(parts)
                if info["custom"]:
                    display += " (自定义)"

                self.console.print(f"   ✅ {provider_name:20} {display}")
        else:
            self.console.print("   [dim]未配置任何供应商[/dim]")

        # Custom API Bases
        if custom_bases:
            self.console.print()
            self.console.print("[bold]🌐 自定义 API 地址[/bold]")
            self.console.print("━" * 70)
            for provider, base in custom_bases.items():
                self.console.print(f"   • {provider:15} {base}")

        # Model Definitions
        if model_defs:
            self.console.print()
            self.console.print("[bold]📦 供应商模型定义[/bold]")
            self.console.print("━" * 70)
            for provider, count in model_defs.items():
                self.console.print(
                    f"   • {provider:15} {count} 个模型已配置"
                )

        # Concurrency Limits
        if concurrency:
            self.console.print()
            self.console.print("[bold]⚡ 并发限制[/bold]")
            self.console.print("━" * 70)
            for provider, limit in concurrency.items():
                self.console.print(f"   • {provider:15} {limit} 请求/密钥")
            self.console.print("   • 默认:           1 请求/密钥 (其他供应商)")

        # Model Filters (basic info only)
        if filters:
            self.console.print()
            self.console.print("[bold]🎯 模型过滤器[/bold]")
            self.console.print("━" * 70)
            for provider, filter_info in filters.items():
                status_parts = []
                if filter_info["has_whitelist"]:
                    status_parts.append("白名单")
                if filter_info["has_ignore"]:
                    status_parts.append("忽略列表")
                status = " + ".join(status_parts) if status_parts else "无"
                self.console.print(f"   • {provider:15} ✅ {status}")

        # Provider-Specific Settings (deferred to Settings Tool to avoid heavy imports)
        self.console.print()
        self.console.print("[bold]🔬 供应商特定设置[/bold]")
        self.console.print("━" * 70)
        self.console.print(
            t("launch_settings_tool_hint")
        )

        # Actions
        self.console.print()
        self.console.print("━" * 70)
        self.console.print()
        self.console.print("[bold]💡 操作[/bold]")
        self.console.print()
        self.console.print(
            "   1. 🔧 启动设置工具      （配置高级设置）"
        )
        self.console.print("   2. ↩️  返回主菜单")

        self.console.print()
        self.console.print("━" * 70)
        self.console.print(
            t("advanced_in_env")
        )
        self.console.print()
        self.console.print(
            t("settings_tool_note")
        )
        self.console.print()

        choice = Prompt.ask(t("select_option"), choices=["1", "2"], show_choices=False)

        if choice == "1":
            self.launch_settings_tool()
        # choice == "2" returns to main menu

    def launch_credential_tool(self):
        """启动凭据管理工具"""
        import time

        # CRITICAL: Show full loading UI to replace the 6-7 second blank wait
        clear_screen()

        _start_time = time.time()

        # Show the same header as standalone mode
        self.console.print("━" * 70)
        self.console.print(t("credential_tool_header"))
        self.console.print("GitHub: https://github.com/Mirrowel/LLM-API-Key-Proxy")
        self.console.print("━" * 70)
        self.console.print(t("loading_credential_components"))

        # Now import with spinner (this is where the 6-7 second delay happens)
        with self.console.status(t("initializing_credential_tool"), spinner="dots"):
            from rotator_library.credential_tool import (
                run_credential_tool,
                _ensure_providers_loaded,
            )

            _, PROVIDER_PLUGINS = _ensure_providers_loaded()
        self.console.print(t("credential_tool_initialized"))

        _elapsed = time.time() - _start_time
        self.console.print(
            t("tool_ready", elapsed=_elapsed, count=len(PROVIDER_PLUGINS))
        )

        # Small delay to let user see the ready message
        time.sleep(0.5)

        # Run the tool with from_launcher=True to skip duplicate loading screen
        run_credential_tool(from_launcher=True)
        # Reload environment after credential tool
        load_dotenv(dotenv_path=_get_env_file(), override=True)

    def launch_settings_tool(self):
        """启动设置配置工具"""
        import time

        clear_screen()

        self.console.print("━" * 70)
        self.console.print(t("settings_tool_header"))
        self.console.print("━" * 70)

        _start_time = time.time()

        with self.console.status(t("initializing_settings_tool"), spinner="dots"):
            from proxy_app.settings_tool import run_settings_tool

        _elapsed = time.time() - _start_time
        self.console.print(t("settings_tool_ready", elapsed=_elapsed))

        time.sleep(0.3)

        run_settings_tool()
        # Reload environment after settings tool
        load_dotenv(dotenv_path=_get_env_file(), override=True)

    def launch_quota_viewer(self):
        """启动配额统计查看器"""
        clear_screen()

        self.console.print("━" * 70)
        self.console.print(t("quota_viewer_header"))
        self.console.print("━" * 70)
        self.console.print()

        # Import the lightweight viewer (no heavy imports)
        from proxy_app.quota_viewer import run_quota_viewer

        run_quota_viewer()

    def show_about(self):
        """显示关于页面"""
        clear_screen()

        self.console.print(
            Panel.fit(
                "[bold cyan]ℹ️  关于 LLM API 密钥代理[/bold cyan]", border_style="cyan"
            )
        )

        self.console.print()
        self.console.print("[bold]📦 项目信息[/bold]")
        self.console.print("━" * 70)
        self.console.print("   [bold cyan]LLM API Key Proxy[/bold cyan]")
        self.console.print(
            t("about_description_1")
        )
        self.console.print(t("about_description_2"))
        self.console.print()
        self.console.print(
            "   [dim]GitHub:[/dim] [blue underline]https://github.com/Mirrowel/LLM-API-Key-Proxy[/blue underline]"
        )

        self.console.print()
        self.console.print("[bold]✨ 主要特性[/bold]")
        self.console.print("━" * 70)
        self.console.print(t("feature_rotation"))
        self.console.print(t("feature_oauth"))
        self.console.print(t("feature_providers"))
        self.console.print(t("feature_custom"))
        self.console.print(t("feature_filtering"))
        self.console.print(t("feature_concurrency"))
        self.console.print(t("feature_cost"))
        self.console.print(t("feature_tui"))

        self.console.print()
        self.console.print("[bold]📝 许可与致谢[/bold]")
        self.console.print("━" * 70)
        self.console.print(t("made_with_love"))
        self.console.print(t("open_source"))

        self.console.print()
        self.console.print("━" * 70)
        self.console.print()

        Prompt.ask(t("press_enter_return_main"), default="")

    def run_proxy(self):
        """准备并在同一窗口启动代理"""
        # Check if forced onboarding needed
        if self.needs_onboarding():
            clear_screen()
            self.console.print(
                Panel(
                    Text.from_markup(
                        t("setup_required_run")
                    ),
                    border_style="yellow",
                )
            )

            # Force credential tool
            from rotator_library.credential_tool import (
                ensure_env_defaults,
                run_credential_tool,
            )

            ensure_env_defaults()
            load_dotenv(dotenv_path=_get_env_file(), override=True)
            run_credential_tool()
            load_dotenv(dotenv_path=_get_env_file(), override=True)

            # Check again after credential tool
            if not os.getenv("PROXY_API_KEY"):
                self.console.print(
                    t("proxy_key_still_not_set")
                )
                return

        # Clear console and modify sys.argv
        clear_screen()
        self.console.print(
            t("starting_proxy", host=self.config.config['host'], port=self.config.config['port'])
        )

        # Brief pause so user sees the message before main.py takes over
        import time

        time.sleep(0.5)

        # Reconstruct sys.argv for main.py
        sys.argv = [
            "main.py",
            "--host",
            self.config.config["host"],
            "--port",
            str(self.config.config["port"]),
        ]
        if self.config.config["enable_request_logging"]:
            sys.argv.append("--enable-request-logging")
        if self.config.config.get("enable_raw_logging", False):
            sys.argv.append("--enable-raw-logging")

        # Exit TUI - main.py will continue execution
        self.running = False


def run_launcher_tui():
    """Entry point for launcher TUI"""
    tui = LauncherTUI()
    tui.run()
