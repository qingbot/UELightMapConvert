#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Python示例: 调用LightmapPacker DLL
"""

import os
import sys
import ctypes
import json
import time
import platform
from typing import List, Tuple, Dict, Optional, Any
from lightmap_structures import InputGroupData, OutputGroupData, SingleOutPutRectangle, OutLightMapTexture

# 定义回调函数类型
LOGFUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p)

def Log(message):
    # 将 bytes 转换为 str
    try:
        msg = message.decode("utf-8")
    except UnicodeDecodeError:
        # 如果UTF-8解码失败，尝试使用GBK解码
        try:
            msg = message.decode("gbk")
        except UnicodeDecodeError:
            # 如果GBK也解码失败，使用repr显示原始字节
            msg = repr(message)
    print("CPP::" + msg)

default_log_callback = LOGFUNC(Log)

class LightmapPackerPython:
    """
    Python包装类,用于调用LightmapPacker.dll
    """
    def __init__(self, dll_path=None):
        """
        初始化包装类,加载C++ DLL
        
        Args:
            dll_path: DLL路径,如果为None则自动搜索
        """
        # 自动搜索DLL
        if dll_path is None:
            # 可能的DLL路径列表
            possible_paths = [
                "LightmapPacker.dll",
                "./CPP/LightmapPacker.dll",
                os.path.join(os.path.dirname(__file__), "LightmapPacker.dll"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "CPP", "LightmapPacker.dll"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "CPP", "build", "bin", "Debug", "LightmapPacker.dll"),
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "CPP", "build", "bin", "Release", "LightmapPacker.dll")
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    dll_path = path
                    break
                    
        if dll_path is None or not os.path.exists(dll_path):
            raise FileNotFoundError("找不到LightmapPacker.dll,请指定正确的路径")
            
        print(f"加载DLL: {dll_path}")
        try:
            if platform.system() == "Windows":
                # 使用绝对路径加载DLL
                self.dll = ctypes.WinDLL(os.path.abspath(dll_path))
            else:
                self.dll = ctypes.CDLL(os.path.abspath(dll_path))
        except Exception as e:
            raise RuntimeError(f"加载DLL失败: {e}")
            
        # 设置函数参数和返回类型
        self._setup_function_signatures()
        
        # 创建Packer实例
        self.instance = self.dll.CreateLightmapPacker()
        if not self.instance:
            raise RuntimeError("创建LightmapPacker实例失败")
        
        # 内部缓存
        self._group_data = {}
        self._log_callback = None
        
    def __del__(self):
        """析构函数,释放C++资源"""
        try:
            if hasattr(self, 'dll') and hasattr(self, 'instance') and self.instance:
                self.dll.DestroyLightmapPacker(self.instance)
        except:
            print("析构失败,交给系统释放")
        
    def _setup_function_signatures(self):
        """设置DLL函数的参数类型和返回类型"""
        # 设置函数参数和返回类型
        self.dll.CreateLightmapPacker.restype = ctypes.c_void_p
        self.dll.DestroyLightmapPacker.argtypes = [ctypes.c_void_p]
        
        # 设置参数
        self.dll.SetTextureSize.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.dll.SetTextureSize.restype = ctypes.c_bool
        
        # 添加组
        self.dll.AddGroup.argtypes = [ctypes.c_void_p, ctypes.POINTER(InputGroupData)]
        self.dll.AddGroup.restype = ctypes.c_bool
        
        # 打包函数
        self.dll.PackLightmaps.argtypes = [ctypes.c_void_p]
        self.dll.PackLightmaps.restype = ctypes.c_bool

        self.dll.PackSingleLightmap.argtypes = [ctypes.c_void_p]
        self.dll.PackSingleLightmap.restype = ctypes.c_bool
        
        # 获取结果
        self.dll.GetTextureCount.argtypes = [ctypes.c_void_p]
        self.dll.GetTextureCount.restype = ctypes.c_int
        
        self.dll.GetPackingEfficiency.argtypes = [ctypes.c_void_p]
        self.dll.GetPackingEfficiency.restype = ctypes.c_float
        
        # 获取特定纹理包含的矩形数量
        self.dll.GetTextureRectangleCount.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.dll.GetTextureRectangleCount.restype = ctypes.c_int
        
        # 获取纹理结果
        self.dll.GetTextureResult.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(OutLightMapTexture)]
        self.dll.GetTextureResult.restype = ctypes.c_bool

        self.dll.TestLog.argtypes = [ctypes.c_void_p]
        self.dll.TestLog.restype = None

        self.dll.SetLogCallBack.argtypes = [ctypes.c_void_p, LOGFUNC]
        self.dll.SetLogCallBack.restype = None
    
    def set_texture_size(self, texture_size: int) -> bool:
        """设置输出纹理大小"""
        return self.dll.SetTextureSize(self.instance, texture_size)
    
    def add_group(self, input_group_data: InputGroupData) -> bool:
        """添加一个组"""
        # 调用C++ DLL添加组
        return self.dll.AddGroup(self.instance, ctypes.byref(input_group_data))
    
    def pack_lightmaps(self) -> bool:
        """
        执行灯光贴图打包
            
        Returns:
            是否成功执行打包
        """
        return self.dll.PackLightmaps(self.instance)
    
    def pack_single_lightmap(self) -> bool:
        """
        执行单个灯光贴图打包
        """
        return self.dll.PackSingleLightmap(self.instance)
    
    def get_texture_count(self) -> int:
        """获取生成的纹理数量"""
        return self.dll.GetTextureCount(self.instance)
    
    def get_packing_efficiency(self) -> float:
        """获取打包效率 (0.0-1.0)"""
        return self.dll.GetPackingEfficiency(self.instance)
    
    def get_texture_rectangle_count(self, texture_id: int) -> int:
        """
        获取特定纹理ID包含的矩形数量
        
        Args:
            texture_id: 纹理ID
            
        Returns:
            矩形数量，如果返回-1则表示没有这个纹理ID
        """
        return self.dll.GetTextureRectangleCount(self.instance, texture_id)
    
    def get_texture_result(self, texture_id: int) -> Optional[OutLightMapTexture]:
        """
        获取特定纹理ID的结果
        
        Args:
            texture_id: 纹理ID
            
        Returns:
            OutLightMapTexture对象，如果失败则返回None
        """
        # 先获取矩形数量
        rectangle_count = self.get_texture_rectangle_count(texture_id)
        if rectangle_count <= 0:
            return None
            
        # 创建OutLightMapTexture对象
        result = OutLightMapTexture()
        
        # 为矩形数组分配内存
        if rectangle_count > 0:
            # 创建矩形数组
            rectangles_array = (SingleOutPutRectangle * rectangle_count)()
            # 设置矩形数组指针
            result.rectangles = ctypes.cast(rectangles_array, ctypes.POINTER(SingleOutPutRectangle))
            # 设置矩形数量
            result.rectangle_count = rectangle_count
            
        # 调用C++ DLL获取结果
        success = self.dll.GetTextureResult(self.instance, texture_id, ctypes.byref(result))
        
        if not success:
            return None
            
        return result
        
    def get_all_texture_results(self) -> List[OutLightMapTexture]:
        """
        获取所有纹理结果
        
        Returns:
            OutLightMapTexture对象列表
        """
        results = []
        texture_count = self.get_texture_count()
        
        for i in range(texture_count):
            # 获取特定纹理ID的结果
            texture_result = self.get_texture_result(i)
            if texture_result:
                results.append(texture_result)
            else:
                # 如果获取失败，则退出循环
                break
                
        return results
    
    def test_log(self):
        """测试日志功能"""
        self.dll.TestLog(self.instance)

    def set_log_callback(self, callback_func):
        """设置日志回调函数"""
        # 保存回调函数的引用，防止被垃圾回收
        self._log_callback = callback_func
        self.dll.SetLogCallBack(self.instance, self._log_callback)

def main():
    """主函数"""
    log_callback = default_log_callback

    # 创建LightmapPacker实例
    lightmap_packer = LightmapPackerPython()
    lightmap_packer.set_log_callback(log_callback)
    lightmap_packer.test_log()

    # 添加一些测试数据
    input_group_data = InputGroupData(100, 100, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    lightmap_packer.add_group(input_group_data)

    input_group_data1 = InputGroupData(200, 200, [1, 2, 3, 9, 10])
    lightmap_packer.add_group(input_group_data1)

    # 执行打包
    success = lightmap_packer.pack_lightmaps()
    if not success:
        print("打包失败")
        return 1

    # 获取纹理数量
    texture_count = lightmap_packer.get_texture_count()
    print(f"纹理数量: {texture_count}")
    
    # 遍历每个纹理
    for texture_id in range(texture_count):
        # 获取纹理包含的矩形数量
        rectangle_count = lightmap_packer.get_texture_rectangle_count(texture_id)
        print(f"纹理 {texture_id} 包含的矩形数量: {rectangle_count}")
        
        if rectangle_count <= 0:
            continue
            
        # 获取纹理结果
        texture_result = lightmap_packer.get_texture_result(texture_id)
        if not texture_result:
            print(f"获取纹理 {texture_id} 结果失败")
            continue
            
        print(f"纹理 {texture_id}:")
        print(f"  纹理索引: {texture_result.texture_index}")
        print(f"  纹理大小: {texture_result.texture_width}x{texture_result.texture_height}")
        print(f"  矩形数量: {texture_result.rectangle_count}")
        
        # 打印矩形信息
        for i, rect in enumerate(texture_result.get_rectangles()):
            print(f"  矩形 {i}:")
            print(f"    位置: ({rect.position_x}, {rect.position_y})")
            print(f"    大小: {rect.width}x{rect.height}")
            print(f"    ID: {rect.rectangle_id}")

    return 0

if __name__ == "__main__":
    sys.exit(main()) 
