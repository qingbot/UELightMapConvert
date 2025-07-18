# Chaos引擎贴图工具使用说明

## 概述

这些工具允许你绕过Chaos引擎的标准导入流程，直接生成带有正确元数据头的贴图文件。主要包含两个工具：

1. `TextureHeaderWriter` - 通用贴图头写入工具
2. `LightmapTextureGenerator` - 专门用于光照图贴图的生成器

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖：
- `pymongo` - 用于BSON序列化
- `pathlib2` - 路径处理

## 文件结构

```
texture_header_writer.py      # 通用贴图头写入工具
lightmap_texture_generator.py # 光照图贴图生成器
requirements.txt              # 依赖包列表
texture_tools_readme.md       # 本说明文档
```

## 使用方法

### 1. 通用贴图转换

#### 转换单个贴图
```python
from texture_header_writer import TextureHeaderWriter

writer = TextureHeaderWriter()

# 转换单个贴图
writer.create_texture_file(
    "input_texture.png",
    "output/texture.texture.ast"
)

# 使用自定义设置
custom_settings = {
    "MaxSize": 4096,
    "SRgb": False,
    "CompressType": 1
}
writer.create_texture_file(
    "input_texture.png",
    "output/texture.texture.ast",
    custom_settings
)
```

#### 批量转换贴图
```python
# 批量转换整个目录
writer.batch_convert_textures(
    "input_textures/",
    "output/textures/"
)
```

#### 命令行使用
```bash
# 转换单个贴图
python texture_header_writer.py

# 处理测试数据
python texture_header_writer.py --test-mode
```

### 2. 光照图贴图生成

#### 处理特定场景
```python
from lightmap_texture_generator import LightmapTextureGenerator

generator = LightmapTextureGenerator()

# 处理指定场景的所有光照图
generator.process_scene_lightmaps("your_scene_name")
```

#### 处理自定义目录
```python
# 处理LQ纹理
generator.process_custom_lightmaps(
    "source_lightmaps/",
    "output/lightmaps/",
    texture_type="LQ"
)

# 处理Dir纹理
generator.process_custom_lightmaps(
    "source_dirmaps/",
    "output/dirmaps/",
    texture_type="Dir"
)
```

#### 命令行使用
```bash
# 处理默认场景
python lightmap_texture_generator.py

# 处理指定场景
python lightmap_texture_generator.py --scene your_scene_name

# 自定义模式
python lightmap_texture_generator.py --custom-mode \
    --source-dir "source_lightmaps/" \
    --output-dir "output/lightmaps/" \
    --texture-type LQ
```

### 3. 复制光照图贴图到Chaos引擎

#### 功能说明
这个功能将 `hybrid_lightmap_packer_nsh.py` 的输出文件复制到Chaos引擎的资源目录中，并自动生成对应的 `.texture.ast` 文件。

#### 复制的文件
- `BigMap/lightmap/` 文件夹中的所有PNG文件
- `BigMap/dir/` 文件夹中的所有PNG文件
- `BigMap/Landscape_combine_lightmap.png` 地形文件
- `BigMap/Landscape_combine_lightmap_dir.png` 地形方向文件（如果存在）

#### 使用方法
```python
from run_texture_tools import copy_lightmap_textures_to_chaos

# 复制指定场景的光照图贴图
success = copy_lightmap_textures_to_chaos("your_scene_name")
```

#### 命令行使用
```bash
# 复制光照图贴图到Chaos引擎
python run_texture_tools.py copy --scene your_scene_name
```

### 4. 统一命令行工具

#### 可用子命令
```bash
# 查看所有可用命令
python run_texture_tools.py --help

# 通用贴图转换
python run_texture_tools.py texture --help

# 光照图贴图生成
python run_texture_tools.py lightmap --help

# 复制光照图贴图到Chaos引擎
python run_texture_tools.py copy --help

# 读取贴图文件头
python run_texture_tools.py header --help

# 运行测试
python run_texture_tools.py test
```

#### 使用示例
```bash
# 转换单个贴图
python run_texture_tools.py texture -i input.png -o output.texture.ast

# 批量转换贴图
python run_texture_tools.py texture --batch-mode --input-dir textures/ --output-dir output/

# 处理场景光照图
python run_texture_tools.py lightmap --scene your_scene

# 复制光照图到引擎
python run_texture_tools.py copy --scene your_scene

# 读取贴图文件头
python run_texture_tools.py header --input-file texture.texture.ast

# 运行测试
python run_texture_tools.py test
```

### 3. 贴图文件头读取

#### 读取单个贴图文件头
```python
from texture_header_writer import TextureHeaderWriter

writer = TextureHeaderWriter()

# 读取文件头数据
header_data = writer.read_texture_header("path/to/texture.texture.ast")

# 打印详细信息
writer.print_texture_header_info("path/to/texture.texture.ast")
```

#### 命令行使用
```bash
# 读取单个贴图文件头（详细信息）
python run_texture_tools.py header --input-file path/to/texture.texture.ast

# 读取单个贴图文件头（JSON格式）
python run_texture_tools.py header --input-file path/to/texture.texture.ast --json-output

# 读取文件头并保存到JSON文件
python run_texture_tools.py header --input-file path/to/texture.texture.ast --json-output --output-file header_data.json

# 批量读取目录中的所有贴图文件头
python run_texture_tools.py header --input-dir path/to/textures/ 

# 批量读取并输出JSON格式
python run_texture_tools.py header --input-dir path/to/textures/ --json-output

# 批量读取并保存到JSON文件
python run_texture_tools.py header --input-dir path/to/textures/ --json-output --output-file all_headers.json
```

#### 文件头数据结构
```json
{
  "texture_id": "Texture_V2",
  "bson_data_length": 1234,
  "image_data_length": 5678,
  "total_file_size": 6912,
  "header_size": 1234,
  "settings": {
    "Brightness": 1.0,
    "CompressType": 0,
    "Hue": 0.0,
    "InvertG": false,
    "IsVolumeTexture": false,
    "MaxAlpha": 1.0,
    "MaxSize": 2048,
    "MinAlpha": 0.0,
    "MipBias": 0,
    "MipGenType": 0,
    "SRgb": true,
    "SamplingFilterType": 0,
    "Saturation": 1.0,
    "SourceFilePath": "/path/to/source/image.png",
    "TileSizeX": 0,
    "TileSizeY": 0,
    "XTillingMethod": 0,
    "YTillingMethod": 0
  }
}
```

## 贴图设置说明

### 通用贴图设置
- `MipBias`: Mip偏移值 (默认: 0)
- `CompressType`: 压缩类型 (默认: 0)
- `MipGenType`: Mip生成类型 (默认: 0)
- `MaxSize`: 最大尺寸 (默认: 2048)
- `SRgb`: 是否使用sRGB (默认: True)
- `InvertG`: 是否反转G通道 (默认: False)
- `XTillingMethod`: X轴平铺方法 (默认: 0)
- `YTillingMethod`: Y轴平铺方法 (默认: 0)
- `Brightness`: 亮度 (默认: 1.0)
- `Saturation`: 饱和度 (默认: 1.0)
- `Hue`: 色调 (默认: 0.0)
- `MinAlpha`: 最小透明度 (默认: 0.0)
- `MaxAlpha`: 最大透明度 (默认: 1.0)
- `IsVolumeTexture`: 是否为体积纹理 (默认: False)
- `TileSizeX`: X轴平铺尺寸 (默认: 0)
- `TileSizeY`: Y轴平铺尺寸 (默认: 0)
- `SamplingFilterType`: 采样过滤类型 (默认: 0)

### 光照图专用设置
- `SRgb`: False (光照图不使用sRGB)
- `CompressType`: 1 (光照图压缩类型)
- `MipGenType`: 1 (光照图mip生成)
- `MaxSize`: 4096 (光照图通常需要更大尺寸)
- `SamplingFilterType`: 1 (线性过滤)

### 方向图专用设置
- `SRgb`: False (方向图不使用sRGB)
- `CompressType`: 2 (方向图压缩类型)
- `MipGenType`: 1 (方向图mip生成)
- `MaxSize`: 4096 (方向图通常需要更大尺寸)
- `SamplingFilterType`: 1 (线性过滤)

## 二进制文件格式

生成的`.texture.ast`文件格式：

```
[HEADER_BYTE]          # 字节 0x0a
[TEXTURE_ID]           # 字符串 "Texture_V2"
[BSON_DATA_LENGTH]     # int32 - BSON数据长度
[BSON_DATA]            # BSON序列化的TextureSerializeModel
[IMAGE_DATA_LENGTH]    # int32 - 图像数据长度
[IMAGE_DATA]           # 原始图像数据
```

## 与现有工具的集成

这些工具可以与现有的光照图处理流程配合使用，形成完整的光照图处理管道：

### 完整工作流程

#### 方案1：一键处理（推荐）
```bash
# 1. 打包光照图（静态物体+地形）
python hybrid_lightmap_packer_nsh.py --scene your_scene --process-staticmesh --process-terrain

# 2. 生成XML元数据并自动复制贴图到Chaos引擎
python lightmap_converter.py --scene your_scene --copy-textures
```

#### 方案2：分步处理
```bash
# 1. 打包光照图
python hybrid_lightmap_packer_nsh.py --scene your_scene --process-staticmesh --process-terrain

# 2. 生成XML元数据
python lightmap_converter.py --scene your_scene

# 3. 复制贴图到Chaos引擎
python run_texture_tools.py copy --scene your_scene
```

#### 方案3：单独处理组件
```bash
# 只处理地形
python hybrid_lightmap_packer_nsh.py --scene your_scene --process-terrain

# 只处理静态物体
python hybrid_lightmap_packer_nsh.py --scene your_scene --process-staticmesh

# 生成XML元数据
python lightmap_converter.py --scene your_scene

# 复制贴图
python run_texture_tools.py copy --scene your_scene
```

### 工作流程说明

1. **打包阶段** - `hybrid_lightmap_packer_nsh.py`
   - 读取虚幻引擎导出的光照图数据
   - 将静态物体的光照图打包到统一的纹理图集中
   - 处理地形光照图的合并
   - 输出到 `BigMap` 文件夹

2. **元数据生成阶段** - `lightmap_converter.py`
   - 匹配XML场景文件和JSON光照图数据
   - 生成Chaos引擎所需的XML元数据文件
   - 可选择自动复制贴图到引擎目录

3. **贴图复制阶段** - `run_texture_tools.py copy`
   - 将打包好的光照图复制到Chaos引擎资源目录
   - 自动生成对应的 `.texture.ast` 文件
   - 使用适合光照图的纹理参数

## 注意事项

1. **文件权限**: 确保有写入目标目录的权限
2. **路径格式**: 支持相对路径和绝对路径
3. **文件覆盖**: 如果目标文件已存在，会被覆盖
4. **内存使用**: 大型贴图文件会占用相应的内存
5. **BSON兼容性**: 确保使用的pymongo版本支持BSON序列化

## 错误处理

常见错误及解决方法：

1. **ImportError: No module named 'bson'**
   - 解决：`pip install pymongo`

2. **FileNotFoundError**
   - 检查源文件路径是否正确
   - 确保目标目录存在

3. **PermissionError**
   - 检查文件权限
   - 确保目标目录可写

4. **MemoryError**
   - 处理大型贴图时可能出现
   - 考虑分批处理或增加系统内存

## 自定义扩展

如果需要添加新的纹理类型或修改设置：

```python
# 创建自定义设置
custom_settings = {
    "CompressType": 3,  # 新的压缩类型
    "CustomParameter": "custom_value"  # 自定义参数
}

# 更新生成器设置
generator.update_texture_settings("LQ", custom_settings)
```

## 测试验证

可以通过以下方式验证生成的文件：

1. 检查文件大小是否合理
2. 使用十六进制编辑器查看文件头
3. 在Chaos引擎中加载验证

生成的文件应该与引擎原生导入的文件格式完全一致。 