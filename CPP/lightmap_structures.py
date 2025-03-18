#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ctypes
from typing import List

# 确保内存对齐方式与C++一致 (4字节对齐)
class InputGroupData(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("rectangle_count", ctypes.c_int),
        ("rectangle_width", ctypes.c_int),
        ("rectangle_height", ctypes.c_int),
        ("rectangle_id", ctypes.POINTER(ctypes.c_int))
    ]

    def __init__(self, width: int, height: int, ids: List[int]):
        """
        初始化InputGroupData结构
        
        Args:
            width: 矩形宽度
            height: 矩形高度
            ids: 矩形ID列表
        """
        super().__init__()
        self.rectangle_width = width
        self.rectangle_height = height
        self.rectangle_count = len(ids)
        
        # 创建整数数组
        arr = (ctypes.c_int * len(ids))(*ids)
        self.rectangle_id = ctypes.cast(arr, ctypes.POINTER(ctypes.c_int))


class SingleOutputRectangle(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("position_x", ctypes.c_int),
        ("position_y", ctypes.c_int),
        ("rectangle_id", ctypes.c_int)
    ]

class OutputGroupData(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("texture_index", ctypes.c_int),
        ("scale", ctypes.c_float),
        ("single_rectangle_width", ctypes.c_int),
        ("single_rectangle_height", ctypes.c_int),
        ("group_instance_count", ctypes.c_int),
        ("rectangles", ctypes.POINTER(SingleOutputRectangle))
    ]

    def __init__(self):
        """初始化OutputGroupData结构"""
        super().__init__()
        self.rectangles = None
        self.group_instance_count = 0

    def set_rectangles(self, rectangles: List[SingleOutputRectangle]):
        """
        设置矩形数组
        
        Args:
            rectangles: SingleOutputRectangle对象列表
        """
        self.group_instance_count = len(rectangles)
        arr = (SingleOutputRectangle * len(rectangles))(*rectangles)
        self.rectangles = ctypes.cast(arr, ctypes.POINTER(SingleOutputRectangle))

    def get_rectangles(self) -> List[SingleOutputRectangle]:
        """
        获取矩形列表
        
        Returns:
            SingleOutputRectangle对象列表
        """
        if not self.rectangles or self.group_instance_count == 0:
            return []
        return [self.rectangles[i] for i in range(self.group_instance_count)]

# 使用示例
def example_usage():
    # 创建输入数据
    input_data = InputGroupData(width=100, height=100, ids=[1, 2, 3, 4])
    
    # 创建输出数据
    output_data = OutputGroupData()
    output_data.texture_index = 0
    output_data.scale = 1.0
    output_data.single_rectangle_width = 100
    output_data.single_rectangle_height = 100
    
    # 创建矩形数据
    rectangles = []
    for i in range(4):
        rect = SingleOutputRectangle()
        rect.position_x = i * 100
        rect.position_y = 0
        rect.rectangle_id = i + 1
        rectangles.append(rect)
    
    # 设置矩形数组
    output_data.set_rectangles(rectangles)
    
    # 获取并打印矩形数据
    for rect in output_data.get_rectangles():
        print(f"Rectangle {rect.rectangle_id}: pos=({rect.position_x}, {rect.position_y})")

if __name__ == "__main__":
    example_usage() 