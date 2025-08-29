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
        # max_mip_level已移除，由算法根据格子数量自动计算完美四叉树的mip级别

        # 场景的左下角在世界坐标系中的位置 对应虚幻中的xy坐标, 以下俩构成了一个矩形对角线，这个矩形框定了场景的边界，尽量是正方形
        "level_left_pos" : [-1024,-1024],
        # 场景的右上角在世界坐标系中的位置
        "level_right_pos" : [1024,1024], 


        # mip0 一张贴图的边长对应的世界边长，mip1 是其二倍，以此类推
        # mip0_texture_size已移除，改为用户直接指定mip0格子数量
        "lightmap_mip0_grid_count": 8,  # mip0级别的n×n格子数中的n值 (必须是2的整数次幂: 2,4,8,16,32...)
        
        # 运行时lightmap加载距离数组，将写入ast的lightmap_mip_distance标签
        # 这是纯粹的运行时加载距离，与计算格子大小无关
        "lightmap_runtime_mip_distances": [1000, 2000, 4000, 8000],  # 运行时各mip级别的加载距离（虚幻厘米单位）

        # CHAOS中Lightmap所在的绝对路径
        "lightmap_absolute_path" : "D:/ev/dev/wolfgang/_games/proven_ground/_content/New Folder1/lightMaps",
        # 原始lightmap所在的绝对路径
        "original_lightmap_absolute_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map/BigLightmap"
    },

    "carcassonne" : {
        "source_lightmap_texture_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map",
        "source_lightmap_json_path" : "C:/chaos_integrated_tools/data_analysis/scene/current_scene_data.json",
        "source_scene_xml_folder_path" : "E:/EV/dev/wolfgang/_games/proven_ground/_content/levels/LightMapScene/data_layers/default",
        "lightmap_path_in_chaos_assets" : "_project/testSimpleLM/lightMaps",
        "source_terrain_xml_path" : "D:/ev/dev/chaos/_content/levels/_test/basic_level/basic_level.terrain.ast",
        "lightmap_data_ast_path_in_chaos" : "E:/EV/dev/wolfgang/_games/proven_ground/_content/levels/lightmapscene/TestLightMapData.level_lightmap.ast.level_lightmap.ast",
        "terrain_size_offset" : [2048,2048,1024,1024],
        "lightmap_texture_size" : 2048,

        # 合并为一张大纹理时，该纹理的最小边长
        "lightmap_texture_min_size" : 16,
        # max_mip_level已移除，由算法根据格子数量自动计算完美四叉树的mip级别

        # 场景的左下角在世界坐标系中的位置 对应虚幻中的xy坐标, 以下俩构成了一个矩形对角线，这个矩形框定了场景的边界，尽量是正方形
        "level_left_pos" : [-65000,-14010],
        # 场景的右上角在世界坐标系中的位置
        "level_right_pos" : [30000,100000], 

        # mip0 一张贴图的边长对应的世界边长
        # mip0_texture_size已移除，改为用户直接指定mip0格子数量  
        "lightmap_mip0_grid_count": 8,  # mip0级别的n×n格子数中的n值 (必须是2的整数次幂: 2,4,8,16,32...)
        
        # 运行时lightmap加载距离数组，将写入ast的lightmap_mip_distance标签
        # 这是纯粹的运行时加载距离，与计算格子大小无关
        "lightmap_runtime_mip_distances": [10000, 20000, 40000, 80000],  # 运行时各mip级别的加载距离（虚幻厘米单位）

        "lightmap_absolute_path" : "E:/EV/dev/wolfgang/_games/proven_ground/_content/testSimpleLM/lightMaps",
        "original_lightmap_absolute_path" : "C:/chaos_integrated_tools/data_analysis/scene/light/light_map/BigLightmap"
    },

}

'''
chaos_texture_document.cs中的TextureSerializeModel

    public const string TEXTURE_ID = "Texture_V2";
    private class TextureSerializeModel
    {
        public int MipBias { get; set; }
        public int CompressType { get; set; }
        public int MipGenType { get; set; }
        public uint MaxSize { get; set; }
        public bool SRgb { get; set; }
        public bool InvertG { get; set; }
        public uint XTillingMethod { get; set; }
        public uint YTillingMethod { get; set; }
        public float Brightness { get; set; }
        public float Saturation { get; set; }
        public float Hue { get; set; }
        public float MinAlpha { get; set; }
        public float MaxAlpha { get; set; }
        public string SourceFilePath { get; set; }
        public bool IsVolumeTexture { get; set; }
        public uint TileSizeX { get; set; }
        public uint TileSizeY { get; set; }
        public int SamplingFilterType { get; set; }
    }
'''
LightMapTextureParameter = {
    "MipBias": 0,
    "CompressType": 5,
    "MipGenType": 0,
    "MaxSize": 0,
    "SRgb": False,
    "InvertG": False,
    "XTillingMethod": 0,
    "YTillingMethod": 0,
    "Brightness": 1.0,
    "Saturation": 1.0,
    "Hue": 0.0,
    "MinAlpha": 0.0,
    "MaxAlpha": 1.0,
    "SourceFilePath": "",
    "IsVolumeTexture": False,
    "TileSizeX": 0,
    "TileSizeY": 0,
    "SamplingFilterType": 0,
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

# 自动加载外部配置文件
def _load_external_scene_config():
    """自动加载sceneConfig文件夹中的配置文件"""
    import json
    import os
    
    config_file_path = os.path.join("sceneConfig", "sceneConfig.json")
    
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                external_config = json.load(f)
            
            # 将外部配置合并到ALL_LIGHT_MAP_DATA中
            for scene_name, scene_config in external_config.items():
                ALL_LIGHT_MAP_DATA[scene_name] = scene_config
                #print(f"✓ 已从外部配置加载场景 '{scene_name}'")
                
            #print(f"✓ 外部配置文件加载完成，共加载 {len(external_config)} 个场景配置")
            
        except Exception as e:
            print(f"⚠️ 加载外部配置文件时出错: {e}")
    else:
        print(f"ℹ️ 未找到外部配置文件: {config_file_path}")

# 在模块加载时自动执行
_load_external_scene_config()

def convert_ue_position_to_chaos_position(position):
    """
    将虚幻引擎的位置坐标转换为Chaos的坐标
    
    Args:
        position: 虚幻引擎的位置坐标 [x, y, z]
        
    Returns:
        list: 转换后的Chaos坐标 [x, y, z]
    """
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        print(f"警告: 位置坐标格式不正确，应为[x, y]格式，当前: {position}")
        return position
    
    # 交换x和y坐标：(x, y) -> (y, x)
    local_location = [position[1], position[0]]
    
    # 根据导入/导出类型进行单位转换
    if True:
        # 从虚幻的厘米单位转换为Chaos的米单位（除以100）
        local_location[0] /= 100.0
        local_location[1] /= 100.0
    
    
    return local_location

def list_all_scenes():
    """列出所有可用的场景配置"""
    print("=" * 60)
    print("所有可用的场景配置:")
    print("=" * 60)
    
    if not ALL_LIGHT_MAP_DATA:
        print("未找到任何场景配置")
        return
    
    # 按场景名排序
    sorted_scenes = sorted(ALL_LIGHT_MAP_DATA.keys())
    
    for i, scene_name in enumerate(sorted_scenes, 1):
        scene_config = ALL_LIGHT_MAP_DATA[scene_name]
        print(f"\n{i:2d}. 场景名称: {scene_name}")
        print(f"    XML路径: {scene_config.get('source_scene_xml_folder_path', 'N/A')}")
        print(f"    JSON路径: {scene_config.get('source_lightmap_json_path', 'N/A')}")
        print(f"    输出路径: {scene_config.get('lightmap_data_ast_path_in_chaos', 'N/A')}")
        
        # 显示场景边界
        left_pos = scene_config.get('level_left_pos', [0, 0])
        right_pos = scene_config.get('level_right_pos', [0, 0])
        print(f"    场景边界: {left_pos} 到 {right_pos}")
    
    print(f"\n总共 {len(sorted_scenes)} 个场景配置")
    print("=" * 60)

def show_scene_config(scene_name):
    """显示指定场景的详细配置"""
    if scene_name not in ALL_LIGHT_MAP_DATA:
        print(f"❌ 错误: 场景 '{scene_name}' 不存在")
        print(f"可用场景: {list(ALL_LIGHT_MAP_DATA.keys())}")
        return
    
    scene_config = ALL_LIGHT_MAP_DATA[scene_name]
    
    print("=" * 60)
    print(f"场景配置详情: {scene_name}")
    print("=" * 60)
    
    # 路径配置
    print("\n📁 路径配置:")
    print("-" * 40)
    print(f"光照图纹理路径:     {scene_config.get('source_lightmap_texture_path', 'N/A')}")
    print(f"场景JSON文件路径:   {scene_config.get('source_lightmap_json_path', 'N/A')}")
    print(f"场景XML文件夹路径:  {scene_config.get('source_scene_xml_folder_path', 'N/A')}")
    print(f"地形XML文件路径:    {scene_config.get('source_terrain_xml_path', 'N/A')}")
    print(f"输出AST文件路径:    {scene_config.get('lightmap_data_ast_path_in_chaos', 'N/A')}")
    print(f"Chaos资源路径:      {scene_config.get('lightmap_path_in_chaos_assets', 'N/A')}")
    print(f"Chaos绝对路径:      {scene_config.get('lightmap_absolute_path', 'N/A')}")
    print(f"原始光照图路径:     {scene_config.get('original_lightmap_absolute_path', 'N/A')}")
    
    # 场景范围配置
    print("\n🗺️ 场景范围配置:")
    print("-" * 40)
    left_pos = scene_config.get('level_left_pos', [0, 0])
    right_pos = scene_config.get('level_right_pos', [0, 0])
    print(f"左下角坐标:         {left_pos}")
    print(f"右上角坐标:         {right_pos}")
    
    # 计算场景大小
    if len(left_pos) >= 2 and len(right_pos) >= 2:
        width = abs(right_pos[0] - left_pos[0])
        height = abs(right_pos[1] - left_pos[1])
        print(f"场景尺寸:           {width} x {height}")
    
    # 纹理配置
    print("\n🖼️ 纹理配置:")
    print("-" * 40)
    print(f"光照图纹理大小:     {scene_config.get('lightmap_texture_size', 'N/A')}")
    print(f"光照图最小大小:     {scene_config.get('lightmap_texture_min_size', 'N/A')}")
    print(f"Mip0格子数量:       {scene_config.get('lightmap_mip0_grid_count', 'N/A')} * {scene_config.get('lightmap_mip0_grid_count', 'N/A')}")
     
    # 运行时距离配置
    print("\n🚀 运行时加载距离配置:")
    print("-" * 40)
    runtime_distances = scene_config.get('lightmap_runtime_mip_distances', [])
    if runtime_distances:
        print(f"运行时距离:         {runtime_distances}")
        for i, distance in enumerate(runtime_distances):
            print(f"  - Mip {i}: {distance} 厘米")
    else:
        print("运行时距离:         未配置")
    
    # 地形配置
    print("\n🏔️ 地形配置:")
    print("-" * 40)
    terrain_offset = scene_config.get('terrain_size_offset', [])
    if terrain_offset and len(terrain_offset) >= 4:
        print(f"地形大小偏移:       {terrain_offset}")
        print(f"  - 大小: {terrain_offset[0]} x {terrain_offset[1]}")
        print(f"  - 偏移: {terrain_offset[2]}, {terrain_offset[3]}")
    else:
        print("地形大小偏移:       未配置")
    
    print("=" * 60)

def main():
    """主函数，处理命令行参数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="GlobalParameter 场景配置管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python GlobalParameter.py --list                    # 列出所有场景
  python GlobalParameter.py --show carcassonne        # 显示carcassonne场景配置
  python GlobalParameter.py --show-all               # 显示所有场景的详细配置
        """
    )
    
    parser.add_argument("--list", "-l", action="store_true",
                      help="列出所有可用的场景配置")
    
    parser.add_argument("--show", "-s", type=str, metavar="SCENE_NAME",
                      help="显示指定场景的详细配置")
    
    parser.add_argument("--show-all", action="store_true",
                      help="显示所有场景的详细配置")
    
    args = parser.parse_args()
    
    # 如果没有提供任何参数，显示帮助信息
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    # 处理参数
    if args.list:
        list_all_scenes()
    
    elif args.show:
        show_scene_config(args.show)
    
    elif args.show_all:
        print("=" * 60)
        print("所有场景的详细配置")
        print("=" * 60)
        
        sorted_scenes = sorted(ALL_LIGHT_MAP_DATA.keys())
        for i, scene_name in enumerate(sorted_scenes, 1):
            if i > 1:
                print("\n" + "=" * 60)
            show_scene_config(scene_name)

if __name__ == "__main__":
    main()
