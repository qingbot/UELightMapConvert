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
from lightmap_structures import InputGroupData, OutputGroupData,SingleOutputRectangle

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
        self.dll.AddGroup.argtypes = [ctypes.c_void_p, InputGroupData]
        self.dll.AddGroup.restype = ctypes.c_bool
        
        # 打包函数
        self.dll.PackLightmaps.argtypes = [ctypes.c_void_p]
        self.dll.PackLightmaps.restype = ctypes.c_bool
        
        # 获取结果
        self.dll.GetTextureCount.argtypes = [ctypes.c_void_p]
        self.dll.GetTextureCount.restype = ctypes.c_int
        
        self.dll.GetPackingEfficiency.argtypes = [ctypes.c_void_p]
        self.dll.GetPackingEfficiency.restype = ctypes.c_float
        
        self.dll.GetResultCount.argtypes = [ctypes.c_void_p]
        self.dll.GetResultCount.restype = ctypes.c_int

        self.dll.TestLog.argtypes = [ctypes.c_void_p]
        self.dll.TestLog.restype = None

        self.dll.SetLogCallBack.argtypes = [ctypes.c_void_p, LOGFUNC]
        self.dll.SetLogCallBack.restype = None
        
        self.dll.GetResult.argtypes = [
            ctypes.c_void_p,            # instance
            ctypes.c_int,               # index
            ctypes.c_char_p,            # mesh_id
            ctypes.c_char_p,            # name
            ctypes.c_char_p,            # new_lq
            ctypes.POINTER(ctypes.c_int),  # texture_index
            ctypes.POINTER(ctypes.c_int),  # position_x
            ctypes.POINTER(ctypes.c_int),  # position_y
            ctypes.POINTER(ctypes.c_int),  # size_w
            ctypes.POINTER(ctypes.c_int),  # size_h
            ctypes.POINTER(ctypes.c_float),  # bias_scale (4个浮点数)
            ctypes.POINTER(ctypes.c_float)   # scale_factor
        ]
        self.dll.GetResult.restype = ctypes.c_bool
    
    def set_texture_size(self, texture_size: int) -> bool:
        """设置输出纹理大小"""
        return self.dll.SetTextureSize(self.instance, texture_size)
    
    def add_group(self, input_group_data: InputGroupData) -> bool:
        # 调用C++ DLL添加组
        return self.dll.AddGroup(self.instance, input_group_data)
    
    def pack_lightmaps(self, use_simulated_annealing: bool = True) -> bool:
        """
        执行灯光贴图打包
        
        Args:
            use_simulated_annealing: 是否使用模拟退火算法,默认为True
            
        Returns:
            是否成功执行打包
        """
        return self.dll.PackLightmaps(self.instance)
    
    def get_texture_count(self) -> int:
        """获取生成的纹理数量"""
        return self.dll.GetTextureCount(self.instance)
    
    def get_packing_efficiency(self) -> float:
        """获取打包效率 (0.0-1.0)"""
        return self.dll.GetPackingEfficiency(self.instance)
    
    def get_result_count(self) -> int:
        """获取结果数量"""
        return self.dll.GetResultCount(self.instance)
    
    def get_result(self, index: int) -> Optional[Dict[str, Any]]:
        """
        获取指定索引的打包结果
        
        Args:
            index: 结果索引
            
        Returns:
            打包结果字典,包含以下字段:
            - mesh_id: 物体ID
            - name: 物体名称
            - new_lq: 新的灯光贴图路径
            - texture_index: 纹理索引
            - position: (x, y) 在纹理中的位置
            - size: (width, height) 在纹理中的大小
            - new_bias_scale: 新的bias_scale (4个浮点数)
            - scale_factor: 缩放因子
        """
        # 创建缓冲区
        mesh_id_buf = ctypes.create_string_buffer(256)
        name_buf = ctypes.create_string_buffer(256)
        new_lq_buf = ctypes.create_string_buffer(512)
        
        texture_index = ctypes.c_int(0)
        position_x = ctypes.c_int(0)
        position_y = ctypes.c_int(0)
        size_w = ctypes.c_int(0)
        size_h = ctypes.c_int(0)
        
        # 创建bias_scale数组 (4个浮点数)
        bias_scale = (ctypes.c_float * 4)()
        scale_factor = ctypes.c_float(1.0)
        
        # 调用C++ DLL获取结果
        success = self.dll.GetResult(
            self.instance,
            index,
            mesh_id_buf,
            name_buf,
            new_lq_buf,
            ctypes.byref(texture_index),
            ctypes.byref(position_x),
            ctypes.byref(position_y),
            ctypes.byref(size_w),
            ctypes.byref(size_h),
            bias_scale,
            ctypes.byref(scale_factor)
        )
        
        if not success:
            return None
            
        # 解码字符串
        mesh_id = mesh_id_buf.value.decode('utf-8')
        name = name_buf.value.decode('utf-8')
        new_lq = new_lq_buf.value.decode('utf-8')
        
        # 将bias_scale转换为Python列表
        bias_scale_list = [bias_scale[i] for i in range(4)]
        
        # 返回结果字典
        return {
            "mesh_id": mesh_id,
            "name": name,
            "new_lq": new_lq,
            "texture_index": texture_index.value,
            "position": (position_x.value, position_y.value),
            "size": (size_w.value, size_h.value),
            "new_bias_scale": bias_scale_list,
            "scale_factor": scale_factor.value
        }
    
    def get_all_results(self) -> List[Dict[str, Any]]:
        """
        获取所有打包结果
        
        Returns:
            所有打包结果的列表
        """
        results = []
        count = self.get_result_count()
        
        for i in range(count):
            result = self.get_result(i)
            if result:
                results.append(result)
                
        return results
    
    def test_log(self):
        self.dll.TestLog(self.instance)

    def set_log_callback(self, callback_func):
        # 保存回调函数的引用，防止被垃圾回收
        self._log_callback = callback_func
        self.dll.SetLogCallBack(self.instance, self._log_callback)

def main():
    log_callback = default_log_callback

    lightmap_packer = LightmapPackerPython()
    lightmap_packer.set_log_callback(log_callback)
    lightmap_packer.test_log()

    input_group_data = InputGroupData(100, 100, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    lightmap_packer.add_group(input_group_data)


    input_group_data1 = InputGroupData(200, 200, [1, 2, 3, 9, 10])
    lightmap_packer.add_group(input_group_data1)

    lightmap_packer.pack_lightmaps()


if __name__ == "__main__":
    sys.exit(main()) 
