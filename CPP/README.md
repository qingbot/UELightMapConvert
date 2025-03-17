# LightmapPacker C++ DLL

用于灯光贴图优化、打包和处理的高性能C++库，可以作为DLL被Python程序调用。利用多线程和高性能计算技术，大幅提升光照贴图处理速度。

## 功能特点

- 使用C++实现的高性能灯光贴图处理引擎
- 支持多线程并行处理，充分利用多核CPU
- 提供模拟退火算法和传统算法两种打包策略
- 支持从Python程序中调用
- 完整的C和C++ API，方便集成到任何项目中

## 编译说明

### 前置需求

- CMake 3.14+
- 支持C++17的编译器 (MSVC, GCC, Clang)
- (可选) nlohmann/json库 - 用于JSON解析
- (可选) OpenCV - 用于图像处理
- (可选) pybind11 - 用于创建Python绑定

### 构建步骤

在Windows上使用MSVC:

```bash
# 创建构建目录
mkdir build
cd build

# 配置项目
cmake ..

# 编译项目
cmake --build . --config Release

# 安装DLL (可选)
cmake --install . --prefix C:/path/to/install
```

在Linux或macOS上:

```bash
# 创建构建目录
mkdir build && cd build

# 配置项目
cmake ..

# 编译项目
cmake --build . -j8

# 安装 (可选)
cmake --install . --prefix /path/to/install
```

## Python调用示例

### 使用ctypes调用

```python
import ctypes
import os

# 加载DLL
dll_path = os.path.join(os.path.dirname(__file__), "LightmapPacker.dll")
lightmap_packer_dll = ctypes.CDLL(dll_path)

# 设置函数参数和返回类型
lightmap_packer_dll.CreateLightmapPacker.restype = ctypes.c_void_p
lightmap_packer_dll.SetJsonPath.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
lightmap_packer_dll.SetJsonPath.restype = ctypes.c_bool
# ... 设置其他函数的参数和返回类型 ...

# 创建实例
packer = lightmap_packer_dll.CreateLightmapPacker()

# 设置参数
lightmap_packer_dll.SetJsonPath(packer, b"C:/path/to/current_scene_data_source.json")
lightmap_packer_dll.SetLightmapPath(packer, b"C:/path/to/light/light_map")
lightmap_packer_dll.SetOutputPath(packer, b"C:/path/to/light/light_map/BigLightmap")

# 执行打包
success = lightmap_packer_dll.PackLightmaps(packer, True)  # 使用模拟退火
if success:
    # 获取结果
    texture_count = lightmap_packer_dll.GetTextureCount(packer)
    efficiency = lightmap_packer_dll.GetPackingEfficiency(packer)
    print(f"打包成功！生成了 {texture_count} 个纹理，利用率: {efficiency * 100:.2f}%")
    
    # 获取所有结果
    result_count = lightmap_packer_dll.GetResultCount(packer)
    for i in range(result_count):
        # 获取每个结果的详细信息
        # ...
else:
    print("打包失败")

# 销毁实例
lightmap_packer_dll.DestroyLightmapPacker(packer)
```

### 使用提供的Python包装器(如果启用了BUILD_PYTHON_WRAPPER)

```python
import lightmap_packer_py as lp

# 创建实例
packer = lp.LightmapPacker()

# 设置参数
packer.set_json_path("C:/path/to/current_scene_data_source.json")
packer.set_lightmap_path("C:/path/to/light/light_map")
packer.set_output_path("C:/path/to/light/light_map/BigLightmap")

# 执行打包
if packer.pack_lightmaps(use_simulated_annealing=True):
    print(f"打包成功！生成了 {packer.get_texture_count()} 个纹理")
    print(f"打包效率: {packer.get_packing_efficiency() * 100:.2f}%")
else:
    print("打包失败")
```

## 开发说明

### 实现自定义功能

如果需要添加新的功能，可以:

1. 在`LightmapPacker.h`中添加新的C++方法或C API函数
2. 在`LightmapPacker.cpp`中实现这些函数
3. 在`LightmapPacker.def`中添加新的导出函数名
4. 重新编译DLL

### 性能优化建议

- 使用多线程处理大型数据集
- 利用SIMD指令进行图像处理
- 减少内存分配和复制操作
- 考虑使用GPU加速图像处理(通过OpenCV或CUDA)

## 许可证

此项目遵循MIT许可证。详情请参阅LICENSE文件。

## 作者

[您的名字]

---

最后更新: 2023年11月 