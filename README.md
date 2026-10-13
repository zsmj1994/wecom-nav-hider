# WeCom Nav Hider

Windows 企业微信导航栏精简工具。通过终端勾选要隐藏的导航项，保存配置后在后台运行。

使用 Python 管理启动、配置和会话，使用 Frida 加载进程内 JavaScript 拦截脚本。不修改企业微信磁盘程序文件，不修改服务端配置；退出后台程序后，刷新导航或重启企业微信可恢复。

> 当前适配 **WXWork 5.0.12.6013 / 32 位客户端**，并严格校验文件 SHA-256。自动检测安装位置不等于兼容其他版本。仍使用 5.0.11.6029 的用户请使用 v0.1.0。

## 快速开始

### EXE 便携版（推荐）

从 [GitHub Releases](https://github.com/zsmj1994/wecom-nav-hider/releases/latest) 下载 `windows-x64.zip`，完整解压到可写目录，双击 **WeComNavHider.exe**。无需安装 Python、PowerShell 或 Frida。需要 Windows 10/11 x64，企业微信仍须匹配上方指定版本。

EXE 旁边的 `_internal` 是运行库，不能删除或单独移动 EXE。首次运行自动创建 `config.json`；选择后回车即可后台运行，终端可关闭。双击 `Stop-Hiding.cmd` 停止隐藏；`Start-Background.vbs` 使用已保存配置后台启动。配置与日志保存在 EXE 同目录，升级时可保留自己的 `config.json`。

终端中可运行 `WeComNavHider.exe --check` 检查本机适配情况，或 `--self-test` 检查内置资源和 Frida（不会挂载企业微信）。程序未做代码签名。Release 附带 ZIP 的 SHA-256 校验值。

### 从源码运行

环境：Windows、PowerShell 7（`pwsh.exe`）、Python 3.10+（包含 `pythonw.exe`）。

1. 下载源码并完整解压到可写目录。
2. 双击 **Setup.cmd**，将固定版本的 Frida 安装到本目录的 `deps/`。首次安装需要联网。
3. 双击 **Start-WeCom.cmd**，在终端选择隐藏项目。
4. 按回车保存并后台运行，随后可以关闭终端。若界面尚未变化，切换导航或重新启动企业微信。

首次使用会从 `config.example.json` 创建本地 `config.json`。优先采用已保存路径，再检测注册表、PATH 和常见安装目录。找不到 Python 或企业微信时，在终端提示输入完整 EXE 路径或安装目录。留空取消。

已有手动挂载脚本或另一份启动器时，请先停止它，避免重复挂载。

## 终端操作

```text
企业微信 · 导航隐藏设置

↑/↓ 移动  空格 勾选  A 全选  N 清空
Enter 保存并后台运行  Esc/Q 取消

 > [x] 智能助理
   [ ] 邮件
   [ ] 文档
   ...
```

勾选表示隐藏。选择保存在本地，下次打开自动读取。消息入口始终保留。

| 入口 | 用途 |
| --- | --- |
| `Start-WeCom.cmd` | 选择隐藏项目，保存并后台运行 |
| `Start-WeCom.vbs` | 跳过选择，直接按已保存配置运行 |
| `Stop-Hiding.vbs` | 撤销挂载，不关闭企业微信 |
| `Setup.cmd` | 安装 Frida 依赖 |

企业微信未运行时启动器会启动它；已经运行时直接附加。企业微信退出后，后台程序结束。需要自动隐藏时请通过启动器再次启动。可以为 CMD 或 VBS 文件创建桌面快捷方式，不要单独移动这些文件。

## 配置

编辑 `config.json`，例如：

```json
{
  "hide": ["智能助理", "智能文档", "智能总结", "微盘", "高级功能"],
  "paths": {
    "wecom": "",
    "python": ""
  }
}
```

- `hide`：要隐藏的中文名称；空数组表示不隐藏任何项目。
- `paths.wecom`：`WXWork.exe` 路径，空字符串表示自动检测。
- `paths.python`：`python.exe` 路径，空字符串表示自动检测。
- TUI 保存时会写入实际检测到的路径；只修改隐藏名单不会清除路径。
- 每秒检查配置变化。有效的隐藏名单在下一次导航刷新时生效；路径变化在下次启动时使用。
- JSON 写错或保存中途文件暂不可读时，保持上次有效设置，原因记录在 `launcher.log`。
- 取消隐藏表示不再拦截该项目，不会强制显示企业微信原本禁用的入口。

可选名称：智能助理、邮件、文档、日程、待办、会议、智能文档、智能总结、工作台、通讯录、微盘、高级功能。

`config.json`、`launcher.log` 和 `deps/` 都是本地产物，已加入 `.gitignore`，不应提交到仓库。

## 兼容性与验证范围

智能助理隐藏已完成运行时和人工界面验证。智能文档、智能总结、微盘、高级功能已核对同版客户端的控件名称与运行时显示调用，完整界面验收尚未完成。其他可选项基于同版导航资源映射，尚未逐项实测。

软件更新、不同构建或不同界面库可能不兼容。哈希不匹配时停止挂载；不要仅替换哈希绕过检查。详见 [版本适配说明](docs/compatibility.md)。

这是非官方个人界面定制工具，与腾讯无隶属关系。仓库不包含企业微信二进制文件、账户数据或运行时内存转储。

## 开发与检查

在项目目录运行（PowerShell 7）：

```powershell
python -m unittest discover -s tests -v
node --check hooks/navigation.js
pwsh.exe -NoLogo -NoProfile -File ./launch.ps1 -Check
```

单元测试不启动、不附加企业微信。Node 只用于 JavaScript 语法检查，不是运行依赖。`-Check` 会检查本机安装、依赖、配置和文件哈希，但不会挂载进程。

```text
launcher.py          进程生命周期、Frida 会话、撤销
tui.py               终端选择和后台启动
settings.py          配置验证、原子保存、热加载
paths.py             安装路径与界面库检测
hooks/navigation.js  导航判断和控件显示拦截
compatibility.json   当前构建的哈希、RVA 和结构偏移
launch.ps1           Python 检测与启动引导
tests/               不依赖企业微信进程的自动检查
```

## 许可证

项目原创代码使用 [MIT License](LICENSE)。Frida 是独立依赖，其许可证不由本项目的 MIT 许可证替代。源码仓库不包含依赖二进制；Release 便携包包含 Python、Frida 和 PyInstaller 引导程序，相应许可证随包附在 `licenses/` 中。

## 构建便携版

在 Windows x64 的干净源码目录使用 Python 3.13：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-build.txt
.venv/Scripts/python.exe build_release.py
```

生成文件位于 `dist/`。构建先执行 EXE 自检，再生成 ZIP 和 `SHA256SUMS.txt`。重复构建请使用新的源码目录，避免混入旧产物。
