# SPDX-License-Identifier: MIT
# 中文本地化模块 - LLM API Key Proxy UI 汉化

"""
Centralized Chinese localization module for the LLM API Key Proxy UI.
All user-facing strings are collected here for easy maintenance.

Usage:
    from proxy_app.i18n import t
    print(t('app_title'))  # => "LLM API 密钥代理"
"""

# ════════════════════════════════════════════════════════════════════════════════
# TRANSLATION DICTIONARY
# ════════════════════════════════════════════════════════════════════════════════

_TRANSLATIONS = {
    # ── Common / Shared ──────────────────────────────────────────────────────
    "app_title": "--- API 密钥代理 ---",
    "select_option": "请选择",
    "press_enter_continue": "\n按回车键继续...",
    "press_enter_return": "按回车键返回...",
    "press_enter_return_launcher": "\n按回车键返回启动器...",
    "press_enter_return_main": "按回车键返回主菜单",
    "no_changes_made": "\n[yellow]未做任何更改[/yellow]",
    "operation_cancelled": "\n[dim]操作已取消。[/dim]",
    "cancelled": "[dim]已取消。[/dim]",
    "back": "返回",
    "back_to_main_menu": "↩️  返回主菜单",
    "back_to_settings": "↩️  返回设置菜单",
    "yes": "是",
    "no": "否",
    "enabled": "已启用",
    "disabled": "已禁用",
    "configured": "已配置",
    "not_set": "未设置",
    "none": "无",
    "save": "保存",
    "discard": "放弃",
    "cancel": "取消",
    "confirm_yn": "输入 [bold]Y[/bold] 确认, [bold]N[/bold] 取消 (区分大小写)",
    "please_enter_yn": "[red]请输入 'Y' 或 'N' (区分大小写)[/red]",

    # ── Launcher TUI ─────────────────────────────────────────────────────────
    "launcher_title": "🚀 LLM API 密钥代理 - 交互式启动器",
    "launcher_github": "[dim]GitHub: [blue underline]https://github.com/Mirrowel/LLM-API-Key-Proxy[/blue underline][/dim]",

    # Onboarding warning
    "setup_required_title": "⚠️  [bold yellow]需要初始配置[/bold yellow]",
    "setup_required_body": (
        "⚠️  [bold yellow]需要初始配置[/bold yellow]\n\n"
        "代理服务器需要进行初始配置：\n"
        "  ❌ 未找到 .env 文件\n\n"
        "为什么这很重要：\n"
        "  • .env 文件存储您的凭据和设置\n"
        "  • PROXY_API_KEY 保护您的代理服务器免受未授权访问\n"
        "  • 供应商 API 密钥用于访问 LLM 服务\n\n"
        "操作步骤：\n"
        '  1. 选择 "3. 管理凭据" 启动凭据管理工具\n'
        "  2. 工具会自动创建 .env 并设置 PROXY_API_KEY\n"
        "  3. 您可以添加供应商凭据（API 密钥或 OAuth）\n\n"
        "⚠️  注意：凭据工具会默认添加 PROXY_API_KEY。\n"
        "   如果您想要不设防的代理，可以稍后删除它。"
    ),

    # Security warning
    "security_warning_title": "⚠️  [bold red]安全警告：PROXY_API_KEY 未设置[/bold red]",
    "security_warning_body": (
        "⚠️  [bold red]安全警告：PROXY_API_KEY 未设置[/bold red]\n\n"
        "您的代理服务器当前 [bold red]未受保护[/bold red]！\n"
        "任何人都可以在无需认证的情况下访问它。\n\n"
        "如果您的代理可从互联网或不受信任的网络访问，\n"
        "这将是一个严重的安全风险。\n\n"
        "👉 [bold]建议：[/bold] 在 .env 文件中设置 PROXY_API_KEY\n"
        '   使用选项 "2. 代理设置" → "3. 设置代理 API 密钥"\n'
        '   或选项 "3. 管理凭据"'
    ),

    # Proxy Configuration
    "proxy_config_title": "📋 代理配置",
    "host_label": "   主机地址：          ",
    "port_label": "   端口：              ",
    "transaction_logging": "   事务日志：          ",
    "raw_io_logging": "   原始I/O日志：       ",
    "proxy_api_key_label": "   代理 API 密钥：     ",
    "proxy_api_key_not_set": "[red]未设置 (不安全!)[/red]",

    # Status Summary
    "status_summary_title": "📊 状态概览",
    "providers_count": "   供应商：             {count} 个已配置",
    "custom_providers_count": "   自定义供应商：       {count} 个已配置",
    "advanced_settings_active": "   高级设置：           活跃 (在菜单4中查看)",
    "advanced_settings_none": "   高级设置：           无 (在菜单4中查看详情)",

    # Main Menu
    "main_menu_title": "🎯 主菜单",
    "menu_run_proxy": "1. ▶️  启动代理服务器",
    "menu_config_proxy": "2. ⚙️  代理设置",
    "menu_manage_creds": "3. 🔑 管理凭据",
    "menu_manage_creds_start": "3. 🔑 管理凭据            ⬅️  [bold yellow]从这里开始！[/bold yellow]",
    "menu_view_provider": "4. 📊 查看供应商与高级设置",
    "menu_view_quota": "5. 📈 查看配额与使用统计 (Alpha)",
    "menu_reload_config": "6. 🔄 重新加载配置",
    "menu_about": "7. ℹ️  关于",
    "menu_exit": "8. 🚪 退出",
    "config_reloaded": "\n[green]✅ 配置已重新加载！[/green]",

    # Config Menu
    "config_menu_title": "⚙️  代理配置",
    "current_settings": "📋 当前设置",
    "config_options": "⚙️  配置选项",
    "config_set_host": "1. 🌐 设置主机 IP",
    "config_set_port": "2. 🔌 设置端口",
    "config_set_api_key": "3. 🔑 设置代理 API 密钥",
    "config_toggle_trans_log": "4. 📝 切换事务日志",
    "config_toggle_raw_log": "5. 📋 切换原始I/O日志",
    "config_reset_defaults": "6. 🔄 恢复默认设置",
    "config_back": "7. ↩️  返回主菜单",

    # Config change warnings
    "warn_host_ip": "主机 IP",
    "warn_host_lines": [
        "更改主机 IP 会影响代理监听的网络接口：",
        "  • [cyan]127.0.0.1[/cyan] = 仅本地访问（推荐用于开发）",
        "  • [cyan]0.0.0.0[/cyan] = 可从所有网络接口访问",
        "",
        "配置为连接旧主机地址的应用程序可能无法连接。",
    ],
    "warn_port": "端口",
    "warn_port_lines": [
        "更改端口将影响当前配置为连接到",
        "代理现有端口的所有应用程序。",
        "",
        "使用旧端口的应用程序将无法连接。",
    ],
    "warn_proxy_key": "代理 API 密钥",
    "warn_proxy_key_lines": [
        "这是应用程序用来访问您代理的认证密钥。",
        "",
        "[bold red]⚠️  更改此密钥将导致所有当前配置了",
        "   现有 API 密钥的应用程序连接失败！[/bold red]",
        "",
        "[bold cyan]💡 如果您想添加供应商 API 密钥（OpenAI、Gemini 等），",
        '   请在主菜单中选择 "3. 🔑 管理凭据"。[/bold cyan]',
    ],
    "warn_setting_change": "⚠️  WARNING: 您即将更改 {setting_name}",
    "warn_not_sure": "[bold]如果您不确定是否要更改 - 请不要更改。[/bold]",

    "enter_new_host": "请输入新的主机 IP",
    "host_updated": "\n[green]✅ 主机已更新为: {host}[/green]",
    "enter_new_port": "请输入新的端口",
    "port_updated": "\n[green]✅ 端口已更新为: {port}[/green]",
    "port_invalid": "\n[red]❌ 端口必须在 1-65535 之间[/red]",
    "enter_new_api_key": "请输入新的代理 API 密钥（留空以禁用认证）",
    "auth_will_be_disabled": "\n[bold red]⚠️  认证将被禁用 - 任何人都可以访问您的代理！[/bold red]",
    "press_enter": "按回车键继续",
    "api_key_updated": "\n[green]✅ 代理 API 密钥更新成功！[/green]",
    "api_key_updated_in_env": "   已更新到 .env 文件",
    "api_key_cleared": "\n[yellow]⚠️  代理 API 密钥已清除 - 认证已禁用！[/yellow]",
    "trans_log_toggled": "\n[green]✅ 事务日志已{status}！[/green]",
    "raw_log_toggled": "\n[green]✅ 原始I/O日志已{status}！[/green]",

    # Reset defaults
    "reset_defaults_title": "设置（恢复默认值）",
    "reset_defaults_warning": "这将把所有代理设置恢复为默认值：",
    "reset_setting_col": "[bold]   设置              当前值                →  默认值[/bold]",
    "reset_break_warning": "[bold red]⚠️  这可能导致使用当前设置的应用程序连接失败！[/bold red]",
    "all_settings_reset": "\n[green]✅ 所有设置已恢复为默认值！[/green]",

    # Provider Settings Menu
    "provider_settings_title": "📊 供应商与高级设置",
    "configured_providers": "📊 已配置的供应商",
    "no_providers_configured": "   [dim]未配置任何供应商[/dim]",
    "custom_api_bases": "🌐 自定义 API 地址",
    "provider_model_defs": "📦 供应商模型定义",
    "concurrency_limits": "⚡ 并发限制",
    "model_filters": "🎯 模型过滤器",
    "provider_specific_settings": "🔬 供应商特定设置",
    "launch_settings_tool_hint": "   [dim]启动设置工具以查看/配置供应商特定设置[/dim]",
    "actions_title": "💡 操作",
    "launch_settings_tool": "1. 🔧 启动设置工具      （配置高级设置）",
    "back_to_main": "2. ↩️  返回主菜单",
    "advanced_in_env": "[dim]ℹ️  高级设置存储在 .env 文件中。\n   使用设置工具进行交互式配置。[/dim]",
    "settings_tool_note": "[dim]⚠️  注意：设置工具仅支持常见的配置类型。\n   复杂设置请直接编辑 .env 文件。[/dim]",

    # Credential tool
    "credential_tool_header": "交互式凭据管理工具",
    "loading_credential_components": "加载凭据管理组件...",
    "initializing_credential_tool": "正在初始化凭据工具...",
    "credential_tool_initialized": "✓ 凭据工具已初始化",
    "tool_ready": "✓ 工具就绪，耗时 {elapsed:.2f}s（{count} 个供应商可用）",

    # Settings tool launch
    "settings_tool_header": "高级设置配置工具",
    "initializing_settings_tool": "正在初始化设置工具...",
    "settings_tool_ready": "✓ 设置工具就绪，耗时 {elapsed:.2f}s",

    # Quota viewer launch
    "quota_viewer_header": "配额与使用统计查看器",

    # About
    "about_title": "ℹ️  关于 LLM API 密钥代理",
    "project_info": "📦 项目信息",
    "about_description_1": "   一个轻量级、高性能的代理服务器，用于管理",
    "about_description_2": "   LLM API 密钥，支持自动轮换和 OAuth 认证",
    "key_features": "✨ 主要特性",
    "feature_rotation": "   • [green]智能密钥轮换[/green] - 在多个 API 密钥之间自动轮换",
    "feature_oauth": "   • [green]OAuth 支持[/green] - 支持供应商的自动 OAuth 流程",
    "feature_providers": "   • [green]多供应商支持[/green] - 支持 10+ 个 LLM 供应商",
    "feature_custom": "   • [green]自定义供应商[/green] - 轻松集成自定义 OpenAI 兼容 API",
    "feature_filtering": "   • [green]高级过滤[/green] - 按供应商设置模型白名单和忽略列表",
    "feature_concurrency": "   • [green]并发控制[/green] - 每个密钥的速率限制和请求管理",
    "feature_cost": "   • [green]费用追踪[/green] - 跨所有供应商追踪使用量和费用",
    "feature_tui": "   • [green]交互式 TUI[/green] - 美观的终端界面，方便配置",
    "license_credits": "📝 许可与致谢",
    "made_with_love": "   由社区用 ❤️  构建",
    "open_source": "   开源项目 - 欢迎贡献！",

    # Run proxy
    "setup_required_run": (
        "⚠️  [bold yellow]需要先完成配置[/bold yellow]\n\n"
        "无法在没有 .env 的情况下启动。\n"
        "正在启动凭据工具..."
    ),
    "proxy_key_still_not_set": "\n[red]❌ PROXY_API_KEY 仍未设置。无法启动代理。[/red]",
    "starting_proxy": "\n[bold green]🚀 正在启动代理服务器 {host}:{port}...[/bold green]\n",

    # ── Settings Tool ────────────────────────────────────────────────────────
    "st_title": "⚙️  高级设置配置",
    "st_config_categories": "⚙️  配置类别",
    "st_custom_provider_bases": "1. 🌐 自定义供应商 API 地址",
    "st_provider_model_defs": "2. 📦 供应商模型定义",
    "st_concurrency_limits": "3. ⚡ 并发限制",
    "st_rotation_modes": "4. 🔄 轮换模式",
    "st_provider_settings": "5. 🔬 供应商特定设置",
    "st_model_filters": "6. 🎯 模型过滤器（忽略/白名单）",
    "st_save_exit": "7. 💾 保存并退出",
    "st_exit_no_save": "8. 🚫 不保存退出",

    # Custom providers
    "st_custom_providers_title": "🌐 自定义供应商 API 地址",
    "st_configured_custom": "📋 已配置的自定义供应商",
    "st_no_custom_providers": "   [dim]未配置自定义供应商[/dim]",
    "st_actions": "⚙️  操作",
    "st_add_provider": "1. ➕ 添加新的自定义供应商",
    "st_edit_provider": "2. ✏️  编辑已有供应商",
    "st_remove_provider": "3. 🗑️  移除供应商",
    "st_back_settings": "4. ↩️  返回设置菜单",
    "st_provider_name_prompt": "供应商名称（例如 'opencode'）",
    "st_api_base_prompt": "API 基础 URL",
    "st_provider_staged": "\n[green]✅ 自定义供应商 '{name}' 已暂存！[/green]",
    "st_provider_usage_hint": "   使用方法: 在凭据中设置 {key}",
    "st_no_providers_edit": "\n[yellow]没有可编辑的供应商[/yellow]",
    "st_select_provider_edit": "\n[bold]选择要编辑的供应商：[/bold]",
    "st_current_api_base": "\n当前 API 地址: {base}",
    "st_new_api_base": "新的 API 地址 [按回车保持当前值]",
    "st_provider_updated": "\n[green]✅ 自定义供应商 '{name}' 已更新！[/green]",
    "st_no_providers_remove": "\n[yellow]没有可移除的供应商[/yellow]",
    "st_select_provider_remove": "\n[bold]选择要移除的供应商：[/bold]",
    "st_confirm_remove": "确定移除 '{name}'？",
    "st_pending_cancelled": "\n[green]✅ 已取消 '{name}' 的待处理添加！[/green]",
    "st_provider_marked_remove": "\n[green]✅ 供应商 '{name}' 已标记为移除！[/green]",

    # Model definitions
    "st_model_defs_title": "📦 供应商模型定义",
    "st_configured_models": "📋 已配置的供应商模型",
    "st_no_model_defs": "   [dim]未配置模型定义[/dim]",
    "st_add_models": "1. ➕ 为供应商添加模型",
    "st_edit_models": "2. ✏️  编辑供应商模型",
    "st_view_models": "3. 👁️  查看供应商模型",
    "st_remove_models": "4. 🗑️  移除供应商模型",
    "st_back_settings_5": "5. ↩️  返回设置菜单",
    "st_select_provider": "\n[bold]选择供应商：[/bold]",
    "st_enter_custom_name": "输入自定义供应商名称",
    "st_provider_name": "供应商名称",
    "st_model_define_mode": "\n如何定义模型？",
    "st_simple_list": "1. 简单列表（仅名称）",
    "st_advanced_mode": "2. 高级模式（名称、ID 和选项）",
    "st_select_mode": "选择模式",
    "st_model_name_prompt": "\n模型名称（输入 'done' 完成）",
    "st_model_id_prompt": "模型 ID [按回车使用 '{name}']",
    "st_add_model_options": "添加模型选项（如温度限制）？",
    "st_enter_options": "\n输入 key=value 对（每行一个，输入 'done' 完成）：",
    "st_option_prompt": "选项",
    "st_models_saved": "\n[green]✅ 供应商 '{provider}' 的模型定义已保存！[/green]",
    "st_no_models_added": "\n[yellow]未添加任何模型[/yellow]",
    "st_editing_models": "[bold]正在编辑供应商: {provider} 的模型[/bold]\n",
    "st_current_models": "当前模型:",
    "st_options_label": "\n选项:",
    "st_add_new_model": "1. 添加新模型",
    "st_edit_existing": "2. 编辑已有模型",
    "st_remove_model": "3. 移除模型",
    "st_done": "4. 完成",
    "st_new_model_name": "新模型名称",
    "st_model_id": "模型 ID",
    "st_select_model_edit": "\n[bold]选择要编辑的模型：[/bold]",
    "st_select_model_remove": "\n[bold]选择要移除的模型：[/bold]",
    "st_models_updated": "\n[green]✅ 供应商 '{provider}' 的模型已更新！[/green]",
    "st_no_models_left": "\n[yellow]没有剩余模型 - 正在移除定义[/yellow]",
    "st_no_providers_edit_models": "\n[yellow]没有可编辑的供应商[/yellow]",
    "st_no_providers_view": "\n[yellow]没有可查看的供应商[/yellow]",
    "st_no_providers_remove_models": "\n[yellow]没有可移除的供应商[/yellow]",
    "st_no_models_found": "\n[yellow]未找到供应商 '{provider}' 的模型[/yellow]",
    "st_select_provider_view": "\n[bold]选择要查看的供应商：[/bold]",
    "st_provider_label": "[bold]供应商: {provider}[/bold]\n",
    "st_configured_models_view": "[bold]📦 已配置的模型：[/bold]",
    "st_select_remove_models": "\n[bold]选择要移除模型的供应商：[/bold]",
    "st_confirm_remove_models": "确定移除供应商 '{provider}' 的所有模型定义？",
    "st_pending_models_cancelled": "\n[green]✅ 已取消 '{provider}' 的待处理模型！[/green]",
    "st_models_marked_removal": "\n[green]✅ 供应商 '{provider}' 的模型定义已标记为移除！[/green]",
    "st_no_creds_found": "\n[yellow]未找到有凭据的供应商。请先添加凭据。[/yellow]",

    # Model filter GUI
    "st_launching_filter_gui": "\n[cyan]正在启动模型过滤器 GUI...[/cyan]\n",
    "st_gui_close_hint": "[dim]GUI 将在新窗口中打开。关闭它即可返回此处。[/dim]\n",
    "st_gui_import_error": "\n[red]启动模型过滤器 GUI 失败: {error}[/red]",
    "st_install_ctk": "[yellow]请确保已安装 'customtkinter'：[/yellow]",
    "st_pip_install_ctk": "  [cyan]pip install customtkinter[/cyan]",

    # Concurrency
    "st_concurrency_title": "⚡ 并发限制",
    "st_current_concurrency": "📋 当前并发设置",
    "st_add_concurrency": "1. ➕ 为供应商添加并发限制",
    "st_edit_concurrency": "2. ✏️  编辑已有限制",
    "st_remove_concurrency": "3. 🗑️  移除限制（恢复默认）",
    "st_back_settings_4": "4. ↩️  返回设置菜单",
    "st_max_concurrent": "每个密钥最大并发请求数 (1-100)",
    "st_limit_staged": "\n[green]✅ 供应商 '{provider}' 的并发限制已暂存: {limit} 请求/密钥[/green]",
    "st_limit_invalid": "\n[red]❌ 限制必须在 1-100 之间[/red]",
    "st_no_limits_edit": "\n[yellow]没有可编辑的限制[/yellow]",
    "st_no_limits_remove": "\n[yellow]没有可移除的限制[/yellow]",
    "st_current_limit": "\n当前限制: {limit} 请求/密钥",
    "st_new_limit": "新限制 (1-100) [按回车保持当前值]",
    "st_limit_updated": "\n[green]✅ 供应商 '{provider}' 的并发限制已更新: {limit} 请求/密钥[/green]",
    "st_limit_must_be": "\n[red]限制必须在 1-100 之间[/red]",
    "st_select_provider_remove_limit": "\n[bold]选择要移除限制的供应商：[/bold]",
    "st_confirm_remove_limit": "确定移除供应商 '{provider}' 的并发限制（恢复为默认值 1）？",
    "st_pending_limit_cancelled": "\n[green]✅ 已取消 '{provider}' 的待处理限制！[/green]",
    "st_limit_marked_removal": "\n[green]✅ 供应商 '{provider}' 的限制已标记为移除[/green]",

    # Rotation modes
    "st_rotation_title": "🔄 轮换模式",
    "st_rotation_explained": "📋 轮换模式说明",
    "st_rotation_balanced": "   [cyan]balanced[/cyan]   - 在请求之间均匀轮换凭据（默认）",
    "st_rotation_sequential": "   [cyan]sequential[/cyan] - 使用一个凭据直到耗尽（429），然后切换",
    "st_current_rotation": "📋 当前轮换模式设置",
    "st_set_rotation": "1. ➕ 为供应商设置轮换模式",
    "st_reset_rotation": "2. 🗑️  恢复供应商默认值",
    "st_config_priority": "3. ⚡ 配置优先级并发倍率",
    "st_rotation_back": "4. ↩️  返回设置菜单",
    "st_current_mode_for": "\n供应商 {provider} 的当前模式: [cyan]{mode}[/cyan]",
    "st_select_rotation": "\n选择新的轮换模式:",
    "st_balanced_desc": "   1. [blue]balanced[/blue] - 均匀轮换凭据",
    "st_sequential_desc": "   2. [green]sequential[/green] - 使用直到耗尽",
    "st_rotation_staged": "\n[green]✅ 供应商 '{provider}' 的轮换模式已暂存为 {mode}！[/green]",
    "st_no_custom_rotation": "\n[yellow]没有自定义轮换模式可重置[/yellow]",
    "st_select_reset_rotation": "\n[bold]选择要恢复默认的供应商：[/bold]",
    "st_confirm_reset_rotation": "确定将 '{provider}' 恢复为默认模式 ({mode})？",
    "st_rotation_cancelled": "\n[green]✅ 已取消 '{provider}' 的待处理模式！[/green]",
    "st_rotation_reset": "\n[green]✅ 供应商 '{provider}' 的轮换模式已标记为恢复默认 ({mode})！[/green]",

    # Priority multipliers
    "st_priority_title": "⚡ 优先级并发倍率",
    "st_current_priority": "📋 当前优先级倍率设置",
    "st_no_priority_settings": "   [dim]未配置优先级倍率[/dim]",
    "st_about_priority": "ℹ️  关于优先级倍率：",
    "st_priority_desc": "   更高优先级层级（较小数字）可以有更高的倍率。",
    "st_priority_example": "   示例: 优先级 1 = 5x, 优先级 2 = 3x, 其他 = 1x",
    "st_set_priority": "1. ✏️  设置优先级倍率",
    "st_reset_priority": "2. 🔄 恢复供应商默认值",
    "st_priority_back": "3. ↩️  返回",
    "st_no_providers_available": "\n[yellow]没有可用的供应商[/yellow]",
    "st_provider_prompt": "供应商",
    "st_priority_level": "优先级层级（例如 1, 2, 3）",
    "st_current_multiplier": "\n优先级 {priority} 的当前倍率: {current}x",
    "st_new_multiplier": "新倍率 (1-10)",
    "st_multiplier_set": "\n[green]✅ 供应商 '{provider}' 的优先级 {priority} 倍率已设为 {multiplier}x[/green]",
    "st_multiplier_invalid": "\n[yellow]倍率必须在 1 到 10 之间[/yellow]",
    "st_no_custom_multipliers": "\n[yellow]没有自定义倍率可重置[/yellow]",
    "st_select_reset_provider": "\n[bold]选择要重置的供应商：[/bold]",
    "st_priority_reset": "\n[green]✅ 已将供应商 '{provider}' 的优先级 {priority} 重置为默认值 ({default}x)[/green]",
    "st_no_override_for": "\n[yellow]优先级 {priority} 没有自定义覆盖[/yellow]",

    # Provider specific settings
    "st_provider_specific_title": "🔬 供应商特定设置 - {provider}",
    "st_available_providers": "📋 可配置的供应商",
    "st_select_provider_config": "⚙️  选择要配置的供应商",
    "st_current_settings": "📋 当前设置",
    "st_mod_legend": "[dim]* = 已修改, + = 待添加, ~ = 待编辑, - = 待重置[/dim]",
    "st_edit_setting": "E. ✏️  编辑设置",
    "st_reset_setting": "R. 🔄 重置为默认值",
    "st_reset_all_settings": "A. 🔄 全部恢复默认",
    "st_back_provider": "B. ↩️  返回供应商选择",
    "st_select_action": "选择操作",
    "st_select_setting": "\n[bold]选择要编辑的设置编号：[/bold]",
    "st_setting_number": "设置编号",
    "st_editing": "\n[bold]正在编辑: {key}[/bold]",
    "st_current_value": "当前值: [cyan]{value}[/cyan]",
    "st_default_value": "默认值: [dim]{value}[/dim]",
    "st_type_label": "类型: {type}",
    "st_enable_setting": "\n启用此设置？",
    "st_new_value": "\n新值",
    "st_setting_enabled": "\n[green]✅ {key} 已启用！[/green]",
    "st_setting_disabled": "\n[green]✅ {key} 已禁用！[/green]",
    "st_setting_set": "\n[green]✅ {key} 已设为 {value}！[/green]",
    "st_setting_updated": "\n[green]✅ {key} 已更新！[/green]",
    "st_select_setting_reset": "\n[bold]选择要重置的设置编号：[/bold]",
    "st_confirm_reset_setting": "\n确定将 {key} 恢复为默认值 ({default})？",
    "st_setting_reset": "\n[green]✅ {key} 已恢复为默认值！[/green]",
    "st_confirm_reset_all": "\n[bold red]确定将所有 {provider} 设置恢复为默认值？[/bold red]",
    "st_all_reset": "\n[green]✅ 所有 {provider} 设置已恢复为默认值！[/green]",

    # Save & Exit
    "st_review_title": "💾 审查并保存更改",
    "st_pending_status": "待处理更改",
    "st_confirm_save": "\n[bold yellow]保存所有待处理更改？[/bold yellow]",
    "st_all_saved": "\n[green]✅ 所有更改已保存到 .env！[/green]",
    "st_changes_not_saved": "\n[yellow]更改未保存[/yellow]",
    "st_no_changes": "\n[dim]没有要保存的更改[/dim]",
    "st_confirm_discard": "\n[bold red]确定放弃所有待处理更改？[/bold red]",
    "st_changes_discarded": "\n[yellow]更改已放弃[/yellow]",

    # ── Quota Viewer ─────────────────────────────────────────────────────────
    "qv_title": "📈 配额与使用统计",
    "qv_global_label": "[magenta]📊 全局/累计[/magenta]",
    "qv_current_label": "[cyan]📈 当前周期[/cyan]",
    "qv_connected_to": "已连接: [bold]{name}[/bold] ({connection})",
    "qv_no_data": "[yellow]无数据可用。按 R 重新加载。[/yellow]",
    "qv_total": "[bold]合计:[/bold] {creds} 个凭据 | ",

    # Quota viewer table headers
    "qv_col_provider": "供应商",
    "qv_col_creds": "凭据",
    "qv_col_quota_status": "配额状态",
    "qv_col_requests": "请求数",
    "qv_col_tokens": "令牌 (输入/输出)",
    "qv_col_cost": "费用",

    # Quota viewer menu
    "qv_view_details": "查看 [cyan]{provider}[/cyan] 详情",
    "qv_toggle_view": "G. 切换查看模式（当前/全局）",
    "qv_reload_stats": "R. 重新加载所有统计（从代理重新读取）",
    "qv_switch_remote": "S. 切换远程服务器",
    "qv_manage_remotes": "M. 管理远程服务器",
    "qv_back": "B. 返回主菜单",

    # Provider detail
    "qv_detail_title": "📊 {provider} - 详细统计",
    "qv_no_creds_for_provider": "[dim]该供应商没有配置凭据。[/dim]",
    "qv_toggle_view_detail": "G.  切换查看模式（当前/全局）",
    "qv_reload_cache": "R.  重新加载统计（从代理缓存）",
    "qv_reload_all": "RA. 重新加载所有统计",
    "qv_force_refresh": "F.  [yellow]强制刷新所有 {provider} 配额（从 API）[/yellow]",
    "qv_force_refresh_single": "F{idx}. 仅强制刷新 [{idx}] ({email})",
    "qv_back_summary": "B.  返回汇总",

    # Connection error
    "qv_connection_error_title": "❌ 连接错误",
    "qv_connection_error_body": (
        "[bold red]无法连接到代理服务器[/bold red]\n\n"
        "可能的原因：\n"
        "  • 代理服务器未运行\n"
        "  • 主机/端口配置不正确\n"
        "  • API 密钥不正确或缺失"
    ),
    "qv_switch_remote_menu": "S. 切换到其他远程服务器",
    "qv_manage_remotes_menu": "M. 管理远程服务器（添加/编辑/删除）",
    "qv_retry": "R. 重试连接",

    # Remote management
    "qv_switch_remote_title": "🔄 切换远程服务器",
    "qv_current_remote": "当前: [bold]{name}[/bold]",
    "qv_available_remotes": "可用的远程服务器:",
    "qv_select_remote": "选择远程服务器 (1-{count}) 或 B 返回",
    "qv_manage_title": "⚙️ 管理远程服务器",
    "qv_add_remote": "A. 添加新远程服务器",
    "qv_edit_remote": "E. 编辑远程服务器（输入编号，如 E1）",
    "qv_delete_remote": "D. 删除远程服务器（输入编号，如 D1）",
    "qv_set_default": "S. 设置默认远程服务器",
    "qv_back_manage": "B. 返回",

    # Add/Edit/Delete remote
    "qv_add_remote_title": "[bold]添加新远程服务器[/bold]",
    "qv_url_hint": "[dim]对于完整 URL（如 https://api.example.com/v1），端口留空[/dim]",
    "qv_name_prompt": "名称",
    "qv_host_prompt": "主机（或完整 URL）",
    "qv_port_prompt": "端口（完整 URL 留空）",
    "qv_api_key_prompt": "API 密钥（可选）",
    "qv_remote_added": "[green]已添加远程服务器 '{name}'。[/green]",
    "qv_remote_exists": "[red]远程服务器 '{name}' 已存在。[/red]",
    "qv_edit_remote_title": "[bold]编辑远程服务器: {name}[/bold]",
    "qv_edit_hint": "[dim]按回车保持当前值。对于完整 URL，端口留空。[/dim]",
    "qv_remote_updated": "[green]远程服务器已更新。[/green]",
    "qv_remote_update_failed": "[red]更新远程服务器失败。[/red]",
    "qv_no_changes": "[dim]未做任何更改。[/dim]",
    "qv_delete_confirm": "[yellow]确定删除远程服务器 '{name}'？[/yellow]",
    "qv_type_yes": "输入 'yes' 确认",
    "qv_remote_deleted": "[green]已删除远程服务器 '{name}'。[/green]",
    "qv_cannot_delete": "[red]无法删除。至少需要保留一个远程服务器。[/red]",
    "qv_set_default_prompt": "设置默认 (1-{count})",
    "qv_default_set": "[green]'{name}' 已设为默认。[/green]",
    "qv_default_failed": "[red]设置默认失败。[/red]",

    # Auth
    "qv_auth_required": "[yellow]需要认证或连接失败。[/yellow]",
    "qv_enter_api_key": "请输入 API 密钥（或按回车取消）",
    "qv_still_failed": "[red]仍然失败: {error}[/red]",
    "qv_no_remotes": "[red]未配置远程服务器。[/red]",

    # Credential panel
    "qv_exhausted": "[red]⛔ 已耗尽[/red]",
    "qv_cooldown": "[yellow]⚠️ 冷却中 ({time})[/yellow]",
    "qv_cooldown_short": "[yellow]⚠️ 冷却中[/yellow]",
    "qv_active": "[green]✅ 活跃[/green]",
    "qv_active_cooldowns": "[yellow]活跃的冷却：[/yellow]",
    "qv_models_used": "  [dim]已使用的模型：[/dim]",
    "qv_resets": "⛔ 重置时间: {time}",
    "qv_exhausted_label": "⛔ 已耗尽",
    "qv_low_warning": "⚠️ 偏低",
    "qv_resets_label": "重置时间: {time}",
    "qv_press_enter": "按回车继续",
    "qv_refreshed": "\n[green]已刷新 {count} 个凭据 ",

    # Time formatting
    "time_never": "从未",
    "time_unknown": "未知",
    "time_s_ago": "{n}秒前",
    "time_min_ago": "{n}分钟前",
    "time_h_ago": "{n}小时前",
    "time_d_ago": "{n}天前",

    # ── Model Filter GUI ─────────────────────────────────────────────────────
    "fg_window_title": "模型过滤器配置",
    "fg_header": "🎯 模型过滤器配置",
    "fg_help_button": "?",
    "fg_refresh": "🔄 刷新",
    "fg_provider_label": "供应商:",
    "fg_search_placeholder": "搜索模型...",
    "fg_all_models": "所有已获取的模型",
    "fg_filtered_status": "过滤状态",
    "fg_no_models": "无模型",
    "fg_loading": "加载中...",
    "fg_fetching": "正在从 {provider} 获取模型...",
    "fg_retry": "重试",
    "fg_copy": "复制",
    "fg_available": "{count} 个可用",
    "fg_select_provider": "选择供应商开始",
    "fg_no_providers": "未找到带有凭据的供应商。请先在 .env 中添加 API 密钥。",
    "fg_loading_all": "正在加载所有供应商的模型...",
    "fg_no_models_loaded": "未加载任何模型",
    "fg_save_success": "✅ 更改保存成功！",
    "fg_save_failed": "❌ 保存更改失败",
    "fg_changes_discarded": "更改已放弃",
    "fg_unsaved_changes": "● 未保存的更改",
    "fg_fetch_failed": "获取模型失败: {error}",

    # Rules
    "fg_ignore_rules": "🚫 忽略规则",
    "fg_whitelist_rules": "✓ 白名单规则",
    "fg_no_rules": "未配置规则\n在下方添加模式",
    "fg_add_button": "+ 添加",
    "fg_import_button": "导入",
    "fg_pattern_placeholder": "pattern1, pattern2*, ...",
    "fg_discard_button": "↩️ 放弃",
    "fg_save_button": "💾 保存",

    # Context menu
    "fg_add_to_ignore": "➕ 添加到忽略列表",
    "fg_add_to_whitelist": "➕ 添加到白名单",
    "fg_view_affecting_rule": "🔍 查看影响此模型的规则",
    "fg_copy_model_name": "📋 复制模型名称",

    # Unsaved changes dialog
    "fg_unsaved_title": "未保存的更改",
    "fg_unsaved_text": "您有未保存的过滤器更改。\n您想怎么做？",

    # Import dialog
    "fg_import_instruction": "在下方粘贴逗号分隔的模式（将替换所有现有规则）：",
    "fg_import_example": "示例: gpt-4*, claude-3*, model-name",
    "fg_replace_all": "全部替换",

    # Import result
    "fg_got_it": "知道了！",
    "fg_ok": "确定",

    # Help content
    "fg_help_title": "📖 模型过滤指南",
    "fg_help_overview_title": "🎯 概述",
    "fg_help_overview": (
        "模型过滤允许您控制每个供应商通过代理可用的模型。\n\n"
        "• 使用忽略列表来阻止特定模型\n"
        "• 使用白名单确保特定模型始终可用\n"
        "• 白名单始终优先于忽略列表"
    ),
    "fg_help_priority_title": "⚖️ 过滤优先级",
    "fg_help_priority": (
        "检查模型时使用以下顺序：\n\n"
        "1. 白名单检查\n"
        "   如果模型匹配任何白名单模式 → 可用\n"
        "   （白名单覆盖一切）\n\n"
        "2. 忽略检查\n"
        "   如果模型匹配任何忽略模式 → 已阻止\n\n"
        "3. 默认\n"
        "   如果没有匹配的模式 → 可用"
    ),
    "fg_help_syntax_title": "✏️ 模式语法",
    "fg_help_syntax": (
        "支持完整的通配符模式：\n\n"
        "精确匹配\n"
        "  模式: gpt-4\n"
        "  匹配: 仅 \"gpt-4\"\n\n"
        "前缀通配\n"
        "  模式: gpt-4*\n"
        "  匹配: \"gpt-4\", \"gpt-4-turbo\", \"gpt-4-preview\" 等\n\n"
        "后缀通配\n"
        "  模式: *-preview\n"
        "  匹配: \"gpt-4-preview\", \"o1-preview\" 等\n\n"
        "包含通配\n"
        "  模式: *-preview*\n"
        "  匹配: 包含 \"-preview\" 的任何内容\n\n"
        "匹配所有\n"
        "  模式: *\n"
        "  匹配: 该供应商的每个模型\n\n"
        "单字符\n"
        "  模式: gpt-?\n"
        "  匹配: \"gpt-4\", \"gpt-5\" 等\n\n"
        "字符集\n"
        "  模式: gpt-[45]*\n"
        "  匹配: \"gpt-4\", \"gpt-4-turbo\", \"gpt-5\" 等"
    ),
    "fg_help_examples_title": "💡 常用模式",
    "fg_help_examples": (
        "阻止所有，允许特定：\n"
        "  忽略:    *\n"
        "  白名单: gpt-4o, gpt-4o-mini\n"
        "  结果:    仅 gpt-4o 和 gpt-4o-mini 可用\n\n"
        "阻止预览模型：\n"
        "  忽略:    *-preview, *-preview*\n"
        "  结果:    所有预览版本被阻止\n\n"
        "阻止特定系列：\n"
        "  忽略:    o1*, dall-e*\n"
        "  结果:    所有 o1 和 DALL-E 模型被阻止\n\n"
        "仅允许最新版：\n"
        "  忽略:    *\n"
        "  白名单: *-latest\n"
        "  结果:    仅以 \"-latest\" 结尾的模型可用"
    ),
    "fg_help_interface_title": "🖱️ 界面指南",
    "fg_help_interface": (
        "供应商下拉\n"
        "  选择要配置的供应商\n\n"
        "模型列表\n"
        "  • 左侧: 所有已获取的模型（未过滤）\n"
        "  • 右侧: 带彩色状态的相同模型\n"
        "  • 绿色 = 可用（正常）\n"
        "  • 红/橙色调 = 已阻止（忽略）\n"
        "  • 蓝/青色调 = 已白名单\n\n"
        "搜索框\n"
        "  快速过滤两个列表以查找特定模型\n\n"
        "点击模型\n"
        "  • 左键: 高亮影响该模型的规则\n"
        "  • 右键: 带快捷操作的上下文菜单\n\n"
        "点击规则\n"
        "  • 高亮该规则影响的所有模型\n"
        "  • 显示哪些模型将被阻止/允许\n\n"
        "规则输入（合并模式）\n"
        "  • 输入逗号分隔的模式\n"
        "  • 仅添加未被现有规则覆盖的模式\n"
        "  • 按添加或回车创建规则\n\n"
        "导入按钮（替换模式）\n"
        "  • 用导入的规则替换所有现有规则\n"
        "  • 粘贴逗号分隔的模式\n\n"
        "删除规则\n"
        "  • 点击任何规则上的 × 按钮移除"
    ),
    "fg_help_shortcuts_title": "⌨️ 键盘快捷键",
    "fg_help_shortcuts": (
        "Ctrl+S     保存更改\n"
        "Ctrl+R     从供应商刷新模型\n"
        "Ctrl+F     聚焦搜索框\n"
        "F1         打开此帮助窗口\n"
        "Escape     清除搜索 / 关闭对话框"
    ),
    "fg_help_saving_title": "💾 保存更改",
    "fg_help_saving": (
        "更改将以以下格式保存到您的 .env 文件：\n\n"
        "  IGNORE_MODELS_OPENAI=pattern1,pattern2*\n"
        "  WHITELIST_MODELS_OPENAI=specific-model\n\n"
        "点击 \"保存\" 持久化更改，或 \"放弃\" 还原。\n"
        "关闭窗口时如有未保存的更改会提示您。"
    ),
}


def t(key: str, **kwargs) -> str:
    """
    Get translated string by key.

    Args:
        key: Translation key
        **kwargs: Format arguments for the string

    Returns:
        Translated string, or the key itself if not found
    """
    text = _TRANSLATIONS.get(key, key)
    if kwargs and isinstance(text, str):
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def t_list(key: str) -> list:
    """
    Get translated list by key.

    Args:
        key: Translation key

    Returns:
        Translated list, or [key] if not found
    """
    result = _TRANSLATIONS.get(key, [key])
    if isinstance(result, list):
        return result
    return [result]
