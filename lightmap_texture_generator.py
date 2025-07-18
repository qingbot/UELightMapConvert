import os
import json
import argparse
from pathlib import Path
from texture_header_writer import TextureHeaderWriter
import GlobalParameter

class LightmapTextureGenerator:
    """
    专门用于处理光照图贴图的生成器
    与lightmap_converter.py配合使用
    """
    
    def __init__(self):
        self.texture_writer = TextureHeaderWriter()
        
        # 光照图专用设置
        self.lightmap_settings = {
            "SRgb": False,  # 光照图不使用sRGB
            "CompressType": 1,  # 可能需要特定的压缩类型
            "MipGenType": 1,  # 光照图需要特定的mip生成
            "MaxSize": 4096,  # 光照图可能需要更大的尺寸
            "InvertG": False,
            "XTillingMethod": 0,  # 光照图通常不平铺
            "YTillingMethod": 0,
            "Brightness": 1.0,
            "Saturation": 1.0,
            "Hue": 0.0,
            "MinAlpha": 0.0,
            "MaxAlpha": 1.0,
            "IsVolumeTexture": False,
            "TileSizeX": 0,
            "TileSizeY": 0,
            "SamplingFilterType": 1  # 光照图可能需要线性过滤
        }
        
        # 方向图专用设置
        self.dirmap_settings = {
            "SRgb": False,  # 方向图也不使用sRGB
            "CompressType": 2,  # 方向图可能需要不同的压缩类型
            "MipGenType": 1,
            "MaxSize": 4096,
            "InvertG": False,
            "XTillingMethod": 0,
            "YTillingMethod": 0,
            "Brightness": 1.0,
            "Saturation": 1.0,
            "Hue": 0.0,
            "MinAlpha": 0.0,
            "MaxAlpha": 1.0,
            "IsVolumeTexture": False,
            "TileSizeX": 0,
            "TileSizeY": 0,
            "SamplingFilterType": 1
        }
    
    def process_scene_lightmaps(self, scene_name: str):
        """
        处理指定场景的所有光照图贴图
        
        Args:
            scene_name: 场景名称
        """
        if scene_name not in GlobalParameter.ALL_LIGHT_MAP_DATA:
            print(f"错误: 场景 '{scene_name}' 不存在")
            print(f"可用场景: {', '.join(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())}")
            return
        
        scene_config = GlobalParameter.ALL_LIGHT_MAP_DATA[scene_name]
        
        # 获取源光照图路径
        source_lightmap_path = scene_config["source_lightmap_texture_path"]
        
        # 获取输出路径
        lightmap_path_in_chaos = scene_config["lightmap_path_in_chaos_assets"]
        
        print(f"处理场景: {scene_name}")
        print(f"源光照图路径: {source_lightmap_path}")
        print(f"输出路径: {lightmap_path_in_chaos}")
        
        # 处理BigMap输出的光照图
        self.process_bigmap_lightmaps(source_lightmap_path, lightmap_path_in_chaos)
        
        # 处理地形光照图（如果存在）
        self.process_terrain_lightmaps(source_lightmap_path, lightmap_path_in_chaos)
    
    def process_bigmap_lightmaps(self, source_path: str, output_path: str):
        """
        处理BigMap输出的光照图贴图（分类文件夹结构）
        
        Args:
            source_path: 源路径
            output_path: 输出路径
        """
        bigmap_dir = Path(source_path).parent / "BigMap"
        output_dir = Path(output_path)
        
        if not bigmap_dir.exists():
            print(f"BigMap目录不存在: {bigmap_dir}")
            return
        
        print(f"处理BigMap光照图: {bigmap_dir}")
        
        # 处理lightmap文件夹中的LQ纹理
        lightmap_dir = bigmap_dir / "lightmap"
        if lightmap_dir.exists():
            self.process_lightmap_folder(lightmap_dir, output_dir / "lightmap", "LQ")
        
        # 处理dir文件夹中的Dir纹理
        dir_dir = bigmap_dir / "dir"
        if dir_dir.exists():
            self.process_lightmap_folder(dir_dir, output_dir / "dir", "Dir")
    
    def process_lightmap_folder(self, source_folder: Path, output_folder: Path, texture_type: str):
        """
        处理光照图文件夹
        
        Args:
            source_folder: 源文件夹
            output_folder: 输出文件夹
            texture_type: 纹理类型 ("LQ" 或 "Dir")
        """
        print(f"处理{texture_type}纹理文件夹: {source_folder}")
        
        # 确保输出目录存在
        output_folder.mkdir(parents=True, exist_ok=True)
        
        # 选择适当的设置
        settings = self.lightmap_settings if texture_type == "LQ" else self.dirmap_settings
        
        converted_count = 0
        
        for png_file in source_folder.glob("*.png"):
            # 生成输出文件名
            output_file = output_folder / f"{png_file.stem}.texture.ast"
            
            try:
                self.texture_writer.create_texture_file(
                    str(png_file),
                    str(output_file),
                    settings
                )
                converted_count += 1
                print(f"  转换成功: {png_file.name} -> {output_file.name}")
            except Exception as e:
                print(f"  转换失败: {png_file.name} - {e}")
        
        print(f"  {texture_type}纹理转换完成: {converted_count} 个文件")
    
    def process_terrain_lightmaps(self, source_path: str, output_path: str):
        """
        处理地形光照图
        
        Args:
            source_path: 源路径
            output_path: 输出路径
        """
        terrain_dir = Path(source_path).parent / "terrain_lightmaps"
        output_dir = Path(output_path)
        
        if not terrain_dir.exists():
            print(f"地形光照图目录不存在: {terrain_dir}")
            return
        
        print(f"处理地形光照图: {terrain_dir}")
        
        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)
        
        converted_count = 0
        
        for png_file in terrain_dir.glob("*.png"):
            # 生成输出文件名
            output_file = output_dir / f"{png_file.stem}.texture.ast"
            
            try:
                self.texture_writer.create_texture_file(
                    str(png_file),
                    str(output_file),
                    self.lightmap_settings  # 地形使用光照图设置
                )
                converted_count += 1
                print(f"  转换成功: {png_file.name} -> {output_file.name}")
            except Exception as e:
                print(f"  转换失败: {png_file.name} - {e}")
        
        print(f"  地形光照图转换完成: {converted_count} 个文件")
    
    def process_custom_lightmaps(self, source_dir: str, output_dir: str, 
                                texture_type: str = "LQ"):
        """
        处理自定义光照图目录
        
        Args:
            source_dir: 源目录
            output_dir: 输出目录
            texture_type: 纹理类型 ("LQ" 或 "Dir")
        """
        source_path = Path(source_dir)
        output_path = Path(output_dir)
        
        if not source_path.exists():
            print(f"源目录不存在: {source_path}")
            return
        
        print(f"处理自定义光照图目录: {source_path}")
        
        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 选择适当的设置
        settings = self.lightmap_settings if texture_type == "LQ" else self.dirmap_settings
        
        converted_count = 0
        
        # 递归处理所有PNG文件
        for png_file in source_path.rglob("*.png"):
            # 保持目录结构
            relative_path = png_file.relative_to(source_path)
            output_file = output_path / relative_path.with_suffix('.texture.ast')
            
            # 确保输出目录存在
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                self.texture_writer.create_texture_file(
                    str(png_file),
                    str(output_file),
                    settings
                )
                converted_count += 1
                print(f"  转换成功: {relative_path}")
            except Exception as e:
                print(f"  转换失败: {relative_path} - {e}")
        
        print(f"  自定义光照图转换完成: {converted_count} 个文件")
    
    def update_texture_settings(self, texture_type: str, settings: dict):
        """
        更新纹理设置
        
        Args:
            texture_type: 纹理类型 ("LQ" 或 "Dir")
            settings: 要更新的设置
        """
        if texture_type == "LQ":
            self.lightmap_settings.update(settings)
        elif texture_type == "Dir":
            self.dirmap_settings.update(settings)
        else:
            print(f"未知纹理类型: {texture_type}")


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="生成光照图贴图文件")
    
    parser.add_argument("--scene", "-s", type=str, 
                       default=GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME,
                       help=f"要处理的场景名称，默认为{GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME}")
    
    parser.add_argument("--source-dir", type=str,
                       help="自定义源目录路径")
    
    parser.add_argument("--output-dir", type=str,
                       help="自定义输出目录路径")
    
    parser.add_argument("--texture-type", type=str, choices=["LQ", "Dir"],
                       default="LQ", help="纹理类型")
    
    parser.add_argument("--custom-mode", action="store_true",
                       help="使用自定义模式处理指定目录")
    
    args = parser.parse_args()
    
    generator = LightmapTextureGenerator()
    
    if args.custom_mode:
        # 自定义模式
        if not args.source_dir or not args.output_dir:
            print("自定义模式需要指定 --source-dir 和 --output-dir")
            return
        
        generator.process_custom_lightmaps(
            args.source_dir, 
            args.output_dir, 
            args.texture_type
        )
    else:
        # 场景模式
        generator.process_scene_lightmaps(args.scene)
    
    print("处理完成！")


if __name__ == "__main__":
    main() 