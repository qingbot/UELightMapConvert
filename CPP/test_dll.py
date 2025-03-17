import ctypes
import os
import sys

# 加载DLL
dll_path = os.path.abspath("LightmapPacker.dll")
if not os.path.exists(dll_path):
    print(f"找不到DLL: {dll_path}")
    sys.exit(1)

print(f"加载DLL: {dll_path}")
try:
    dll = ctypes.WinDLL(dll_path)
    print("DLL加载成功")
except Exception as e:
    print(f"加载DLL失败: {e}")
    sys.exit(1)

# 设置函数参数和返回类型
try:
    dll.CreateLightmapPacker.restype = ctypes.c_void_p
    dll.DestroyLightmapPacker.argtypes = [ctypes.c_void_p]
    print("函数签名设置成功")
except Exception as e:
    print(f"设置函数签名失败: {e}")
    sys.exit(1)

# 创建实例
try:
    instance = dll.CreateLightmapPacker()
    if not instance:
        print("创建实例失败")
        sys.exit(1)
    print(f"创建实例成功: {instance}")
except Exception as e:
    print(f"创建实例失败: {e}")
    sys.exit(1)

# 销毁实例
try:
    dll.DestroyLightmapPacker(instance)
    print("销毁实例成功")
except Exception as e:
    print(f"销毁实例失败: {e}")
    sys.exit(1)

print("测试完成") 