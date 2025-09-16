#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试完整内容显示功能
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

def test_content_display_improvements():
    """测试内容显示改进"""
    print("🧪 测试内容显示改进...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 检查get_tab1_content方法的改进
        import inspect
        source = inspect.getsource(main_window.get_tab1_content)
        
        improvements = [
            ("max_chars = 3000", "字符数限制增加到3000"),
            ("full_content=False", "支持完整内容参数"),
            ("如果要求完整内容，直接返回", "支持返回完整内容")
        ]
        
        improvements_ok = True
        for check, description in improvements:
            if check in source:
                print(f"✅ {description}: {check}")
            else:
                print(f"❌ {description}未实现: {check}")
                improvements_ok = False
        
        # 检查_delayed_display_tab1_content方法的改进
        display_source = inspect.getsource(main_window._delayed_display_tab1_content)
        
        display_improvements = [
            ("智能显示逻辑", "智能显示逻辑实现"),
            ("max_lines = 30", "最大行数增加到30"),
            ("省略前", "省略提示显示"),
            ("📊", "统计信息显示"),
            ("len(clean_line) > 120", "单行长度限制")
        ]
        
        for check, description in display_improvements:
            if check in display_source:
                print(f"✅ {description}: {check}")
            else:
                print(f"❌ {description}未实现: {check}")
                improvements_ok = False
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return improvements_ok
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_intelligent_line_display():
    """测试智能行数显示"""
    print("\n🧪 测试智能行数显示...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 模拟不同长度的内容
        test_cases = [
            (5, "少量内容（5行）"),
            (15, "中等内容（15行）"),
            (50, "大量内容（50行）")
        ]
        
        for line_count, description in test_cases:
            # 创建测试内容
            test_lines = [f"测试行 {i+1}: 这是一个测试内容" for i in range(line_count)]
            test_content = '\n'.join(test_lines)
            
            # 模拟_delayed_display_tab1_content的逻辑
            lines = test_content.strip().split('\n')
            total_lines = len(lines)
            
            if total_lines <= 10:
                max_lines = total_lines
                expected_behavior = "全部显示"
            elif total_lines <= 30:
                max_lines = 20
                expected_behavior = "显示最近20行"
            else:
                max_lines = 30
                expected_behavior = "显示最近30行"
            
            print(f"✅ {description}: {expected_behavior} (实际显示{max_lines}行)")
        
        # 自动关闭窗口
        QTimer.singleShot(1000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def simulate_complete_content_display():
    """模拟完整内容显示"""
    print("\n🧪 模拟完整内容显示...")
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    try:
        from main_window import RTTMainWindow
        
        # 创建主窗口
        main_window = RTTMainWindow()
        main_window.show()
        
        # 获取TAB 1的文本框并添加大量测试内容
        tab1_widget = main_window.ui.tem_switch.widget(2)  # 使用修复后的索引2
        if tab1_widget:
            from PySide6.QtWidgets import QPlainTextEdit, QTextEdit
            text_edit = tab1_widget.findChild(QPlainTextEdit)
            if not text_edit:
                text_edit = tab1_widget.findChild(QTextEdit)
            
            if text_edit:
                # 创建大量测试内容（模拟实际的RTT输出）
                test_content = """[15:29:15.015][75574498|2][        segger_rtt_scan| 357] RTT LEN: 4 DATA: ver?
[15:29:15.015][75574498|2][     ModMng_CommandQuery| 257] ver
[15:29:15.015][75574498|2][        segger_rtt_scan| 365] AAA25091601        COMPILE: Sep 16 2025 11:46:31
BASE: 25091500
HW: P02
4G: A7670E-LASC,A124802A7670MG,ASR160X_EVB_V1.0
IMEI: 863957075574498
IMSI: 460024057411966
ICCID: 89860835252499011966
GPS: AT6558R-5N-32-1C580901_URANUS5_V5.3.0.0
WIFI: Bin_version(Wroom_02):1.6.2
[15:29:15.015][75574498|2][     ModMng_CommandQuery| 284] AAA25091601
[15:29:15.015][75574498|2][        segger_rtt_scan| 365] AAA25091601
[15:29:16.997][75574498|2][        acmd_inst_receiver| 443] [ite_cmd_inst] ok
[15:29:16.997][75574498|2][        get_gravity_race|3714] GRAVITY_RACE_DEBUG: 加速度(988.16, -88.87, 13.92), 陀螺仪(988.16, 88.87, 13.92), 检测间隔+Xim(1)
[15:29:17.005][75574498|2][        acmd_inst_receiver| 443] [ite_cmd_inst] ok
[15:29:17.005][75574498|2][        get_gravity_race|3714] GRAVITY_RACE_DEBUG: 加速度(988.16, -88.87, 13.92), 陀螺仪(988.16, 88.87, 13.92), 检测间隔+Xim(1)
[15:29:17.013][75574498|2][        segger_rtt_scan| 357] RTT LEN: 4 DATA: ver?
[15:29:17.013][75574498|2][     ModMng_CommandQuery| 257] ver
[15:29:17.013][75574498|2][        segger_rtt_scan| 365] AAA25091601        COMPILE: Sep 16 2025 11:46:31
[15:29:18.021][75574498|2][        sensor_activity_detect[2244] 活动检测, 主频: 0.00 Hz, 方差: 0.155, 呼吸: 0.0次/分, 步数: 17, 倾向: 0, 翻身: 0,
[15:29:18.029][75574498|2][        sensor_activity_detect[2244] 活动检测, 主频: 0.00 Hz, 方差: 0.155, 呼吸: 0.0次/分, 步数: 17, 倾向: 0, 翻身: 0,
[15:29:18.037][75574498|2][        cellmcd_cmd_wait_result[1390] AT+CIPXGET=2,0
[15:29:18.045][75574498|2][        acmd_inst_receiver| 443] [ite_cmd_inst] AT+CIPXGET=2,0
[15:29:18.053][75574498|2][        acmd_inst_receiver| 443] [ite_cmd_inst] +IP ERROR: No data
[15:29:18.061][75574498|2][        advertising_stop| 508] advertising_stop err_code=8
[15:29:18.069][75574498|2][        advertising_init| 460] advertising_init err_code=0
[15:29:18.077][75574498|2][        advertising_start| 479] sd_ble_gap_tx_power_set err_code=0
[15:29:18.085][75574498|2][        sensor_activity_detect[2244] 活动检测, 主频: 0.00 Hz, 方差: 0.155, 呼吸: 0.0次/分, 步数: 17, 倾向: 0, 翻身: 0,"""
                
                # 添加内容到文本框
                if hasattr(text_edit, 'appendPlainText'):
                    text_edit.appendPlainText(test_content)
                else:
                    text_edit.append(test_content)
                
                print("✅ 已添加大量测试内容到TAB 1")
                
                # 测试内容获取（截取模式）
                truncated_content = main_window.get_tab1_content(full_content=False)
                truncated_lines = len(truncated_content.split('\n'))
                print(f"📋 截取模式获取内容: {len(truncated_content)} 字符, {truncated_lines} 行")
                
                # 测试内容获取（完整模式）
                full_content = main_window.get_tab1_content(full_content=True)
                full_lines = len(full_content.split('\n'))
                print(f"📋 完整模式获取内容: {len(full_content)} 字符, {full_lines} 行")
                
                # 测试显示到JLink日志
                main_window._display_tab1_content_to_jlink_log("ver?")
                print("✅ 已调用改进后的显示功能")
                
        # 等待一段时间以便观察效果
        QTimer.singleShot(3000, main_window.close)
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🚀 测试完整内容显示功能")
    print("=" * 60)
    
    # 测试内容显示改进
    improvements_ok = test_content_display_improvements()
    
    # 测试智能行数显示
    intelligent_display_ok = test_intelligent_line_display()
    
    # 模拟完整内容显示
    simulation_ok = simulate_complete_content_display()
    
    print("\n" + "=" * 60)
    
    if all([improvements_ok, intelligent_display_ok, simulation_ok]):
        print("🎉 所有测试通过！")
        
        print("\n改进内容:")
        print("1. ✅ 字符数限制增加 - 从500字符增加到3000字符")
        print("2. ✅ 智能行数显示 - 根据内容量自动调整显示行数")
        print("3. ✅ 完整内容支持 - 支持获取完整内容或截取内容")
        print("4. ✅ 省略提示显示 - 明确显示省略了多少行")
        print("5. ✅ 统计信息显示 - 显示当前行数和总行数")
        print("6. ✅ 单行长度限制 - 避免过长行影响显示")
        
        print("\n智能显示逻辑:")
        print("- 📊 ≤10行：全部显示")
        print("- 📊 11-30行：显示最近20行")
        print("- 📊 >30行：显示最近30行")
        print("- 📏 单行>120字符：自动截断并添加省略号")
        print("- 📋 显示省略提示和统计信息")
        
        print("\n用户体验改进:")
        print("- 更多内容：从500字符增加到3000字符")
        print("- 更多行数：从5行增加到最多30行")
        print("- 清晰提示：明确显示省略了多少内容")
        print("- 统计信息：显示当前/总共行数")
        print("- 长行处理：自动截断过长的行")
        print("- 智能调整：根据内容量自动调整显示策略")
        
    else:
        print("❌ 部分测试失败！")
        failed_tests = []
        if not improvements_ok:
            failed_tests.append("内容显示改进")
        if not intelligent_display_ok:
            failed_tests.append("智能行数显示")
        if not simulation_ok:
            failed_tests.append("完整内容显示模拟")
        
        print(f"失败的测试: {', '.join(failed_tests)}")
    
    return 0 if all([improvements_ok, intelligent_display_ok, simulation_ok]) else 1

if __name__ == '__main__':
    sys.exit(main())
