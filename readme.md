# lightmap的打包程序

## Hybird_lightmap_packer.py

执行方法如下：

```shell
python hybrid_lightmap_packer.py --scene carcassonne --process-terrain

--scene 后面跟的是场景的名字，场景的数据都被配置在了GlobalParameter.py里面了，这个名字也必须是里面的场景

--process-terrain 如果有这条，则会同时解析terrain数据

--use-bakcup 脚本处理完之后会直接覆盖旧的json文件，但是创建一个backup文件存储旧的，如果有此命令，则从backup里面读取json
```

hybird_lightmap_packer.py 是核心脚本，它解析来自虚幻的json，并交给C++执行打包，然后根据打包结果输出大图。

同时它会输出一个新的json文件，里面是新的数据。

它会根据材质和mesh将物体分为不同的batch group同一个batch group的物体会被打包进同一个大图里面。

CPP文件夹内部的文件就是打包程序的源码，里面的build.bat是编译的脚本，将编译为一个dll，里面实现了一个高效的按照group分组的矩形装箱算法，输出所有贴图的布局信息，python根据此布局信息去合并大图：

实测的时间消耗如下，一共5074个物体，总耗时10.85秒，其中C++的矩形装箱为0.14秒

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

## Recode_Terrain_LQ.py

hybird_lightmap_packer.py 的地形处理功能由Recode_Terrain_LQ.py完成

它根据虚幻导出的json脚本，将导出的地形的大量的贴图合并为一张，并且重新归一化计算一个新的coef_add和coef_scale系数，以支持GPU-Driven的地形。

## convert_to_xml.py

convert_to_xml.py将json直接输出到对应的xml文件中，无需chaos重新导入

## GlobalParameter.py

GlobalParameter.py是打包程序所依赖的所有参数，以场景为单位组织

## 处理虚幻的资产的脚本

auto_uv.py 是处理虚幻里面错误2uv资产的脚本，将StaticMesh的generate_lightmap_uv设置为false，然后再手动点击uvEditor上面的generate uv1

clear_material_which_name_endwith_origin.py 功能和名字一样
