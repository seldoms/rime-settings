# 复制这段，让 Agent 帮你装好 🪄

将下面整段交给具有本机终端权限的编程 Agent（如 Codex、Claude Code）。
Agent 需要遵守自身的沙箱和审批规则；系统安装遇到审批时走工具的正常审批流程。

```text
请在这台 Linux 桌面上安装并验证「雾凇拼音设置」：
https://github.com/seldoms/rime-settings

我授权完成这次安装所需的依赖安装、非破坏性用户级配置修改和验证。
请实际动手完成，不要只给我一份命令清单；先检查，再备份，再安装，最后验证。
不得绕过沙箱、审批、项目 AGENTS.md 或系统权限控制。

1. 确认环境
   - 读取 /etc/os-release、桌面环境、Wayland/X11、桌面登录用户。
   - 检查正在运行的 IBus/Fcitx、桌面输入源、ibus engine、Rime 用户目录。
   - 注意 Agent 可能以 root 运行：图形操作和配置必须以真实桌面用户身份执行，
     使用其现有会话总线；不要把 root 的空配置当成桌面用户配置。
   - 此项目面向 IBus-Rime + 雾凇拼音；Ubuntu 24.04+ / GNOME 是推荐起点。
     本项目实测 Ubuntu 26.04.1，其他环境需现场验证。
   - 如果用户已经在用 Fcitx5-Rime 或其他输入法，不要擅自切换框架、卸载软件、
     改环境变量或假装本工具兼容 Fcitx5。先说明范围，并只询问是否迁移到 IBus-Rime。
     依赖版本不足时不要升级整个操作系统或引入不明 PPA；报告缺少项。

2. 下载并检查
   - 将 https://github.com/seldoms/rime-settings 克隆到用户可写的独立源码目录。
     避开 ~/.local/share/rime-settings（这是默认安装目标），不要覆盖已有工作区。
   - 读取 README.md、INSTALL_WITH_AGENT.md 和适用的 AGENTS.md。
   - 使用官方软件源，不执行未经检查的 curl | bash 或第三方一键脚本。

3. 先备份
   - 在用户目录中新建带时间戳的备份目录。
   - 记录当前 GNOME input-sources 的 sources、mru-sources、per-window 等设置；
     备份现有 .xinputrc 和 ~/.config/ibus/rime（如果存在）。
   - 不删除用户词库、个人短语、已有 .custom.yaml，也不把个人数据提交到 GitHub。

4. 安装依赖和输入法
   - Ubuntu/Debian 的典型依赖：
     ibus-rime librime-plugin-lua python3-gi python3-yaml
     gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-ibus-1.0
     可选部署工具 librime-bin；下载源码需要 git。
   - 先检查 apt 安装计划，不允许为此移除现有软件包；缺少 sudo/审批就按规则处理。
   - Python 使用 /usr/bin/python3；要求 GTK 4、libadwaita >= 1.4。
   - 如果已经安装雾凇，保留原方案列表、词库和定制，不做整目录覆盖。
   - 仅当尚未安装雾凇时，从 https://github.com/iDvel/rime-ice 官方仓库下载，
     阅读其安装说明；把配置、词库、Lua 和 OpenCC 数据部署到
     ~/.config/ibus/rime。若目标目录已有内容，先备份，再有选择地合并；
     禁止直接清空目录。通过 default.custom.yaml 启用 rime_ice，保留其他配置。
     不必额外下载语法模型，也不要默认为用户开启云输入。
   - 在真实桌面会话中注册/启用 Rime。只有需要时才重新加载 IBus，
     保留已有键盘布局和其他输入源；不能重启或注销用户桌面。

5. 安装界面
   - 在源码目录运行 /usr/bin/python3 install.py --check。
   - 再以桌面用户运行 /usr/bin/python3 install.py，不要 sudo 运行安装脚本。
   - 安装器只安装设置界面和应用菜单入口，不会自动安装 Rime 或词库。
   - 从应用菜单「雾凇拼音设置」或安装器输出的 Python 路径打开界面。
   - 不擅自改变候选词数量、排列或 Shift 习惯；初次部署保持上游默认或用户原值。

6. 验证并交付
   - 运行 /usr/bin/python3 -m unittest discover -s tests -v；这些测试不修改真实配置。
   - 在真实图形会话确认窗口启动、控件能读取现有配置。
   - 需要验证保存/部署时，可运行 /usr/bin/python3 check_gui.py：
     它会临时改成 9 个竖排候选词，验证后还原原始配置文件及原值；会短暂重新部署。
   - 用独立 IBus 测试上下文或本工具的试打框验证 nihao 能得到「你好」。
     不要向用户正在使用的其他窗口注入测试文字。
   - 检查 ibus engine、实际编译后的 menu/page_size 和 style/horizontal。
     保存不等于部署成功；失败时查看 Rime 日志，报告实际状态，不能宣称成功。
   - 告诉我应用怎么打开、备份在哪里，以及如何恢复原输入源。
     如果必须注销才能生效，只说明原因和剩余步骤，不替我注销。

请持续推进直到安装、启动和必要验证完成；仅在需要权限审批、确有框架迁移
等范围决策，或外部条件阻塞时停下来。不要读取、输出或上传任何凭证。
```

## 已经装了 IBus-Rime + 雾凇？短版也够用

```text
请帮我安装 https://github.com/seldoms/rime-settings 的设置界面。
先确认桌面用户正在使用 IBus-Rime + 雾凇，读取项目说明并备份现有配置。
安装缺少的官方依赖，用 /usr/bin/python3 install.py 做用户级安装，
打开「雾凇拼音设置」，验证保存和部署可用并还原测试设置。
遵守权限审批，不卸载输入法、不改动用户词库、不注销桌面。
完成后告诉我打开方式和备份位置。
```
