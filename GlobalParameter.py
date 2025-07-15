ALL_LIGHT_MAP_DATA = {
    "basic_level" : {
        # 从虚幻里导出的场景的lightmap的纹理文件所在的目录
        "source_lightmap_texture_path" : "C:/chaos_integrated_tools/data_analysis4/scene/light/light_map",
        # 从虚幻里导出的场景的JSON文件
        "source_lightmap_json_path" : "C:/chaos_integrated_tools/data_analysis4/scene/current_scene_data_source.json",
        # 场景的Chaos的XML文件
        "source_scene_xml_folder_path" : "D:/test/scene",
        # 在chaos的Runtime时记录的Lightmap的相对路径，就是资源的引用，该路径仅用于更新xml里面的资源路径，不涉及具体的资源读写
        "lightmap_path_in_chaos_assets" : "_project/New Folder1/lightMaps",
        # 地形的Chaos的XML文件
        "source_terrain_xml_path" : "C:/Users/qingbo.tang/Desktop/ai/basic_level.terrain.ast",
        # 在LightmapData的AST的路径，最终结果将会输入到这个文件之中
        "lightmap_data_ast_path_in_chaos" : "D:/ev/dev/wolfgang/_games/proven_ground/_content/New Folder1/lightMaps/lightmap_data.ast",
        # 地形的大小偏移，用以在runtime时，从世界坐标计算lightmap的uv坐标  uv = (world_pos + offset) / size; 注意offset的正负号使得uv: 0<uv<1
        "terrain_size_offset" : [512,512,512,512],
        # 合并为一张大纹理时，该纹理的大小
        "lightmap_texture_size" : 2048,
        # 合并为一张大纹理时，该纹理的最小大小
        "lightmap_texture_min_size" : 16,
        "max_mip_level" : 4,

        # 场景的左下角在世界坐标系中的位置 对应chaos中的xy坐标, 以下俩构成了一个矩形对角线，这个矩形框定了场景的边界，尽量是正方形
        "level_left_pos" : [-1024,-1024],
        # 场景的右上角在世界坐标系中的位置
        "level_right_pos" : [1024,1024], 

        # 各级lod的最远距离
        "lod_distance" : [100,200,400,800],

        ################################ 这俩暂时不用 #################################
        # CHAOS中Lightmap所在的绝对路径
        "lightmap_absolute_path" : "D:/ev/dev/wolfgang/_games/proven_ground/_content/New Folder1/lightMaps",
        # 原始lightmap所在的绝对路径
        "original_lightmap_absolute_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map/BigLightmap"
    },

    "carcassonne" : {
        "source_lightmap_texture_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map",
        "source_lightmap_json_path" : "C:/chaos_integrated_tools/data_analysis/scene/current_scene_data.json",
        "source_scene_xml_folder_path" : "E:\EV\dev\wolfgang\_games\proven_ground\_content\levels\LightMapScene\data_layers\default",
        "lightmap_path_in_chaos_assets" : "_project/testSimpleLM/lightMaps",
        "source_terrain_xml_path" : "D:/ev/dev/chaos/_content/levels/_test/basic_level/basic_level.terrain.ast",
        "lightmap_data_ast_path_in_chaos" : "E:\EV\dev\wolfgang\_games\proven_ground\_content\levels\lightmapscene\TestLightMapData.level_lightmap.ast.level_lightmap.ast",
        "terrain_size_offset" : [2048,2048,1024,1024],
        "lightmap_texture_size" : 2048,

        # 合并为一张大纹理时，该纹理的最小大小
        "lightmap_texture_min_size" : 16,
        # 合并为一张大纹理时，该纹理的最大mip级别,3表示有四个mip级别
        "max_mip_level" : 3,

        # 场景的左下角在世界坐标系中的位置 对应虚幻中的xy坐标, 以下俩构成了一个矩形对角线，这个矩形框定了场景的边界，尽量是正方形
        "level_left_pos" : [-65000,-14010],
        # 场景的右上角在世界坐标系中的位置
        "level_right_pos" : [30000,100000], 

        # 各级lod的最远距离
        "lod_distance" : [12500],

        "lightmap_absolute_path" : "D:/ev/dev/wolfgang/_games/proven_ground/_content/New Folder1/lightMaps",
        "original_lightmap_absolute_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map/BigLightmap"
    },

}

def load_light_map_data_from_json(json_path):
    """从JSON文件加载灯光贴图配置数据
    
    Args:
        json_path: JSON配置文件路径
        
    Returns:
        dict: 加载的配置数据字典
    """
    import json
    import os

    if not json_path:
        return
    
    try:
        # 检查文件是否存在
        if not os.path.exists(json_path):
            print(f"错误: 找不到配置文件 {json_path}")
            return
            
        # 读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
        # 验证数据格式
        if not isinstance(config_data, dict):
            print(f"错误: 配置文件格式不正确,应为字典格式")
            return
            
        # 遍历场景配置
        for scene_name, scene_config in config_data.items():
            # 验证必需的字段
            required_fields = [
                "source_lightmap_texture_path",
                "source_lightmap_json_path",
                "source_scene_xml_folder_path",
                "lightmap_path_in_chaos_assets",
                "source_terrain_xml_path",
                "terrain_size_offset",
                "lightmap_texture_size"
            ]
            
            missing_fields = [field for field in required_fields if field not in scene_config]
            if missing_fields:
                print(f"警告: 场景 '{scene_name}' 缺少必需的配置字段: {missing_fields}")
                continue
                
            # 添加到全局配置中
            ALL_LIGHT_MAP_DATA[scene_name] = scene_config
            print(f"已加载场景 '{scene_name}' 的配置数据")
            
        return 
        
    except Exception as e:
        print(f"加载配置文件时出错: {e}")
        return


DEFAULT_LIGHT_MAP_SCENE_NAME = "carcassonne"
