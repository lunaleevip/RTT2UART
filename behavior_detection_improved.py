#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的行为检测算法 - 解决测试结果不一致问题
"""

import numpy as np
import time
from collections import deque
from dataclasses import dataclass
from typing import List, Tuple, Dict
import json
import logging

@dataclass
class SensorData:
    """传感器数据结构"""
    timestamp: float
    gyro_x: float
    gyro_y: float
    gyro_z: float
    accel_x: float
    accel_y: float
    accel_z: float
    mag_x: float = 0.0
    mag_y: float = 0.0
    mag_z: float = 0.0

@dataclass
class BehaviorResult:
    """行为检测结果"""
    behavior_type: str  # 'walking', 'wandering', 'stationary'
    confidence: float
    turn_count: int
    movement_intensity: float
    data_quality: float
    metadata: Dict

class DataPreprocessor:
    """数据预处理器 - 提高数据质量和一致性"""
    
    def __init__(self, window_size=50):
        self.window_size = window_size
        self.gyro_offset = np.array([0.0, 0.0, 0.0])
        self.accel_offset = np.array([0.0, 0.0, 0.0])
        self.noise_std = np.array([0.1, 0.1, 0.1])
        self.is_calibrated = False
        
        # 滤波器参数
        self.alpha = 0.2  # 低通滤波系数
        self.prev_gyro = np.zeros(3)
        self.prev_accel = np.zeros(3)
        
    def calibrate(self, static_data: List[SensorData]):
        """使用静止数据校准传感器零点"""
        if len(static_data) < 10:
            logging.warning("校准数据不足，使用默认值")
            return
            
        gyro_values = np.array([[d.gyro_x, d.gyro_y, d.gyro_z] for d in static_data])
        accel_values = np.array([[d.accel_x, d.accel_y, d.accel_z] for d in static_data])
        
        # 计算零点偏移
        self.gyro_offset = np.mean(gyro_values, axis=0)
        self.accel_offset = np.mean(accel_values, axis=0) - np.array([0, 0, 9.8])  # 重力补偿
        
        # 计算噪声水平
        self.noise_std = np.std(gyro_values, axis=0)
        
        self.is_calibrated = True
        logging.info(f"传感器校准完成 - 陀螺仪偏移: {self.gyro_offset}")
        
    def apply_calibration(self, data: SensorData) -> SensorData:
        """应用校准参数"""
        if not self.is_calibrated:
            return data
            
        # 应用零点偏移校正
        corrected_data = SensorData(
            timestamp=data.timestamp,
            gyro_x=data.gyro_x - self.gyro_offset[0],
            gyro_y=data.gyro_y - self.gyro_offset[1],
            gyro_z=data.gyro_z - self.gyro_offset[2],
            accel_x=data.accel_x - self.accel_offset[0],
            accel_y=data.accel_y - self.accel_offset[1],
            accel_z=data.accel_z - self.accel_offset[2],
            mag_x=data.mag_x,
            mag_y=data.mag_y,
            mag_z=data.mag_z
        )
        
        return corrected_data
    
    def apply_filter(self, data: SensorData) -> SensorData:
        """应用低通滤波器减少噪声"""
        current_gyro = np.array([data.gyro_x, data.gyro_y, data.gyro_z])
        current_accel = np.array([data.accel_x, data.accel_y, data.accel_z])
        
        # 低通滤波
        filtered_gyro = self.alpha * current_gyro + (1 - self.alpha) * self.prev_gyro
        filtered_accel = self.alpha * current_accel + (1 - self.alpha) * self.prev_accel
        
        self.prev_gyro = filtered_gyro
        self.prev_accel = filtered_accel
        
        return SensorData(
            timestamp=data.timestamp,
            gyro_x=filtered_gyro[0],
            gyro_y=filtered_gyro[1],
            gyro_z=filtered_gyro[2],
            accel_x=filtered_accel[0],
            accel_y=filtered_accel[1],
            accel_z=filtered_accel[2],
            mag_x=data.mag_x,
            mag_y=data.mag_y,
            mag_z=data.mag_z
        )

class AdaptiveTurnDetector:
    """自适应转向检测器 - 减少阈值敏感性"""
    
    def __init__(self):
        self.turn_threshold = 30.0  # 初始阈值（度/秒）
        self.min_threshold = 15.0
        self.max_threshold = 45.0
        self.adaptation_rate = 0.05
        
        self.recent_gyro_data = deque(maxlen=100)
        self.turn_history = deque(maxlen=20)
        self.hysteresis_factor = 0.8  # 滞后因子
        
    def update_threshold(self, gyro_magnitude):
        """根据最近数据自适应调整阈值"""
        self.recent_gyro_data.append(gyro_magnitude)
        
        if len(self.recent_gyro_data) >= 50:
            # 计算噪声水平
            noise_level = np.std(list(self.recent_gyro_data))
            mean_level = np.mean(list(self.recent_gyro_data))
            
            # 自适应阈值 = 基础噪声 * 倍数 + 信号强度 * 比例
            adaptive_threshold = noise_level * 3 + mean_level * 0.2
            
            # 平滑调整
            target_threshold = np.clip(adaptive_threshold, self.min_threshold, self.max_threshold)
            self.turn_threshold = (self.turn_threshold * (1 - self.adaptation_rate) + 
                                 target_threshold * self.adaptation_rate)
                                 
    def detect_turn(self, gyro_data: SensorData) -> bool:
        """检测转向事件（带滞后处理）"""
        # 计算角速度幅值
        gyro_magnitude = np.sqrt(gyro_data.gyro_x**2 + gyro_data.gyro_y**2 + gyro_data.gyro_z**2)
        
        # 更新自适应阈值
        self.update_threshold(gyro_magnitude)
        
        # 滞后检测：上升阈值和下降阈值不同
        upper_threshold = self.turn_threshold
        lower_threshold = self.turn_threshold * self.hysteresis_factor
        
        # 检查转向状态
        if len(self.turn_history) == 0:
            # 初始状态
            is_turning = gyro_magnitude > upper_threshold
        else:
            # 根据当前状态决定阈值
            was_turning = self.turn_history[-1]
            if was_turning:
                # 之前在转向，使用较低阈值（滞后）
                is_turning = gyro_magnitude > lower_threshold
            else:
                # 之前未转向，使用较高阈值
                is_turning = gyro_magnitude > upper_threshold
        
        self.turn_history.append(is_turning)
        return is_turning

class BehaviorClassifier:
    """改进的行为分类器 - 多特征融合"""
    
    def __init__(self, window_size=100):
        self.window_size = window_size
        self.data_window = deque(maxlen=window_size)
        self.turn_detector = AdaptiveTurnDetector()
        self.preprocessor = DataPreprocessor()
        
        # 分类阈值（可配置）
        self.thresholds = {
            'turn_count_walking': (5, 15),      # 行走：转向次数中等
            'turn_count_wandering': (15, 50),   # 闲逛：转向次数多
            'movement_intensity_min': 0.5,      # 最小运动强度
            'stationary_threshold': 0.2         # 静止阈值
        }
        
    def add_data(self, data: SensorData):
        """添加传感器数据"""
        # 预处理数据
        processed_data = self.preprocessor.apply_calibration(data)
        processed_data = self.preprocessor.apply_filter(processed_data)
        
        self.data_window.append(processed_data)
        
    def calculate_features(self) -> Dict:
        """计算多维特征"""
        if len(self.data_window) < self.window_size // 2:
            return {}
            
        # 转向特征
        turn_count = 0
        turn_events = []
        
        for data in self.data_window:
            if self.turn_detector.detect_turn(data):
                turn_count += 1
                turn_events.append(data.timestamp)
        
        # 运动强度特征
        accel_magnitudes = []
        gyro_magnitudes = []
        
        for data in self.data_window:
            accel_mag = np.sqrt(data.accel_x**2 + data.accel_y**2 + data.accel_z**2)
            gyro_mag = np.sqrt(data.gyro_x**2 + data.gyro_y**2 + data.gyro_z**2)
            accel_magnitudes.append(accel_mag)
            gyro_magnitudes.append(gyro_mag)
        
        movement_intensity = np.std(accel_magnitudes)
        rotation_intensity = np.mean(gyro_magnitudes)
        
        # 时间特征
        time_span = self.data_window[-1].timestamp - self.data_window[0].timestamp
        turn_frequency = turn_count / time_span if time_span > 0 else 0
        
        # 模式特征
        turn_intervals = []
        if len(turn_events) > 1:
            turn_intervals = [turn_events[i+1] - turn_events[i] for i in range(len(turn_events)-1)]
        
        turn_regularity = 1.0 / (1.0 + np.std(turn_intervals)) if turn_intervals else 0
        
        return {
            'turn_count': turn_count,
            'turn_frequency': turn_frequency,
            'movement_intensity': movement_intensity,
            'rotation_intensity': rotation_intensity,
            'turn_regularity': turn_regularity,
            'data_quality': self.assess_data_quality()
        }
    
    def assess_data_quality(self) -> float:
        """评估数据质量分数"""
        if len(self.data_window) < 10:
            return 0.0
            
        # 检查数据完整性
        timestamps = [d.timestamp for d in self.data_window]
        time_intervals = np.diff(timestamps)
        
        # 采样率稳定性
        expected_interval = np.mean(time_intervals)
        interval_variance = np.var(time_intervals) / (expected_interval**2) if expected_interval > 0 else 1
        sampling_quality = 1.0 / (1.0 + interval_variance * 10)
        
        # 信号质量（信噪比）
        gyro_values = np.array([[d.gyro_x, d.gyro_y, d.gyro_z] for d in self.data_window])
        signal_power = np.var(gyro_values)
        noise_power = np.mean(self.preprocessor.noise_std**2)
        snr = signal_power / noise_power if noise_power > 0 else 10
        signal_quality = min(1.0, snr / 10)
        
        # 综合质量分数
        overall_quality = (sampling_quality * 0.6 + signal_quality * 0.4)
        return overall_quality
    
    def classify_behavior(self) -> BehaviorResult:
        """分类行为模式"""
        features = self.calculate_features()
        
        if not features:
            return BehaviorResult(
                behavior_type='unknown',
                confidence=0.0,
                turn_count=0,
                movement_intensity=0.0,
                data_quality=0.0,
                metadata={}
            )
        
        # 多重判定逻辑
        classifications = []
        confidences = []
        
        # 方法1：基于转向次数
        turn_count = features['turn_count']
        movement_intensity = features['movement_intensity']
        
        if movement_intensity < self.thresholds['stationary_threshold']:
            classifications.append('stationary')
            confidences.append(0.9)
        elif self.thresholds['turn_count_walking'][0] <= turn_count <= self.thresholds['turn_count_walking'][1]:
            classifications.append('walking')
            confidences.append(0.8)
        elif turn_count > self.thresholds['turn_count_wandering'][0]:
            classifications.append('wandering')
            confidences.append(0.7)
        else:
            classifications.append('walking')  # 默认分类
            confidences.append(0.6)
        
        # 方法2：基于运动模式
        turn_regularity = features.get('turn_regularity', 0)
        if turn_regularity > 0.7 and movement_intensity > 0.5:
            classifications.append('walking')
            confidences.append(0.8)
        elif turn_regularity < 0.3 and turn_count > 10:
            classifications.append('wandering')
            confidences.append(0.75)
        
        # 方法3：基于频率特征
        turn_frequency = features.get('turn_frequency', 0)
        if turn_frequency > 2.0:  # 高频转向
            classifications.append('wandering')
            confidences.append(0.7)
        elif 0.5 <= turn_frequency <= 2.0:  # 中频转向
            classifications.append('walking')
            confidences.append(0.75)
        
        # 投票决定最终结果
        final_classification = max(set(classifications), key=classifications.count)
        avg_confidence = np.mean([conf for i, conf in enumerate(confidences) 
                                if classifications[i] == final_classification])
        
        # 数据质量调整置信度
        data_quality = features['data_quality']
        adjusted_confidence = avg_confidence * data_quality
        
        return BehaviorResult(
            behavior_type=final_classification,
            confidence=adjusted_confidence,
            turn_count=turn_count,
            movement_intensity=movement_intensity,
            data_quality=data_quality,
            metadata={
                'features': features,
                'all_classifications': classifications,
                'raw_confidences': confidences,
                'adaptive_threshold': self.turn_detector.turn_threshold
            }
        )

class TestConsistencyValidator:
    """测试一致性验证器"""
    
    def __init__(self):
        self.test_results = []
        self.consistency_threshold = 0.15  # 15%变异系数阈值
        
    def add_test_result(self, result: BehaviorResult):
        """添加测试结果"""
        self.test_results.append(result)
        
    def calculate_consistency(self) -> Dict:
        """计算测试一致性指标"""
        if len(self.test_results) < 2:
            return {'status': 'insufficient_data'}
        
        # 提取关键指标
        turn_counts = [r.turn_count for r in self.test_results]
        confidences = [r.confidence for r in self.test_results]
        classifications = [r.behavior_type for r in self.test_results]
        
        # 计算变异系数
        turn_count_cv = np.std(turn_counts) / np.mean(turn_counts) if np.mean(turn_counts) > 0 else 0
        confidence_cv = np.std(confidences) / np.mean(confidences) if np.mean(confidences) > 0 else 0
        
        # 分类一致性
        most_common_class = max(set(classifications), key=classifications.count)
        classification_consistency = classifications.count(most_common_class) / len(classifications)
        
        # 综合评估
        is_consistent = (turn_count_cv < self.consistency_threshold and 
                        classification_consistency > 0.8)
        
        return {
            'status': 'consistent' if is_consistent else 'inconsistent',
            'turn_count_cv': turn_count_cv,
            'confidence_cv': confidence_cv,
            'classification_consistency': classification_consistency,
            'recommendations': self._generate_recommendations(turn_count_cv, classification_consistency)
        }
    
    def _generate_recommendations(self, turn_cv, class_consistency) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if turn_cv > 0.2:
            recommendations.append("转向检测阈值需要调整或使用自适应算法")
        if turn_cv > 0.15:
            recommendations.append("增加数据预处理步骤（滤波、校准）")
        if class_consistency < 0.7:
            recommendations.append("重新评估分类阈值参数")
        if class_consistency < 0.8:
            recommendations.append("考虑使用多特征融合方法")
            
        return recommendations

# 使用示例
def main():
    """使用示例"""
    
    # 创建改进的行为分类器
    classifier = BehaviorClassifier(window_size=100)
    validator = TestConsistencyValidator()
    
    # 模拟多次测试
    for test_round in range(5):
        print(f"\n=== 测试轮次 {test_round + 1} ===")
        
        # 重置分类器
        classifier = BehaviorClassifier(window_size=100)
        
        # 模拟传感器数据（实际使用中从RTT获取）
        for i in range(150):
            # 模拟数据（实际应用中替换为真实数据）
            data = SensorData(
                timestamp=time.time() + i * 0.02,
                gyro_x=np.random.normal(0, 10) + 20 * np.sin(i * 0.1),
                gyro_y=np.random.normal(0, 5),
                gyro_z=np.random.normal(0, 5),
                accel_x=np.random.normal(0, 1),
                accel_y=np.random.normal(0, 1),
                accel_z=9.8 + np.random.normal(0, 0.5)
            )
            
            classifier.add_data(data)
        
        # 获取分类结果
        result = classifier.classify_behavior()
        validator.add_test_result(result)
        
        print(f"行为类型: {result.behavior_type}")
        print(f"置信度: {result.confidence:.3f}")
        print(f"转向次数: {result.turn_count}")
        print(f"数据质量: {result.data_quality:.3f}")
        print(f"自适应阈值: {result.metadata.get('adaptive_threshold', 0):.1f}")
    
    # 验证一致性
    consistency = validator.calculate_consistency()
    print(f"\n=== 一致性评估 ===")
    print(f"状态: {consistency['status']}")
    print(f"转向次数变异系数: {consistency.get('turn_count_cv', 0):.3f}")
    print(f"分类一致性: {consistency.get('classification_consistency', 0):.3f}")
    
    if consistency.get('recommendations'):
        print("\n改进建议:")
        for rec in consistency['recommendations']:
            print(f"- {rec}")

if __name__ == "__main__":
    main()
