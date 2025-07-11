# 混合架构灯光贴图打包工具 (hybrid_lightmap_packer_nsh) 设计文档

## 1. 系统概述

### 1.1 项目背景
本工具是一个混合架构的灯光贴图打包系统，专门用于处理大型3D场景中的灯光贴图优化。系统采用Python+C++的混合架构，充分发挥了Python在数据处理和C++在计算性能方面的优势。

### 1.2 核心功能
- **静态网格物体灯光贴图打包**：将场景中的静态物体按空间位置分组，优化灯光贴图存储
- **地形灯光贴图处理**：专门处理地形的灯光贴图合并和优化
- **高性能矩形装箱算法**：使用C++ DLL实现多线程并行计算
- **JSON数据管理**：自动更新场景配置文件中的灯光贴图引用信息

### 1.3 技术架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Python层      │    │   C++ DLL层     │    │   数据层        │
│                 │    │                 │    │                 │
│ • 数据解析      │◄──►│ • 矩形装箱      │◄──►│ • JSON配置      │
│ • 图像处理      │    │ • 多线程计算    │    │ • 灯光贴图      │
│ • 流程控制      │    │ • 内存优化      │    │ • 结果输出      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 2. 功能模块详解

### 2.1 数据管理模块

#### 2.1.1 JSON数据加载与解析
- **功能**：加载场景配置文件，解析物体的灯光贴图信息
- **支持格式**：
  - `Static Mesh`格式：`{"Static Mesh": {"mesh_id": {...}}}`
  - 直接物体格式：`{"actor_name": {"Parameters": {...}}}`
- **关键信息提取**：
  - 物体位置（Location）
  - 灯光贴图路径（LightMap.LQ/HQ）
  - UV偏移缩放（BiasScale）

#### 2.1.2 备份管理系统
- **创建备份**：`--create-backup`参数，在backup文件夹中创建原始JSON副本
- **使用备份**：`--use-backup`参数，从备份文件读取数据进行处理
- **安全保障**：防止原始数据在处理过程中意外损坏

### 2.2 空间分组模块

#### 2.2.1 世界空间网格划分
```python
def generate_world_single_area_size(lod_distance):
    """根据lod_distance生成世界单个区域的尺寸"""
    weighted_values = []
    for i, distance in enumerate(lod_distance):
        weight = 1.0 / (2 ** i)  # LOD权重计算
        weighted_values.append(distance * weight)
    return max(weighted_values)
```

#### 2.2.2 物体分组策略
- **网格计算**：根据世界边界和LOD距离确定网格大小
- **空间索引**：`grid_x_y`格式的键值对应世界坐标区域
- **分组优化**：相邻物体优先打包到同一纹理中

### 2.3 灯光贴图处理模块

#### 2.3.1 贴图提取算法
原始lightmap的上半部分是我们需要的lightmap信息，下半部分是对当前位置贡献最大的方向信息我们不需要，所以y * 0.5偏移只采用上半部分
```python
def get_lightmap_size_from_bias_scale(bias_scale, texture_size):
    """根据bias_scale计算灯光贴图的尺寸"""
    # 考虑UE4的BiasScale计算逻辑
    padded_size_x = texture_size[0] * bias_scale[2] + 2
    padded_size_y = texture_size[1] * bias_scale[3] * 0.5 + 2
    base_x = texture_size[0] * bias_scale[0] - 1
    base_y = texture_size[1] * bias_scale[1] * 0.5 - 1
    return padded_size_x, padded_size_y, base_x, base_y
```

#### 2.3.2 双层纹理处理
- **LQ纹理**：Light Quality，灯光质量纹理（图像上半部分）
- **Dir纹理**：Direction，方向纹理（图像下半部分）
- **分离保存**：生成独立的LQ和Dir纹理文件

### 2.4 C++集成模块

#### 2.4.1 矩形装箱接口
```python
# 创建LightmapPacker实例
packer = LightmapPackerPython(None)
packer.set_texture_size(texture_size)

# 添加矩形组
cpp_input_group_data = InputGroupData(width, height, [rectangle_id])
packer.add_group(cpp_input_group_data)

# 执行打包
packer.pack_single_lightmap()
results = packer.get_all_texture_results()
```

#### 2.4.2 性能优化特性
- **多线程处理**：C++层实现并行计算
- **内存优化**：高效的矩形装箱算法
- **结果缓存**：避免重复计算

### 2.5 地形处理模块

#### 2.5.1 地形lightmap合并
- **调用ReCode_Terrain_LQ模块**：专门处理地形贴图
- **Landscape数据更新**：更新JSON中的地形lightmapGroup
- **方向图支持**：同时处理光照和方向信息

#### 2.5.2 系数计算
- **CoefScale**：缩放系数，包含光照和方向信息
- **CoefAdd**：偏移系数，用于颜色校正
- **BiasScale**：UV坐标映射，统一使用[0,0,1,1]

## 3. 处理流程

### 3.1 主要处理流程
```
开始
  ↓
参数解析 → 备份管理
  ↓
数据加载 → JSON解析
  ↓
┌─────────────────┐  ┌─────────────────┐
│   地形处理      │  │   静态网格处理  │
│ • 调用地形模块  │  │ • 空间分组      │
│ • 合并lightmap  │  │ • 尺寸计算      │
│ • 更新JSON      │  │ • C++打包       │
└─────────────────┘  │ • 纹理生成      │
  ↓                  │ • BiasScale更新 │
合并结果             └─────────────────┘
  ↓
保存JSON → 输出结果
  ↓
结束
```

### 3.2 静态网格处理详细流程

#### 步骤1：数据准备
- 从GlobalParameter获取场景配置
- 确定输入/输出路径
- 设置纹理参数

#### 步骤2：空间分组
- 计算世界边界和网格大小
- 遍历物体，按位置分配到网格
- 验证lightmap信息完整性

#### 步骤3：尺寸计算
- 加载原始贴图，获取真实尺寸
- 根据BiasScale计算实际区域大小
- 应用最小尺寸限制

#### 步骤4：矩形装箱
- 为每个网格创建独立的Packer实例
- 调用C++算法进行优化布局
- 获取最终的矩形位置信息

#### 步骤5：纹理生成
- 创建空白目标纹理
- 按计算位置复制源纹理区域
- 分别处理LQ和Dir纹理
- 保存到BigMap目录

#### 步骤6：数据更新
- 计算新的BiasScale参数
- 更新JSON中的lightmap路径
- 添加Dir纹理引用

## 4. 关键算法

### 4.1 BiasScale计算
```python
def caculate_bias_scale(width, height, position_x, position_y, texture_size):
    """计算新的UV坐标映射参数"""
    bias_scale = [0, 0, 0, 0]
    bias_scale[0] = (position_x + 1) / texture_size  # U偏移
    bias_scale[1] = (position_y + 1) / texture_size  # V偏移
    bias_scale[2] = (width - 2) / texture_size       # U缩放
    bias_scale[3] = (height - 2) / texture_size      # V缩放
    return bias_scale
```

### 4.2 矩形ID管理
```python
# 全局ID映射，维护矩形与原始数据的关联
rectangle_id_map = {}
rectangle_id_counter = 1

def generate_sequential_id(mesh_id, info=None):
    """生成唯一的矩形ID并建立映射"""
    global rectangle_id_counter
    new_id = rectangle_id_counter
    rectangle_id_counter += 1
    rectangle_id_map[new_id] = info
    return new_id
```

## 5. 配置参数

### 5.1 场景配置（GlobalParameter.py）
```python
ALL_LIGHT_MAP_DATA = {
    "scene_name": {
        "source_lightmap_json_path": "path/to/scene.json",
        "source_lightmap_texture_path": "path/to/lightmaps/",
        "lightmap_texture_size": 2048,
        "lightmap_texture_min_size": 16,
        "level_left_pos": [-1024, -1024],
        "level_right_pos": [1024, 1024],
        "lod_distance": [100, 200, 400, 800]
    }
}
```

### 5.2 命令行参数
- `--scene`：场景名称
- `--process-terrain`：处理地形
- `--process-staticmesh`：处理静态网格
- `--use-backup`：使用备份文件
- `--create-backup`：创建备份

## 6. 输出结果

### 6.1 文件结构
```
output/
├── lightmaps/
│   └── scene_name/
│       └── packing_debug.json
└── BigMap/
    ├── packed_lightmap_0.png
    ├── packed_lightmap_0_dir.png
    ├── packed_lightmap_1.png
    └── packed_lightmap_1_dir.png
```

### 6.2 JSON更新
- **LightMap.LQ**：更新为打包后的纹理路径
- **LightMap.Dir**：新增方向纹理引用
- **LightMap.BiasScale**：重新计算的UV映射参数

## 7. 错误处理

### 7.1 文件处理错误
- 贴图文件不存在：生成64x64占位图像
- 路径跨驱动器：使用相对路径或文件名
- 权限问题：提供详细错误信息

### 7.2 数据完整性检查
- JSON格式验证
- 必要字段检查
- 数值范围验证

### 7.3 性能监控
- 各步骤耗时统计
- 内存使用监控
- 处理进度显示

## 8. 扩展性设计

### 8.1 模块化架构
- 地形处理独立模块
- C++算法可替换
- 配置驱动的参数系统

### 8.2 格式支持
- 多种JSON格式自动识别
- 可扩展的贴图格式支持
- 灵活的输出路径配置

### 8.3 性能优化
- 并行处理能力
- 内存池管理
- 缓存机制

## 9. 使用示例

### 9.1 基本用法
```bash
# 处理静态网格物体
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-staticmesh

# 处理地形
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-terrain

# 同时处理地形和静态网格
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-terrain --process-staticmesh
```

### 9.2 备份管理
```bash
# 创建备份
python hybrid_lightmap_packer_nsh.py --scene basic_level --create-backup

# 从备份处理
python hybrid_lightmap_packer_nsh.py --scene basic_level --use-backup --process-staticmesh
```

## 10. 总结

本工具实现了一个完整的灯光贴图优化解决方案，通过混合架构设计，在保证处理效率的同时提供了灵活的配置和扩展能力。主要特点包括：

1. **高性能**：C++实现的矩形装箱算法，多线程并行处理
2. **智能分组**：基于空间位置的自动分组策略
3. **数据安全**：完整的备份和恢复机制
4. **格式兼容**：支持多种JSON格式和贴图类型
5. **易于扩展**：模块化设计，便于功能扩展和维护

该工具特别适用于大型3D场景的灯光贴图优化，能够显著减少纹理数量，提高渲染性能。
