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

## 未来功能

*   (待添加)

## 贡献

欢迎提出 Issue 或 Pull Request。
