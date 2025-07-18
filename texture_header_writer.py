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
                # 写入前导字节 (0x0a)
                f.write(b'\x0a')
                
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

    def read_texture_header(self, texture_file_path: str) -> dict:
        """
        读取并解析chaos贴图文件头的所有数据
        
        Args:
            texture_file_path: .texture.ast文件路径
            
        Returns:
            dict: 包含所有文件头数据的字典，格式为：
                {
                    "texture_id": "Texture_V2",
                    "bson_data_length": 1234,
                    "image_data_length": 5678,
                    "settings": {
                        "MipBias": 0,
                        "CompressType": 0,
                        ...
                    }
                }
        """
        try:
            if not os.path.exists(texture_file_path):
                raise FileNotFoundError(f"贴图文件不存在: {texture_file_path}")
            
            result = {}
            
            with open(texture_file_path, 'rb') as f:
                # 跳过第一个字节（0x0a）
                f.read(1)
                
                # 读取TEXTURE_ID
                texture_id_bytes = f.read(len(self.TEXTURE_ID))
                texture_id = texture_id_bytes.decode('utf-8')
                result["texture_id"] = texture_id
                
                if texture_id != self.TEXTURE_ID:
                    raise ValueError(f"无效的TEXTURE_ID: 期望'{self.TEXTURE_ID}', 实际'{texture_id}'")
                
                # 读取BSON数据长度
                bson_length_bytes = f.read(4)
                if len(bson_length_bytes) != 4:
                    raise ValueError("文件格式错误: 无法读取BSON数据长度")
                
                bson_length = struct.unpack('<i', bson_length_bytes)[0]
                result["bson_data_length"] = bson_length
                
                if bson_length <= 0:
                    raise ValueError(f"无效的BSON数据长度: {bson_length}")
                
                # 读取BSON数据
                bson_data = f.read(bson_length)
                if len(bson_data) != bson_length:
                    raise ValueError(f"BSON数据长度不匹配: 期望{bson_length}, 实际{len(bson_data)}")
                
                # 解析BSON数据
                try:
                    settings = bson.decode(bson_data)
                    result["settings"] = settings
                except Exception as e:
                    raise ValueError(f"解析BSON数据失败: {e}")
                
                # 读取图像数据长度
                image_length_bytes = f.read(4)
                if len(image_length_bytes) != 4:
                    raise ValueError("文件格式错误: 无法读取图像数据长度")
                
                image_length = struct.unpack('<i', image_length_bytes)[0]
                result["image_data_length"] = image_length
                
                if image_length <= 0:
                    raise ValueError(f"无效的图像数据长度: {image_length}")
                
                # 验证剩余数据长度
                current_pos = f.tell()
                f.seek(0, 2)  # 移动到文件末尾
                file_size = f.tell()
                remaining_data_length = file_size - current_pos
                
                if remaining_data_length != image_length:
                    raise ValueError(f"图像数据长度不匹配: 期望{image_length}, 实际{remaining_data_length}")
                
                # 计算总文件大小
                result["total_file_size"] = file_size
                result["header_size"] = current_pos
                
                print(f"✅ 成功读取贴图文件头: {texture_file_path}")
                print(f"   - 文件总大小: {file_size} 字节")
                print(f"   - 文件头大小: {current_pos} 字节")
                print(f"   - BSON数据长度: {bson_length} 字节")
                print(f"   - 图像数据长度: {image_length} 字节")
                
                return result
                
        except Exception as e:
            print(f"❌ 读取贴图文件头失败: {e}")
            raise
    
    def print_texture_header_info(self, texture_file_path: str):
        """
        打印贴图文件头的详细信息
        
        Args:
            texture_file_path: .texture.ast文件路径
        """
        try:
            header_data = self.read_texture_header(texture_file_path)
            
            print(f"\n=== 贴图文件头信息 ===")
            print(f"文件路径: {texture_file_path}")
            print(f"文件大小: {header_data['total_file_size']} 字节")
            print(f"文件头大小: {header_data['header_size']} 字节")
            print(f"Texture ID: {header_data['texture_id']}")
            print(f"BSON数据长度: {header_data['bson_data_length']} 字节")
            print(f"图像数据长度: {header_data['image_data_length']} 字节")
            
            print(f"\n=== 贴图设置 (所有键值对) ===")
            settings = header_data['settings']
            
            # 按键名排序以便更好的阅读
            sorted_settings = sorted(settings.items())
            
            for key, value in sorted_settings:
                # 格式化不同类型的值
                if isinstance(value, bool):
                    value_str = "True" if value else "False"
                elif isinstance(value, (int, float)):
                    value_str = str(value)
                elif isinstance(value, str):
                    value_str = f'"{value}"'
                else:
                    value_str = str(value)
                
                print(f"  {key:20s}: {value_str}")
            
            print(f"\n=== 统计信息 ===")
            print(f"总设置项数量: {len(settings)}")
            print(f"压缩比例: {header_data['image_data_length'] / header_data['total_file_size'] * 100:.1f}% (图像数据占比)")
            
        except Exception as e:
            print(f"❌ 打印贴图文件头信息失败: {e}")


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