# SchoolHax

一个包含用于 macOS 的实用工具脚本的项目。

## 功能

### Wi-Fi 切换器 (`wifi_toggle.py`)

提供一个通过全局键盘快捷键快速开启或关闭 macOS Wi-Fi 的工具。

**依赖:**

*   Python 3
*   `pyobjc` (需要通过 pip 安装: `pip install pyobjc`)

**安装与设置:**

1.  **克隆仓库:**
    ```bash
    git clone https://github.com/molder91/SchoolHax.git
    cd SchoolHax
    ```
2.  **安装依赖:**
    ```bash
    pip install pyobjc
    # 建议在虚拟环境中使用
    # python -m venv .venv
    # source .venv/bin/activate
    # pip install pyobjc
    ```
3.  **设置快捷键:**
    使用命令行设置你想要的快捷键。请使用 `pyobjc` 兼容的格式，例如：
    ```bash
    # 设置 Command + Option + W
    python wifi_toggle.py --set-hotkey '<cmd>+<alt>+w>'

    # 设置 Command + Shift + K
    # python wifi_toggle.py --set-hotkey '<cmd>+<shift>+k>'
    ```
    *   **有效修饰键**: `<cmd>`, `<alt>`, `<option>`, `<ctrl>`, `<control>`, `<shift>`
    *   **有效按键**: 小写字母 (`a`-`z`), 数字 (`0`-`9`), 功能键 (`<f1>`-`<f12>`), 特殊键 (`<space>`, `<enter>`, `<esc>`, etc.)。具体可查看脚本内 `KEYCODE_MAP`。
4.  **授予辅助功能权限:**
    *   首次运行监听器时，macOS 可能会提示需要"辅助功能"权限。
    *   前往 "系统设置" -> "隐私与安全性" -> "辅助功能"。
    *   确保你用来运行脚本的应用程序（如"终端"）已被勾选允许。
    *   **重要:** 如果刚授予权限，请**完全退出并重启**该应用程序。

**运行:**

在终端中运行脚本以启动监听器：

```bash
python wifi_toggle.py
```

脚本会在后台运行。按下你设置的快捷键来切换 Wi-Fi。按 `Ctrl+C` 停止脚本。

### 老板键 (`boss_key.py`)

提供一个完善的"老板键"功能，通过按下特定快捷键可以：
1. 隐藏当前应用（如游戏）并切换到预设的"安全"应用（如浏览器）
2. 可选择关闭WiFi连接
3. 通过独立的恢复快捷键来恢复被隐藏的应用和WiFi连接

**依赖:**

*   Python 3
*   `pyobjc` (需要通过 pip 安装: `pip install pyobjc`)

**安装与设置:**

安装依赖与Wi-Fi切换器相同。

1.  **设置快捷键:**
    ```bash
    # 设置老板键快捷键 (默认: <cmd>+<alt>+b)
    python boss_key.py --set-boss-hotkey '<cmd>+<alt>+b>'
    
    # 设置恢复键快捷键 (默认: <cmd>+<alt>+r)
    python boss_key.py --set-restore-hotkey '<cmd>+<alt>+r>'
    ```

2.  **设置目标应用程序:**
    ```bash
    # 例如设置为Google Chrome
    python boss_key.py --set-target-app 'Google Chrome'
    ```
    **注意:** 目标应用必须已经处于运行状态，脚本当前不会自动启动它。

3.  **配置WiFi控制功能:**
    老板键支持在激活时关闭WiFi，在恢复时打开WiFi。你可以启用或禁用此功能：
    ```bash
    # 启用WiFi控制 (默认)
    python boss_key.py --enable-wifi-control
    
    # 禁用WiFi控制
    python boss_key.py --disable-wifi-control
    
    # 如果你使用的WiFi接口不是默认的en0，可以指定接口名称
    python boss_key.py --set-wifi-interface 'en1'
    ```

4.  **查看当前配置:**
    ```bash
    python boss_key.py --status
    ```

5.  **授予辅助功能权限:**
    与Wi-Fi切换器相同，需要授予Terminal（或运行脚本的应用）辅助功能权限。

**运行:**

```bash
python boss_key.py
```

**使用方法:**

1. **老板键模式** (默认: CMD+ALT+B):
   * 隐藏当前应用（如游戏）
   * 切换到指定的"安全"应用（默认为Safari）
   * 如果启用了WiFi控制，会同时关闭WiFi

2. **恢复键模式** (默认: CMD+ALT+R):
   * 恢复之前隐藏的应用
   * 如果启用了WiFi控制，会同时打开WiFi

**特性:**
- 支持两个独立的快捷键：一个用于激活"老板模式"，另一个用于恢复应用
- 可选择是否同时控制WiFi连接
- 完全从系统中隐藏应用，不会出现在Dock或应用切换器(CMD+Tab)中
- 只能通过特定的恢复快捷键来重新显示被隐藏的应用

## 未来功能

* 支持自动启动目标应用（如果尚未运行）
* 添加屏幕截图/录制功能
* 添加更多自定义选项

## 贡献

欢迎提出 Issue 或 Pull Request。
