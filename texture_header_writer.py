import os
import struct
import bson
from pathlib import Path
from typing import Optional

class TextureHeaderWriter:
    """
    绕过Chaos引擎导入，直接生成带有元数据头的贴图文件
    """
    
    TEXTURE_ID = "Texture_V2"
    
    def __init__(self):
        # 默认贴图设置
        self.default_settings = {
            "MipBias": 0,
            "CompressType": 0,  # 可能需要根据实际情况调整
            "MipGenType": 0,
            "MaxSize": 2048,
            "SRgb": True,
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
            "SamplingFilterType": 0
        }
    
    def create_texture_file(self, source_image_path: str, output_path: str, 
                           custom_settings: Optional[dict] = None):
        """
        创建带有元数据头的贴图文件
        
        Args:
            source_image_path: 源图像文件路径
            output_path: 输出的.texture.ast文件路径
            custom_settings: 自定义设置，会覆盖默认设置
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # 读取源图像数据
            with open(source_image_path, 'rb') as f:
                source_image_data = f.read()
            
            # 准备贴图设置
            settings = self.default_settings.copy()
            if custom_settings:
                settings.update(custom_settings)
            
            # 设置源文件路径
            settings["SourceFilePath"] = source_image_path
            
            # 创建输出文件
            with open(output_path, 'wb') as f:
                # 写入TEXTURE_ID
                texture_id_bytes = self.TEXTURE_ID.encode('utf-8')
                f.write(texture_id_bytes)
                
                # 序列化设置为BSON
                bson_data = bson.encode(settings)
                
                # 写入BSON数据长度
                f.write(struct.pack('<i', len(bson_data)))
                
                # 写入BSON数据
                f.write(bson_data)
                
                # 写入源图像数据长度
                f.write(struct.pack('<i', len(source_image_data)))
                
                # 写入源图像数据
                f.write(source_image_data)
            
            print(f"成功创建贴图文件: {output_path}")
            print(f"源图像大小: {len(source_image_data)} 字节")
            print(f"BSON元数据大小: {len(bson_data)} 字节")
            
        except Exception as e:
            print(f"创建贴图文件失败: {e}")
            raise
    
    def batch_convert_textures(self, source_dir: str, output_dir: str, 
                              custom_settings: Optional[dict] = None):
        """
        批量转换贴图文件
        
        Args:
            source_dir: 源图像目录
            output_dir: 输出目录
            custom_settings: 自定义设置
        """
        source_path = Path(source_dir)
        output_path = Path(output_dir)
        
        # 支持的图像格式
        supported_formats = {'.png', '.jpg', '.jpeg', '.tga', '.bmp', '.tiff'}
        
        converted_count = 0
        
        for image_file in source_path.rglob('*'):
            if image_file.suffix.lower() in supported_formats:
                # 保持目录结构
                relative_path = image_file.relative_to(source_path)
                output_file = output_path / relative_path.with_suffix('.texture.ast')
                
                # 确保输出目录存在
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    self.create_texture_file(
                        str(image_file), 
                        str(output_file), 
                        custom_settings
                    )
                    converted_count += 1
                except Exception as e:
                    print(f"转换 {image_file} 失败: {e}")
        
        print(f"批量转换完成，共转换 {converted_count} 个文件")
    
    def create_lightmap_texture(self, source_image_path: str, output_path: str):
        """
        创建光照图贴图文件，使用适合光照图的设置
        
        Args:
            source_image_path: 源图像文件路径
            output_path: 输出的.texture.ast文件路径
        """
        # 光照图特定设置
        lightmap_settings = {
            "SRgb": False,  # 光照图通常不使用sRGB
            "CompressType": 1,  # 可能需要特定的压缩类型
            "MipGenType": 1,  # 光照图可能需要特定的mip生成
            "MaxSize": 4096,  # 光照图可能需要更大的尺寸
        }
        
        self.create_texture_file(source_image_path, output_path, lightmap_settings)


def main():
    """
    示例使用方法
    """
    writer = TextureHeaderWriter()
    
    # 示例1：转换单个贴图
    if os.path.exists("example_texture.png"):
        writer.create_texture_file(
            "example_texture.png", 
            "output/example_texture.texture.ast"
        )
    
    # 示例2：批量转换贴图
    if os.path.exists("source_textures"):
        writer.batch_convert_textures(
            "source_textures", 
            "output/textures"
        )
    
    # 示例3：创建光照图贴图
    if os.path.exists("lightmap.png"):
        writer.create_lightmap_texture(
            "lightmap.png", 
            "output/lightmap.texture.ast"
        )
    
    print("示例完成！")


if __name__ == "__main__":
    main() 