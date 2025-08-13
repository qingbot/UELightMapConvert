# sceneConfig 文件夹说明

## 功能说明

这个文件夹用于存放外部场景配置文件，允许用户通过修改JSON文件来添加新的场景配置，而无需修改`GlobalParameter.py`源代码。

## 使用方法

### 1. 配置文件位置
- 配置文件路径：`sceneConfig/sceneConfig.json`
- 此文件会在程序启动时自动加载

### 2. 配置文件格式

```json
{
    "场景名称": {
        "source_lightmap_texture_path": "光照图纹理源路径",
        "source_lightmap_json_path": "场景数据JSON文件路径",
        "source_scene_xml_folder_path": "场景XML文件夹路径", 
        "lightmap_path_in_chaos_assets": "Chaos引擎中的光照图资源路径",
        "source_terrain_xml_path": "地形XML文件路径",
        "lightmap_data_ast_path_in_chaos": "输出的lightmap AST文件路径",
        "terrain_size_offset": [512, 512, 512, 512],
        "lightmap_texture_size": 2048,
        "lightmap_texture_min_size": 16,
        "level_left_pos": [-1024, -1024],
        "level_right_pos": [1024, 1024],
        "lod_distance": [100, 200, 400, 800],
        "lightmap_mip0_grid_count": 8,
        "lightmap_absolute_path": "Chaos引擎光照图绝对路径",
        "original_lightmap_absolute_path": "原始光照图绝对路径"
    }
}
```

### 3. 添加新场景配置

1. 编辑`sceneConfig/sceneConfig.json`文件
2. 按照上述格式添加新的场景配置
3. 保存文件
4. 重新运行程序，新配置会自动加载

### 4. 查看和管理场景配置

```bash
# 查看所有可用的场景列表
python GlobalParameter.py --list

# 查看特定场景的详细配置
python GlobalParameter.py --show carcassonne

# 查看所有场景的详细配置
python GlobalParameter.py --show-all
```

### 5. 运行程序

```bash
# 使用配置的场景运行
python lightmap_converter.py --scene 你的场景名称

# 查看可用场景列表
python lightmap_converter.py --scene non_existing_scene
```

## 配置字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `source_lightmap_texture_path` | 字符串 | 从虚幻引擎导出的光照图纹理文件所在目录 |
| `source_lightmap_json_path` | 字符串 | 从虚幻引擎导出的场景JSON文件路径 |
| `source_scene_xml_folder_path` | 字符串 | 场景的Chaos XML文件夹路径 |
| `lightmap_path_in_chaos_assets` | 字符串 | Chaos运行时光照图的相对路径 |
| `source_terrain_xml_path` | 字符串 | 地形的Chaos XML文件路径 |
| `lightmap_data_ast_path_in_chaos` | 字符串 | 最终lightmap AST文件的输出路径 |
| `terrain_size_offset` | 数组 | 地形大小偏移参数 [size_x, size_y, offset_x, offset_y] |
| `lightmap_texture_size` | 数字 | 合并后光照图纹理大小 |
| `lightmap_texture_min_size` | 数字 | 光照图纹理最小大小 |
| `level_left_pos` | 数组 | 场景左下角世界坐标 [x, y] |
| `level_right_pos` | 数组 | 场景右上角世界坐标 [x, y] |
| `lod_distance` | 数组 | 各级LOD距离数组 |
| `lightmap_mip0_grid_count` | 数字 | mip0级别的格子数量（必须是2的整数次幂） |
| `lightmap_absolute_path` | 字符串 | Chaos引擎中光照图的绝对路径 |
| `original_lightmap_absolute_path` | 字符串 | 原始光照图的绝对路径 |

## 示例

参见`sceneConfig.json`中的示例配置。

## GlobalParameter 命令行工具

`GlobalParameter.py`现在支持作为独立的命令行工具使用，提供以下功能：

### 可用命令

| 命令 | 简写 | 说明 |
|------|------|------|
| `--list` | `-l` | 列出所有可用的场景配置 |
| `--show SCENE_NAME` | `-s SCENE_NAME` | 显示指定场景的详细配置 |
| `--show-all` | | 显示所有场景的详细配置 |
| `--help` | `-h` | 显示帮助信息 |

### 使用示例

```bash
# 显示帮助信息
python GlobalParameter.py --help

# 列出所有场景（简洁版）
python GlobalParameter.py --list

# 查看carcassonne场景的详细配置
python GlobalParameter.py --show carcassonne

# 查看example_scene场景的详细配置
python GlobalParameter.py -s example_scene

# 显示所有场景的详细配置
python GlobalParameter.py --show-all
```

### 配置信息显示

详细配置显示包含以下分类信息：

- **📁 路径配置**：各种文件和目录路径
- **🗺️ 场景范围配置**：场景边界坐标和尺寸
- **🖼️ 纹理配置**：光照图纹理相关设置
- **📏 LOD配置**：细节层次距离设置
- **🏔️ 地形配置**：地形大小和偏移参数

## 注意事项

1. 配置文件必须是有效的JSON格式
2. 路径可以使用正斜杠或反斜杠，但建议使用正斜杠
3. 新添加的配置会与`GlobalParameter.py`中的内置配置合并
4. 如果场景名称重复，外部配置会覆盖内置配置
5. 使用`GlobalParameter.py`命令行工具可以快速查看和验证配置
