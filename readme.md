# lightmap的打包程序

## hybrid_lightmap_packer.py

执行方法如下：

```shell
python hybrid_lightmap_packer.py --scene carcassonne --process-terrain

--scene 后面跟的是场景的名字，场景的数据都被配置在了GlobalParameter.py里面，这个名字必须是配置文件中已定义的场景

--process-staticmesh 处理StaticMesh

--process-terrain 如果有这个参数，则会同时解析地形(terrain)数据

--use-backup 脚本处理完之后会直接覆盖旧的json文件，但会创建一个backup文件存储旧的数据，如果有此命令，则从backup里面读取json
```

hybrid_lightmap_packer.py 是核心脚本，它解析来自虚幻引擎的json数据，交给C++执行贴图打包算法，然后根据打包结果输出大图。该脚本会：

- 将物体按材质和mesh分组到不同的batch group中，同一个batch group的物体会被打包进同一个大图
- 处理StaticMesh的光照贴图，将多个贴图合并为少量大图
- 输出一个新的json文件，包含更新后的lightmap数据
- 可选择性地处理terrain地形数据

CPP文件夹内部是打包程序的源码，build.bat是编译脚本，将编译为一个dll。该dll实现了一个高效的按照group分组的矩形装箱算法，输出所有贴图的布局信息，然后python根据此布局信息合并大图。

实测的时间消耗（处理5074个物体）：总耗时10.85秒，其中C++的矩形装箱仅用0.14秒。

```shell
总共处理了 19 个Texture
总耗时: 10.85秒

时间分布:
- 加载JSON数据: 0.5%    (0.05837082862854004秒)
- 按组整理数据: 0.1%    (0.015072345733642578秒)
- 执行贴图打包: 1.3%    (0.14421796798706055秒)
- 生成新贴图: 87.6%     (9.512019157409668秒)
- 更新JSON数据: 2.0%    (0.21691393852233887秒)

处理纹理 0，包含 61 个矩形
处理纹理 1，包含 109 个矩形
处理纹理 2，包含 256 个矩形
处理纹理 3，包含 256 个矩形
处理纹理 4，包含 256 个矩形
处理纹理 5，包含 256 个矩形
处理纹理 6，包含 256 个矩形
处理纹理 7，包含 256 个矩形
处理纹理 8，包含 256 个矩形
处理纹理 9，包含 256 个矩形
处理纹理 10，包含 256 个矩形
处理纹理 11，包含 256 个矩形
处理纹理 12，包含 256 个矩形
处理纹理 13，包含 256 个矩形
处理纹理 14，包含 256 个矩形
处理纹理 15，包含 256 个矩形
处理纹理 16，包含 256 个矩形
处理纹理 17，包含 476 个矩形
处理纹理 18，包含 588 个矩形
```

主要功能列表：
- `process_staticmesh_lightmap`：处理静态网格的lightmap贴图
- `process_terrain_lightmap`：处理地形的lightmap贴图
- `group_by_parameters`：按材质和mesh特征将物体分组
- `process_and_save_packed_textures`：处理并保存打包后的贴图

## GlobalParameter.py

GlobalParameter.py包含打包程序所依赖的所有配置参数，以场景为单位组织。每个场景的配置包括：

- 源贴图路径
- JSON数据路径
- 场景XML路径
- Chaos引擎中lightmap的资源路径
- 地形尺寸偏移参数
- 输出贴图的大小设置

该文件定义了`ALL_LIGHT_MAP_DATA`字典，包含多个场景的配置，如"basic_level"和"carcassonne"。使用脚本时通过--scene参数指定要处理的场景名称。

## convert_to_xml.py

convert_to_xml.py将JSON中的lightmap信息直接更新到对应的XML文件中，使得无需通过Chaos引擎重新导入就能应用新的光照图数据。

使用方法：

```shell
python convert_to_xml.py [options]

options:
  -h, --help            显示帮助信息
  --scene, -s SCENE     指定要处理的场景名称，默认为basic_level
  --process-staticmesh  处理StaticMesh的光照图
  --process-terrain     处理地形的光照图
  --process-all         处理所有类型的光照图（包括StaticMesh和地形）
```

主要功能：
- 从JSON文件中提取lightmap信息
- 在XML文件中查找匹配的对象（通过名称或位置匹配）
- 创建或更新对象的LightMapComponentDefinition
- 自动生成备份文件保存原始XML
- 可分别处理StaticMesh和地形光照图

## Recode_Terrain_LQ.py

hybrid_lightmap_packer.py调用此脚本来处理地形数据。它的功能是：

- 根据虚幻导出的JSON数据，将地形的多张贴图合并为一张大图
- 重新计算并归一化coef_add和coef_scale系数，以支持GPU-Driven渲染的地形
- 将处理结果写回JSON数据中

## 处理虚幻资产的辅助脚本

- auto_uv.py：处理虚幻引擎中错误的二级UV资产，将StaticMesh的generate_lightmap_uv设置为false，然后再手动点击uvEditor上的generate uv1按钮

- clear_material_which_name_endwith_origin.py：清理名称以origin结尾的材质
