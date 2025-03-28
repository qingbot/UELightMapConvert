
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
        # 地形的大小偏移，用以在runtime时，从世界坐标计算lightmap的uv坐标  uv = (world_pos + offset) / size ; 0<uv<1
        "terrain_size_offset" : [512,512,512,512],
        # 合并为一张大纹理时，该纹理的大小
        "lightmap_texture_size" : 2048,
        # 合并为一张大纹理时，该纹理的最小大小
        "lightmap_texture_min_size" : 16,

        ################################ 这俩暂时不用 #################################
        # CHAOS中Lightmap所在的绝对路径
        "lightmap_absolute_path" : "D:/ev/dev/wolfgang/_games/proven_ground/_content/New Folder1/lightMaps",
        # 原始lightmap所在的绝对路径
        "original_lightmap_absolute_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map/BigLightmap"
    },


    "carcassonne" : {
        "source_lightmap_texture_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map",
        "source_lightmap_json_path" : "C:/chaos_integrated_tools/data_analysis/scene/current_scene_data.json",
        "source_scene_xml_folder_path" : "D:/test/scene",
        "lightmap_path_in_chaos_assets" : "_project/testSimpleLM/lightMaps",
        "source_terrain_xml_path" : "D:/ev/dev/chaos/_content/levels/_test/basic_level/basic_level.terrain.ast",
        "terrain_size_offset" : [1024,1024,512,512],
        "lightmap_texture_size" : 2048,

        "lightmap_absolute_path" : "D:/ev/dev/wolfgang/_games/proven_ground/_content/New Folder1/lightMaps",
        "original_lightmap_absolute_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map/BigLightmap"
    },

}

DEFAULT_LIGHT_MAP_SCENE_NAME = "basic_level"
