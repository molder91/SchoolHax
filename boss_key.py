import subprocess # Keep for potential future use, e.g., launching apps
import sys
import time
import objc # PyObjC core
from AppKit import ( # Import specific classes/constants from AppKit
	NSEvent,
	NSKeyDownMask,
	# NSKeyUpMask, # Likely not needed for boss key
	NSCommandKeyMask,      # For Command key
	NSAlternateKeyMask,    # For Option/Alt key
	NSControlKeyMask,
	NSShiftKeyMask,
	NSDeviceIndependentModifierFlagsMask, # Mask to isolate standard modifiers
	NSApplication,
	# NSRunLoop, # NSApplication.run() handles the loop
	NSWorkspace, # Needed for app interaction
	NSRunningApplication, # Needed for app interaction
	NSApplicationActivateIgnoringOtherApps, # 添加激活应用程序的常量
	# 添加激活策略常量
	NSApplicationActivationPolicyRegular,
	NSApplicationActivationPolicyProhibited
)
# Foundation might be needed implicitly or for other things later
# from Foundation import NSObject, NSRunLoop <- No, AppKit has run loop
import json
import os
import argparse
import signal

# --- 配置 ---
CONFIG_FILE = 'config.json'
DEFAULT_BOSS_KEY_HOTKEY = '<cmd>+<alt>+b' # Default Boss Key Hotkey
DEFAULT_RESTORE_KEY_HOTKEY = '<cmd>+<alt>+r' # Default Restore Key Hotkey
DEFAULT_TARGET_APP_NAME = 'Safari' # Default "safe" application name
DEFAULT_WIFI_CONTROL_ENABLED = True # 默认启用WiFi控制
WIFI_INTERFACE = 'en0' # 默认WiFi接口，大多数Mac上是en0
# --- 配置结束 ---

# --- macOS Virtual Key Code Mapping (Common Keys) ---
# (Keep the existing KEYCODE_MAP)
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
}

# --- Modifier Mask Mapping ---
# (Keep the existing MODIFIER_MAP)
MODIFIER_MAP = {
	'<cmd>': NSCommandKeyMask,
	'<command>': NSCommandKeyMask,
	'<alt>': NSAlternateKeyMask,
	'<option>': NSAlternateKeyMask,
	'<ctrl>': NSControlKeyMask,
	'<control>': NSControlKeyMask,
	'<shift>': NSShiftKeyMask,
}

# --- WiFi 控制函数 ---
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

def toggle_wifi(turn_on=None):
	"""切换WiFi电源状态，如果指定了turn_on参数，则直接设置为指定状态"""
	current_state = get_wifi_power_state(WIFI_INTERFACE)
	if current_state is None:
		print("无法获取当前 Wi-Fi 状态，操作中止。")
		return False
	
	if turn_on is None:
		# 如果未指定状态，则切换当前状态
		target_state = not current_state
	else:
		# 如果指定了状态，且与当前状态相同，则不做操作
		if turn_on == current_state:
			print(f"Wi-Fi 已经是 {'开启' if turn_on else '关闭'} 状态，无需操作。")
			return True
		target_state = turn_on
	
	return set_wifi_power_state(WIFI_INTERFACE, target_state)

# --- Boss Key Logic ---
hidden_app_pid = None # Store the Process ID of the hidden application
hidden_app_name = None # Store the name of the hidden application
last_key_time = 0
key_debounce_seconds = 1.0 # Debounce to prevent rapid toggling
wifi_control_enabled = DEFAULT_WIFI_CONTROL_ENABLED # 控制是否启用WiFi切换功能

def activate_target_app_applescript(app_name):
	"""使用 AppleScript 尝试激活目标应用程序"""
	print(f"尝试使用 AppleScript 激活 '{app_name}'...")
	script = f'tell application "{app_name}" to activate'
	try:
		subprocess.run(['osascript', '-e', script], check=True, capture_output=True, timeout=3)
		print(f"AppleScript 激活 '{app_name}' 命令已发送。")
		return True
	except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
		print(f"AppleScript 激活 '{app_name}' 失败: {e}")
		return False

def activate_app_by_name(app_name):
	"""查找指定名称的正在运行的应用程序对象"""
	workspace = NSWorkspace.sharedWorkspace()
	running_apps = workspace.runningApplications()
	target_app = None
	print(f"正在查找应用: {app_name}...")
	for app in running_apps:
		if app.localizedName() and app.localizedName().lower() == app_name.lower():
			target_app = app
			print(f"找到应用 '{app_name}' (PID: {target_app.processIdentifier()})")
			break

	if target_app:
		return target_app # 只返回对象
	else:
		print(f"错误：未找到名为 '{app_name}' 的正在运行的应用程序。")
		return None

def hide_current_app_and_switch(target_app_name):
	"""隐藏当前应用并切换到目标应用"""
	global hidden_app_pid, hidden_app_name, last_key_time, wifi_control_enabled
	current_time = time.time()
	if current_time - last_key_time < key_debounce_seconds:
		print("Key Debounced.")
		return

	workspace = NSWorkspace.sharedWorkspace()
	front_app = workspace.frontmostApplication()
	
	if not front_app:
		print("错误：无法获取当前最前应用。")
		return

	if front_app.localizedName() == target_app_name:
		print("目标应用已在最前。")
		return
		
	bundle_id = front_app.bundleIdentifier().lower()
	if 'terminal' in bundle_id or 'iterm' in bundle_id:
		print("不能隐藏终端应用。")
		return

	print(f"当前活动应用: {front_app.localizedName()} (PID: {front_app.processIdentifier()})")
	
	# 根据设置决定是否关闭WiFi
	if wifi_control_enabled:
		print("WiFi控制已启用，尝试关闭WiFi...")
		toggle_wifi(turn_on=False) # 尝试关闭WiFi
	else:
		print("WiFi控制已禁用，跳过WiFi操作。")
	
	print(f"尝试切换到 '{target_app_name}'...")

	# 1. 激活目标应用 (优先 AppleScript)
	if not activate_target_app_applescript(target_app_name):
		target_app_obj = activate_app_by_name(target_app_name)
		if not target_app_obj:
			print(f"错误：无法找到目标应用 '{target_app_name}'。中止操作。")
			return
		else:
			if not target_app_obj.activateWithOptions_(NSApplicationActivateIgnoringOtherApps):
				print(f"警告：原生激活目标应用 '{target_app_name}' 失败。")
	else:
		print(f"AppleScript 已发送激活 '{target_app_name}' 的命令。")

	# 给系统一点时间切换
	time.sleep(0.3)

	# 2. 隐藏之前的应用 (使用更强力的方法)
	app_to_hide_pid = front_app.processIdentifier()
	app_to_hide_name = front_app.localizedName()
	print(f"尝试隐藏 '{app_to_hide_name}' (PID: {app_to_hide_pid})...")
	
	# 尝试使用AppleScript强制隐藏应用
	script = f"""
	try
		tell application "System Events"
			if exists process "{app_to_hide_name}" then
				set visible of process "{app_to_hide_name}" to false
			end if
		end tell
		tell application "{app_to_hide_name}" to quit
	on error errMsg number errNum
		return "Error: " & errMsg & " (" & errNum & ")"
	end try
	return "OK"
	"""
	
	try:
		result = subprocess.run(['osascript', '-e', script], check=True, capture_output=True, text=True, timeout=5)
		if result.stdout.strip() == "OK":
			print(f"AppleScript成功尝试退出应用 '{app_to_hide_name}'。")
		else:
			print(f"AppleScript尝试退出应用报告错误: {result.stdout.strip()}")
			# 退出失败，尝试隐藏
			if front_app.hide():
				print(f"已通过原生hide()方法隐藏应用 '{app_to_hide_name}'。")
	except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
		print(f"AppleScript尝试退出应用失败: {e}")
		# 尝试使用原生方法隐藏
		if front_app.hide():
			print(f"已通过原生hide()方法隐藏应用 '{app_to_hide_name}'。")

	# 记录被隐藏的应用信息，无论隐藏是否成功
	hidden_app_pid = app_to_hide_pid
	hidden_app_name = app_to_hide_name
	last_key_time = current_time
	print(f"已记录隐藏应用信息: PID={hidden_app_pid}, 名称='{hidden_app_name}'")
	print("请使用恢复快捷键来恢复此应用。")


def restore_hidden_app():
	"""恢复之前隐藏的应用"""
	global hidden_app_pid, hidden_app_name, last_key_time, wifi_control_enabled
	current_time = time.time()
	if current_time - last_key_time < key_debounce_seconds:
		print("Key Debounced.")
		return
	
	if not hidden_app_pid or not hidden_app_name:
		print("没有需要恢复的应用。")
		return
	
	# 根据设置决定是否打开WiFi
	if wifi_control_enabled:
		print("WiFi控制已启用，尝试打开WiFi...")
		toggle_wifi(turn_on=True) # 尝试打开WiFi
	else:
		print("WiFi控制已禁用，跳过WiFi操作。")
	
	print(f"尝试恢复应用 '{hidden_app_name}' (PID: {hidden_app_pid})...")
	
	# 首先检查应用是否还在运行
	app_to_restore = NSRunningApplication.runningApplicationWithProcessIdentifier_(hidden_app_pid)
	
	# 使用AppleScript激活应用
	script = f'tell application "{hidden_app_name}" to activate'
	try:
		subprocess.run(['osascript', '-e', script], check=True, capture_output=True, timeout=3)
		print(f"已尝试通过AppleScript激活 '{hidden_app_name}'。")
		last_key_time = current_time
		return
	except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
		print(f"通过应用名称激活失败: {e}")
	
	# 如果找不到应用或AppleScript失败，尝试重新启动应用
	if not app_to_restore:
		print(f"找不到PID为{hidden_app_pid}的应用，尝试启动 '{hidden_app_name}'...")
		try:
			workspace = NSWorkspace.sharedWorkspace()
			success = workspace.launchApplication_(hidden_app_name)
			if success:
				print(f"已成功启动应用 '{hidden_app_name}'。")
			else:
				print(f"启动应用 '{hidden_app_name}' 失败。")
		except Exception as e:
			print(f"尝试启动应用时出错: {e}")
	else:
		# 如果应用还在运行，尝试取消隐藏并激活
		print(f"找到应用 '{hidden_app_name}'，尝试取消隐藏并激活...")
		if app_to_restore.unhide():
			print(f"已取消隐藏应用 '{hidden_app_name}'。")
		if app_to_restore.activateWithOptions_(NSApplicationActivateIgnoringOtherApps):
			print(f"已激活应用 '{hidden_app_name}'。")
		else:
			print(f"激活应用 '{hidden_app_name}' 失败。")
	
	last_key_time = current_time


def handle_boss_key(target_app_name):
	"""处理老板键按下事件：隐藏当前应用并切换到目标应用"""
	hide_current_app_and_switch(target_app_name)


def handle_restore_key():
	"""处理恢复键按下事件：恢复之前隐藏的应用"""
	restore_hidden_app()


# --- 解析快捷键字符串 ---
# (Keep the existing parse_hotkey_string function)
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
				# Allow things like '<delete>' to be parsed if map contains them
				if len(part) > 2 and part.startswith('<') and part.endswith('>') and part in KEYCODE_MAP:
					if target_keycode is not None:
						raise ValueError(f"快捷键字符串 '{hotkey_str}' 包含多个主要按键")
					target_keycode = KEYCODE_MAP[part]
					target_key_str = part
				else:
					raise ValueError(f"快捷键字符串 '{hotkey_str}' 包含未知或不支持的部分: '{part}'")

	if target_keycode is None:
		raise ValueError(f"快捷键字符串 '{hotkey_str}' 未指定主要按键")

	return target_keycode, target_modifiers, target_key_str # Return key string too

# --- 事件处理程序 ---
g_boss_key_keycode = None
g_boss_key_modifiers = None
g_restore_key_keycode = None
g_restore_key_modifiers = None
g_boss_key_target_app_name = None # Store configured target app name

def handler(event):
	"""全局键盘事件的处理程序"""
	global g_boss_key_keycode, g_boss_key_modifiers, g_restore_key_keycode, g_restore_key_modifiers, g_boss_key_target_app_name
	# Check if keys are configured
	if g_boss_key_keycode is None or g_restore_key_keycode is None or g_boss_key_target_app_name is None:
		return
	
	try:
		mods = event.modifierFlags() & NSDeviceIndependentModifierFlagsMask
		key_code = event.keyCode()

		# 检查是否匹配老板键
		if key_code == g_boss_key_keycode and mods == g_boss_key_modifiers:
			print("老板键快捷键触发!")
			handle_boss_key(g_boss_key_target_app_name)
		
		# 检查是否匹配恢复键
		elif key_code == g_restore_key_keycode and mods == g_restore_key_modifiers:
			print("恢复键快捷键触发!")
			handle_restore_key()

	except Exception as e:
		import traceback
		print(f"处理事件时出错: {e}\n{traceback.format_exc()}")

# --- 配置加载和更新函数 ---
def load_config(config_path):
	"""从 JSON 文件加载配置"""
	defaults = {
		'boss_key_hotkey': DEFAULT_BOSS_KEY_HOTKEY,
		'restore_key_hotkey': DEFAULT_RESTORE_KEY_HOTKEY,
		'boss_key_target_app_name': DEFAULT_TARGET_APP_NAME,
		'wifi_control_enabled': DEFAULT_WIFI_CONTROL_ENABLED,
		'wifi_interface': WIFI_INTERFACE
	}
	if not os.path.exists(config_path):
		print(f"配置文件 '{config_path}' 未找到，使用默认值。")
		return defaults
	try:
		with open(config_path, 'r') as f:
			config_data = json.load(f)
			# Merge defaults with loaded data (loaded data overrides defaults)
			loaded_config = defaults.copy()
			loaded_config.update(config_data)
			print(f"从 '{config_path}' 加载配置。")
			print(f"  - 老板键快捷键: {loaded_config['boss_key_hotkey']}")
			print(f"  - 恢复键快捷键: {loaded_config['restore_key_hotkey']}")
			print(f"  - 目标应用: {loaded_config['boss_key_target_app_name']}")
			print(f"  - WiFi控制: {'启用' if loaded_config['wifi_control_enabled'] else '禁用'}")
			print(f"  - WiFi接口: {loaded_config['wifi_interface']}")
			return loaded_config
	except Exception as e:
		print(f"读取配置文件 '{config_path}' 时发生错误: {e}，使用默认值。")
		return defaults

def update_boss_key_hotkey_config(config_path, new_hotkey_str):
	"""验证并更新老板键快捷键配置"""
	try:
		parse_hotkey_string(new_hotkey_str) # Validate format
		update_config(config_path, 'boss_key_hotkey', new_hotkey_str)
	except ValueError as e:
		print(f"错误：提供的老板键快捷键字符串 '{new_hotkey_str}' 格式无效或包含未知按键。")
		print(f"原因: {e}")
		print("请使用 '+' 连接，例如 '<cmd>+<shift>+b'。")
		print(f"已知按键: {list(KEYCODE_MAP.keys())}")
		print(f"已知修饰键: {list(MODIFIER_MAP.keys())}")
		sys.exit(1)

def update_restore_key_hotkey_config(config_path, new_hotkey_str):
	"""验证并更新恢复键快捷键配置"""
	try:
		parse_hotkey_string(new_hotkey_str) # Validate format
		update_config(config_path, 'restore_key_hotkey', new_hotkey_str)
	except ValueError as e:
		print(f"错误：提供的恢复键快捷键字符串 '{new_hotkey_str}' 格式无效或包含未知按键。")
		print(f"原因: {e}")
		print("请使用 '+' 连接，例如 '<cmd>+<shift>+r'。")
		print(f"已知按键: {list(KEYCODE_MAP.keys())}")
		print(f"已知修饰键: {list(MODIFIER_MAP.keys())}")
		sys.exit(1)

def update_target_app_config(config_path, new_app_name):
	"""更新目标应用程序名称配置"""
	if not new_app_name or not isinstance(new_app_name, str):
		print("错误：提供的目标应用程序名称无效。")
		sys.exit(1)
	update_config(config_path, 'boss_key_target_app_name', new_app_name)

def update_wifi_control_config(config_path, enabled):
	"""更新WiFi控制设置"""
	update_config(config_path, 'wifi_control_enabled', enabled)

def update_wifi_interface_config(config_path, interface):
	"""更新WiFi接口名称"""
	update_config(config_path, 'wifi_interface', interface)

def update_config(config_path, key, value):
	"""更新配置文件中的单个键值"""
	config_data = {}
	if os.path.exists(config_path):
		try:
			with open(config_path, 'r') as f:
				config_data = json.load(f)
		except Exception as e:
			print(f"警告：无法读取现有配置文件 '{config_path}' ({e})。将创建新的或覆盖。")
			config_data = {} # Reset if reading failed

	config_data[key] = value

	try:
		with open(config_path, 'w') as f:
			json.dump(config_data, f, indent=2)
		print(f"成功更新配置 '{key}' 为: {value}")
		print(f"配置文件 '{config_path}' 已更新。")
	except Exception as e:
		print(f"错误：无法写入配置文件 '{config_path}': {e}")
		sys.exit(1)

# --- 信号处理函数 ---
def signal_handler(signum, frame):
	"""处理 SIGINT (Ctrl+C) 或 SIGTERM 信号"""
	print("\n信号检测到！正在请求终止应用程序...")
	app = NSApplication.sharedApplication()
	# Ensure terminate is called on the main thread
	app.performSelectorOnMainThread_withObject_waitUntilDone_(
		objc.selector(app.terminate_, signature=b'v@:@'), None, False
	)

# --- 主程序 ---
def main():
	global g_boss_key_keycode, g_boss_key_modifiers, g_restore_key_keycode, g_restore_key_modifiers
	global g_boss_key_target_app_name, wifi_control_enabled, WIFI_INTERFACE

	parser = argparse.ArgumentParser(description='Boss Key utility for macOS. 隐藏当前应用，切换到指定应用，并可选择控制WiFi。')
	parser.add_argument(
		'--set-boss-hotkey',
		metavar='<hotkey_str>',
		type=str,
		help="设置老板键快捷键 (例如: '<cmd>+<alt>+b>')"
	)
	parser.add_argument(
		'--set-restore-hotkey',
		metavar='<hotkey_str>',
		type=str,
		help="设置恢复键快捷键 (例如: '<cmd>+<alt>+r>')"
	)
	parser.add_argument(
		'--set-target-app',
		metavar='AppName',
		type=str,
		help="设置目标应用名称 (例如: 'Safari', 'Google Chrome')"
	)
	parser.add_argument(
		'--enable-wifi-control',
		action='store_true',
		help="启用WiFi控制功能 (按下老板键时关闭WiFi，按下恢复键时打开WiFi)"
	)
	parser.add_argument(
		'--disable-wifi-control',
		action='store_true',
		help="禁用WiFi控制功能 (不会影响WiFi状态)"
	)
	parser.add_argument(
		'--set-wifi-interface',
		metavar='Interface',
		type=str,
		help="设置WiFi接口名称 (默认: 'en0')"
	)
	parser.add_argument(
		'--status',
		action='store_true',
		help="显示当前配置状态并退出"
	)
	args = parser.parse_args()

	# 加载配置
	config = load_config(CONFIG_FILE)

	# 处理命令行参数
	config_updated = False
	if args.set_boss_hotkey:
		update_boss_key_hotkey_config(CONFIG_FILE, args.set_boss_hotkey)
		config_updated = True
	if args.set_restore_hotkey:
		update_restore_key_hotkey_config(CONFIG_FILE, args.set_restore_hotkey)
		config_updated = True
	if args.set_target_app:
		update_target_app_config(CONFIG_FILE, args.set_target_app)
		config_updated = True
	if args.enable_wifi_control and args.disable_wifi_control:
		print("错误: 不能同时启用和禁用WiFi控制。")
		sys.exit(1)
	if args.enable_wifi_control:
		update_wifi_control_config(CONFIG_FILE, True)
		config_updated = True
	if args.disable_wifi_control:
		update_wifi_control_config(CONFIG_FILE, False)
		config_updated = True
	if args.set_wifi_interface:
		update_wifi_interface_config(CONFIG_FILE, args.set_wifi_interface)
		config_updated = True
		
	if args.status:
		# 已经在load_config中显示了配置信息
		sys.exit(0)

	if config_updated:
		print("配置已更新。重新启动应用以应用新设置。")
		sys.exit(0)

	if sys.platform != 'darwin':
		print("错误：此脚本需要 macOS 和 pyobjc。")
		sys.exit(1)

	# 应用配置
	boss_key_hotkey_str = config.get('boss_key_hotkey', DEFAULT_BOSS_KEY_HOTKEY)
	restore_key_hotkey_str = config.get('restore_key_hotkey', DEFAULT_RESTORE_KEY_HOTKEY)
	g_boss_key_target_app_name = config.get('boss_key_target_app_name', DEFAULT_TARGET_APP_NAME)
	wifi_control_enabled = config.get('wifi_control_enabled', DEFAULT_WIFI_CONTROL_ENABLED)
	WIFI_INTERFACE = config.get('wifi_interface', WIFI_INTERFACE)

	# 解析快捷键
	try:
		g_boss_key_keycode, g_boss_key_modifiers, _ = parse_hotkey_string(boss_key_hotkey_str)
		print(f"将监听老板键: KeyCode={g_boss_key_keycode}, Modifiers={g_boss_key_modifiers} (来自 '{boss_key_hotkey_str}')")
	except ValueError as e:
		print(f"\n错误：无法解析配置文件中的老板键快捷键 '{boss_key_hotkey_str}'。")
		print(f"原因: {e}")
		print(f"请使用 --set-boss-hotkey 设置一个有效的快捷键或修复 {CONFIG_FILE}。")
		sys.exit(1)

	try:
		g_restore_key_keycode, g_restore_key_modifiers, _ = parse_hotkey_string(restore_key_hotkey_str)
		print(f"将监听恢复键: KeyCode={g_restore_key_keycode}, Modifiers={g_restore_key_modifiers} (来自 '{restore_key_hotkey_str}')")
	except ValueError as e:
		print(f"\n错误：无法解析配置文件中的恢复键快捷键 '{restore_key_hotkey_str}'。")
		print(f"原因: {e}")
		print(f"请使用 --set-restore-hotkey 设置一个有效的快捷键或修复 {CONFIG_FILE}。")
		sys.exit(1)

	print("\n老板键脚本已启动 (使用 pyobjc/AppKit)。")
	boss_display_hotkey = boss_key_hotkey_str.upper().replace('<','').replace('>','').replace('+',' + ')
	restore_display_hotkey = restore_key_hotkey_str.upper().replace('<','').replace('>','').replace('+',' + ')
	print(f"当前老板键快捷键: {boss_display_hotkey}")
	print(f"当前恢复键快捷键: {restore_display_hotkey}")
	print(f"当前目标应用: {g_boss_key_target_app_name}")
	print(f"WiFi控制功能: {'启用' if wifi_control_enabled else '禁用'}")
	if wifi_control_enabled:
		print(f"WiFi接口: {WIFI_INTERFACE}")
	print("\n使用参数 --help 查看所有命令行选项")
	print("脚本在后台运行。按 Ctrl+C 在此终端可尝试停止。")
	print("\n!! 重要 !!")
	print("1. 确保 '系统设置 > 隐私与安全性 > 辅助功能' 权限已为此脚本的运行环境（如终端）启用。")
	print(f"2. 确保快捷键未被系统或其他应用全局占用。")
	print(f"3. 确保目标应用 '{g_boss_key_target_app_name}' 通常是运行状态，脚本目前不会自动启动它。")
	print("4. 按下老板键会隐藏当前应用并切换到目标应用" + ("，同时关闭WiFi" if wifi_control_enabled else "") + "。")
	print("5. 按下恢复键会恢复之前隐藏的应用" + ("，同时打开WiFi" if wifi_control_enabled else "") + "。\n")


	monitor = None
	app = None
	try:
		signal.signal(signal.SIGINT, signal_handler)
		signal.signal(signal.SIGTERM, signal_handler)

		# Use NSWorkspace notification center? No, global monitor is better for key press.
		monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
			NSKeyDownMask,
			handler
		)
		if monitor is None:
			print("错误：无法创建全局事件监视器（权限问题？）。请检查辅助功能权限。")
			sys.exit(1)

		print("事件监视器已注册。启动运行循环...")
		app = NSApplication.sharedApplication()
		app.run() # Start the event loop

	except Exception as e:
		print(f"\n启动或运行时发生错误: {e}")
		if "access for assistive devices" in str(e).lower():
			print("错误信息暗示 '辅助功能' 权限问题！请在 系统设置 > 隐私与安全性 > 辅助功能 中检查。")
		else:
			import traceback
			print(traceback.format_exc())
	finally:
		print("\n正在尝试移除事件监视器...")
		if monitor:
			try:
				NSEvent.removeMonitor_(monitor)
				print("事件监视器已移除。")
			except Exception as e_rem:
				print(f"移除监视器时出错: {e_rem}")
		# Ensure any potentially hidden app is restored on exit?
		# This is tricky because the script might be force-killed.
		# Best effort: if hidden_app_pid is set, try to unhide before exiting signal handler?
		# But signal handler might not have time or context.
		# For now, manual recovery might be needed if script crashes while app is hidden.
		print("脚本已停止。")

if __name__ == "__main__":
	main() 
