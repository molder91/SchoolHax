import subprocess
import sys
import time
import objc # PyObjC core
from AppKit import ( # Import specific classes/constants from AppKit
    NSEvent,
    NSKeyDownMask,
    NSKeyUpMask,
    NSCommandKeyMask,      # For Command key
    NSAlternateKeyMask,    # For Option/Alt key
    NSControlKeyMask,
    NSShiftKeyMask,
    NSDeviceIndependentModifierFlagsMask, # Mask to isolate standard modifiers
    NSApplication,
    NSRunLoop
)
# Foundation might be needed implicitly or for other things later
# from Foundation import NSObject
import json
import os
import argparse
import signal # <--- Import signal module

# --- 配置 ---
WIFI_INTERFACE = 'en0'
CONFIG_FILE = 'config.json'
DEFAULT_HOTKEY = '<cmd>+<alt>+w' # Default if config is invalid
# macOS Virtual Key Codes (e.g., from /System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework/Versions/A/Headers/Events.h)
TARGET_KEYCODE = 13  # Key code for 'W'
# Modifier Flags Mask (Command + Option)
TARGET_MODIFIERS = NSCommandKeyMask | NSAlternateKeyMask
# --- 配置结束 ---

# --- macOS Virtual Key Code Mapping (Common Keys) ---
# Based on /System/Library/Frameworks/Carbon.framework/Versions/A/Frameworks/HIToolbox.framework/Versions/A/Headers/Events.h
# Add more as needed
KEYCODE_MAP = {
    # Letters
    'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5, 'z': 6, 'x': 7, 'c': 8,
    'v': 9, 'b': 11, 'q': 12, 'w': 13, 'e': 14, 'r': 15, 'y': 16, 't': 17,
    'u': 32, 'i': 34, 'o': 31, 'p': 35, 'l': 37, 'j': 38, 'k': 40, 'n': 45,
    'm': 46,
    # Numbers
    '1': 18, '2': 19, '3': 20, '4': 21, '5': 23, '6': 22, '7': 26, '8': 28,
    '9': 25, '0': 29,
    # Symbols (Common ones, may vary with layout)
    '-': 27, '=': 24, '[': 33, ']': 30, '\\': 42, ';': 41, '\'': 39, ',': 43,
    '.': 47, '/': 44, '`': 50,
    # Function Keys
    '<f1>': 122, '<f2>': 120, '<f3>': 99, '<f4>': 118, '<f5>': 96, '<f6>': 97,
    '<f7>': 98, '<f8>': 100, '<f9>': 101, '<f10>': 109, '<f11>': 103, '<f12>': 111,
    # Others
    '<space>': 49, '<enter>': 36, '<return>': 36, # Enter/Return often same code
    '<tab>': 48, '<esc>': 53, '<delete>': 51, '<backspace>': 51, # Delete/Backspace often same
    '<up>': 126, '<down>': 125, '<left>': 123, '<right>': 124,
    '<pageup>': 116, '<pagedown>': 121, '<home>': 115, '<end>': 119,
    # Modifiers (handled separately, but good to know their names)
    # '<cmd>', '<alt>', '<ctrl>', '<shift>'
}

# --- Modifier Mask Mapping ---
MODIFIER_MAP = {
    '<cmd>': NSCommandKeyMask,
    '<command>': NSCommandKeyMask,
    '<alt>': NSAlternateKeyMask,
    '<option>': NSAlternateKeyMask,
    '<ctrl>': NSControlKeyMask,
    '<control>': NSControlKeyMask,
    '<shift>': NSShiftKeyMask,
}

# --- Wi-Fi 控制函数 (保持不变) ---
def get_wifi_power_state(interface):
    """检查 Wi-Fi 电源状态"""
    try:
        result = subprocess.run(
            ['networksetup', '-getairportpower', interface],
            capture_output=True, text=True, check=True, timeout=5
        )
        output = result.stdout.strip()
        if ': On' in output: return True
        elif ': Off' in output: return False
        else: print(f"无法解析 Wi-Fi 状态: {output}"); return None
    except subprocess.TimeoutExpired: print("获取 Wi-Fi 状态超时。"); return None
    except subprocess.CalledProcessError as e: print(f"执行 networksetup 获取状态时出错: {e}"); return None
    except FileNotFoundError: print("错误: 'networksetup' 命令未找到。"); sys.exit(1)

def set_wifi_power_state(interface, state):
    """设置 Wi-Fi 电源状态"""
    state_str = 'on' if state else 'off'
    print(f"正在将 Wi-Fi ({interface}) 设置为 {state_str}...")
    try:
        subprocess.run(
            ['networksetup', '-setairportpower', interface, state_str],
            check=True, capture_output=True, timeout=5
        )
        print(f"Wi-Fi ({interface}) 已成功设置为 {state_str}"); return True
    except subprocess.TimeoutExpired: print(f"设置 Wi-Fi 状态为 {state_str} 超时。"); return False
    except subprocess.CalledProcessError as e: print(f"执行 networksetup 设置状态时出错: {e}"); return False
    except FileNotFoundError: print("错误: 'networksetup' 命令未找到。"); sys.exit(1)

# 使用一个简单的标记来防止快速重复触发
last_toggle_time = 0
toggle_debounce_seconds = 0.5 # 调整防抖时间

def toggle_wifi(target_keycode, target_modifiers_str): # 传入配置用于打印
    """切换 Wi-Fi 状态"""
    global last_toggle_time
    current_time = time.time()
    if current_time - last_toggle_time < toggle_debounce_seconds:
        return # Debounce

    print(f"快捷键 {target_modifiers_str} 被触发!") # 使用加载的字符串
    current_state = get_wifi_power_state(WIFI_INTERFACE)
    if current_state is None:
        print("无法获取当前 Wi-Fi 状态，操作中止。")
        return

    if set_wifi_power_state(WIFI_INTERFACE, not current_state):
        last_toggle_time = current_time
    else:
        print("切换 Wi-Fi 失败。")

# --- 解析快捷键字符串 ---
def parse_hotkey_string(hotkey_str):
    """将 '<cmd>+<alt>+w' 格式的字符串解析为 keyCode 和 modifierFlags"""
    parts = hotkey_str.lower().split('+')
    target_keycode = None
    target_modifiers = 0
    target_key_str = None

    for part in parts:
        part = part.strip()
        if part in MODIFIER_MAP:
            target_modifiers |= MODIFIER_MAP[part]
        elif part in KEYCODE_MAP:
            if target_keycode is not None:
                raise ValueError(f"快捷键字符串 '{hotkey_str}' 包含多个主要按键")
            target_keycode = KEYCODE_MAP[part]
            target_key_str = part # Store the key string itself
        else:
            # Handle single character keys like 'a', '1' etc.
            if len(part) == 1 and part in KEYCODE_MAP:
                 if target_keycode is not None:
                     raise ValueError(f"快捷键字符串 '{hotkey_str}' 包含多个主要按键")
                 target_keycode = KEYCODE_MAP[part]
                 target_key_str = part
            else:
                raise ValueError(f"快捷键字符串 '{hotkey_str}' 包含未知或不支持的部分: '{part}'")

    if target_keycode is None:
        raise ValueError(f"快捷键字符串 '{hotkey_str}' 未指定主要按键")
    if target_modifiers == 0:
         # Allow single keys like '<f1>'? Or require at least one modifier?
         # Let's allow single special keys, but maybe warn if it's just 'a'?
         # For now, we allow it. Add checks if needed.
         pass

    return target_keycode, target_modifiers, target_key_str

# --- 事件处理程序 (现在需要知道目标键码/掩码) ---
# 使用全局变量或将其包装在类中来传递目标值
g_target_keycode = None
g_target_modifiers = None
g_target_hotkey_str = None # Store the original string for display in toggle_wifi

def handler(event):
    """全局键盘事件的处理程序"""
    global g_target_keycode, g_target_modifiers, g_target_hotkey_str
    if g_target_keycode is None: return # Not configured yet

    try:
        mods = event.modifierFlags() & NSDeviceIndependentModifierFlagsMask
        key_code = event.keyCode()

        # Debug: print(f"KeyCode: {key_code}, Modifiers: {mods} | Target: KC={g_target_keycode} Mods={g_target_modifiers}")

        if key_code == g_target_keycode and mods == g_target_modifiers:
            # 将配置信息传递给 toggle_wifi 用于打印
            toggle_wifi(g_target_keycode, g_target_hotkey_str)

    except Exception as e:
        # 添加更详细的错误信息
        import traceback
        print(f"处理事件时出错: {e}\n{traceback.format_exc()}")

# --- 配置加载和更新函数 ---
def load_hotkey_string_from_config(config_path, default_str):
    """从 JSON 文件加载热键字符串配置"""
    if not os.path.exists(config_path):
        print(f"配置文件 '{config_path}' 未找到，使用默认快捷键: {default_str}")
        return default_str
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            hotkey = config_data.get('hotkey')
            if hotkey and isinstance(hotkey, str):
                # Basic validation - more done in parsing later
                 print(f"从配置文件加载快捷键字符串: {hotkey}")
                 return hotkey
            else:
                print(f"配置文件中未找到有效的 'hotkey' 字符串，使用默认: {default_str}")
                return default_str
    except Exception as e:
        print(f"读取配置文件 '{config_path}' 时发生错误: {e}，使用默认: {default_str}")
        return default_str

def update_hotkey_config(config_path, new_hotkey_str):
    """验证快捷键字符串格式并更新配置文件"""
    try:
        # 尝试解析以验证格式
        parse_hotkey_string(new_hotkey_str)
    except ValueError as e:
        print(f"错误：提供的快捷键字符串 '{new_hotkey_str}' 格式无效或包含未知按键。")
        print(f"原因: {e}")
        print("请使用 '+' 连接，例如 '<cmd>+<shift>+k>' 或 '<f1>'。")
        print(f"已知按键: {list(KEYCODE_MAP.keys())}")
        print(f"已知修饰键: {list(MODIFIER_MAP.keys())}")
        sys.exit(1)

    config_data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
        except Exception as e:
            print(f"警告：无法读取现有配置文件 '{config_path}' ({e})。")
            config_data = {}

    config_data['hotkey'] = new_hotkey_str

    try:
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        print(f"成功将快捷键字符串更新为: {new_hotkey_str}")
        print(f"配置文件 '{config_path}' 已更新。")
    except Exception as e:
        print(f"错误：无法写入配置文件 '{config_path}': {e}")
        sys.exit(1)

# --- 新增：信号处理函数 ---
def signal_handler(signum, frame):
    """处理 SIGINT (Ctrl+C) 或 SIGTERM 信号"""
    print("\n信号检测到！正在请求终止应用程序...") # <-- 更通用的消息
    # 告诉 AppKit 应用程序终止
    # 使用 performSelectorOnMainThread 确保在主线程执行 terminate_
    app = NSApplication.sharedApplication()
    # terminate_ 的签名为 v@:@ (void return, takes self, takes sender)
    app.performSelectorOnMainThread_withObject_waitUntilDone_(
        objc.selector(app.terminate_, signature=b'v@:@'), None, False # <-- Use terminate_
    )
    # 直接调用 app.terminate_(None) 在信号处理程序中可能不太安全
    # app.stop_(None) # <-- Previous attempt

# --- 主程序 ---
def main():
    global g_target_keycode, g_target_modifiers, g_target_hotkey_str # Declare globals

    parser = argparse.ArgumentParser(description='Toggle Wi-Fi power via global hotkey (uses pyobjc).')
    parser.add_argument(
        '--set-hotkey',
        metavar='\'<hotkey_str>\'',
        type=str,
        help="Set new hotkey string in config.json (e.g., '<cmd>+<alt>+w>') and exit."
    )
    args = parser.parse_args()

    if args.set_hotkey:
        update_hotkey_config(CONFIG_FILE, args.set_hotkey)
        sys.exit(0)

    if sys.platform != 'darwin':
        print("错误：此脚本需要 macOS 和 pyobjc。")
        sys.exit(1)

    # 加载并解析快捷键
    hotkey_string_to_parse = load_hotkey_string_from_config(CONFIG_FILE, DEFAULT_HOTKEY)
    try:
        g_target_keycode, g_target_modifiers, _ = parse_hotkey_string(hotkey_string_to_parse)
        g_target_hotkey_str = hotkey_string_to_parse # Store for display
        print(f"将尝试监听 KeyCode={g_target_keycode}, Modifiers={g_target_modifiers} (来自 '{hotkey_string_to_parse}')")
    except ValueError as e:
        print(f"\n错误：无法解析配置文件中的快捷键 '{hotkey_string_to_parse}'。")
        print(f"原因: {e}")
        print(f"请使用 --set-hotkey 设置一个有效的快捷键或修复 {CONFIG_FILE}。")
        sys.exit(1)

    print("\nWi-Fi 切换脚本已启动 (使用 pyobjc/AppKit)。")
    # Display a user-friendly version
    display_hotkey = hotkey_string_to_parse.upper().replace('<','').replace('>','').replace('+',' + ')
    print(f"当前快捷键 (来自 {CONFIG_FILE}): {display_hotkey}")
    print("使用 --set-hotkey '<新快捷键>' 参数来更改设置。")
    print("脚本在后台运行。按 Ctrl+C 在此终端可尝试停止。")
    print("\n!! 重要 !!")
    print("1. 请再次确认 '系统设置 > 隐私与安全性 > 辅助功能' 权限已为运行此脚本的应用启用并生效。")
    print("2. 确保快捷键 '{display_hotkey}' 未被系统或其他应用全局占用。\n")

    monitor = None
    app = None # Initialize app variable
    try:
        # --- 在启动事件循环前注册信号处理 ---
        signal.signal(signal.SIGINT, signal_handler)
        # 你也可以处理 SIGTERM (例如来自 kill 命令)
        # signal.signal(signal.SIGTERM, signal_handler)

        monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSKeyDownMask,
            handler
        )
        if monitor is None:
             print("错误：无法创建全局事件监视器（权限问题？）。")
             sys.exit(1)

        print("事件监视器已注册。启动运行循环...")
        app = NSApplication.sharedApplication() # 获取应用实例
        app.run() # 启动事件循环 - 现在可以被 signal_handler 中断

    except Exception as e:
        print(f"\n启动或运行时发生错误: {e}")
        if "access for assistive devices" in str(e): print("错误信息强烈暗示辅助功能权限问题！")
        else: import traceback; print(traceback.format_exc())
    finally:
        print("\n正在尝试移除事件监视器...")
        if monitor:
            try: NSEvent.removeMonitor_(monitor); print("事件监视器已移除。")
            except Exception as e_rem: print(f"移除监视器时出错: {e_rem}")
        print("脚本已停止。")

if __name__ == "__main__":
    main() 