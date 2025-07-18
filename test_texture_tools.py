#!/usr/bin/env python3
"""
测试贴图工具功能
"""

import os
import sys
import struct
import tempfile
import shutil
from pathlib import Path
from PIL import Image
import numpy as np

def create_test_image(width=256, height=256, output_path="test_texture.png"):
    """
    创建一个测试图像
    """
    # 创建一个简单的渐变测试图像
    image = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 创建水平渐变
    for x in range(width):
        for y in range(height):
            image[y, x] = [
                int(255 * x / width),      # 红色渐变
                int(255 * y / height),     # 绿色渐变
                128                        # 蓝色固定
            ]
    
    # 保存图像
    img = Image.fromarray(image)
    img.save(output_path)
    print(f"创建测试图像: {output_path}")
    return output_path

def verify_texture_file(texture_path):
    """
    验证生成的贴图文件格式
    """
    try:
        with open(texture_path, 'rb') as f:
            # 跳过第一个字节然后读取TEXTURE_ID
            f.read(1)  # 跳过0x0a
            texture_id = f.read(10).decode('utf-8')  # "Texture_V2"
            if texture_id != "Texture_V2":
                print(f"❌ 错误的TEXTURE_ID: {texture_id}")
                return False
            
            # 读取BSON数据长度
            bson_length = struct.unpack('<i', f.read(4))[0]
            if bson_length <= 0:
                print(f"❌ 无效的BSON数据长度: {bson_length}")
                return False
            
            # 跳过BSON数据
            f.seek(bson_length, 1)
            
            # 读取图像数据长度
            image_length = struct.unpack('<i', f.read(4))[0]
            if image_length <= 0:
                print(f"❌ 无效的图像数据长度: {image_length}")
                return False
            
            # 检查剩余数据长度
            remaining = len(f.read())
            if remaining != image_length:
                print(f"❌ 图像数据长度不匹配: 期望{image_length}, 实际{remaining}")
                return False
            
            print(f"✅ 贴图文件格式验证通过")
            print(f"   - TEXTURE_ID: {texture_id}")
            print(f"   - BSON数据长度: {bson_length}")
            print(f"   - 图像数据长度: {image_length}")
            return True
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

def test_texture_header_writer():
    """
    测试TextureHeaderWriter功能
    """
    print("\n=== 测试TextureHeaderWriter ===")
    
    try:
        from texture_header_writer import TextureHeaderWriter
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 创建测试图像
            test_image = create_test_image(256, 256, temp_path / "test_input.png")
            
            # 创建TextureHeaderWriter实例
            writer = TextureHeaderWriter()
            
            # 测试1: 基本转换
            print("\n测试1: 基本转换")
            output_file = temp_path / "test_output.texture.ast"
            writer.create_texture_file(str(test_image), str(output_file))
            
            if output_file.exists():
                print("✅ 基本转换成功")
                verify_texture_file(str(output_file))
            else:
                print("❌ 基本转换失败")
                return False
            
            # 测试2: 自定义设置
            print("\n测试2: 自定义设置")
            custom_settings = {
                "MaxSize": 512,
                "SRgb": False,
                "CompressType": 1,
                "Brightness": 1.2
            }
            
            output_file2 = temp_path / "test_custom.texture.ast"
            writer.create_texture_file(str(test_image), str(output_file2), custom_settings)
            
            if output_file2.exists():
                print("✅ 自定义设置转换成功")
                verify_texture_file(str(output_file2))
            else:
                print("❌ 自定义设置转换失败")
                return False
            
            # 测试3: 光照图转换
            print("\n测试3: 光照图转换")
            output_file3 = temp_path / "test_lightmap.texture.ast"
            writer.create_lightmap_texture(str(test_image), str(output_file3))
            
            if output_file3.exists():
                print("✅ 光照图转换成功")
                verify_texture_file(str(output_file3))
            else:
                print("❌ 光照图转换失败")
                return False
            
            # 测试4: 批量转换
            print("\n测试4: 批量转换")
            batch_input_dir = temp_path / "batch_input"
            batch_output_dir = temp_path / "batch_output"
            batch_input_dir.mkdir()
            
            # 创建多个测试图像
            for i in range(3):
                create_test_image(128, 128, batch_input_dir / f"test_{i}.png")
            
            writer.batch_convert_textures(str(batch_input_dir), str(batch_output_dir))
            
            # 检查输出文件
            output_files = list(batch_output_dir.glob("*.texture.ast"))
            if len(output_files) == 3:
                print("✅ 批量转换成功")
                for output_file in output_files:
                    verify_texture_file(str(output_file))
            else:
                print(f"❌ 批量转换失败: 期望3个文件, 实际{len(output_files)}个")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ TextureHeaderWriter测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_texture_header_reader():
    """
    测试贴图文件头读取功能
    """
    print("\n=== 测试贴图文件头读取功能 ===")
    
    try:
        from texture_header_writer import TextureHeaderWriter
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 创建测试图像
            test_image = create_test_image(256, 256, temp_path / "test_input.png")
            
            # 创建TextureHeaderWriter实例
            writer = TextureHeaderWriter()
            
            # 首先创建一个贴图文件
            print("\n步骤1: 创建测试贴图文件")
            test_texture_file = temp_path / "test_texture.texture.ast"
            custom_settings = {
                "MaxSize": 1024,
                "SRgb": False,
                "CompressType": 2,
                "Brightness": 1.5,
                "Saturation": 0.8,
                "Hue": 0.1,
                "MinAlpha": 0.2,
                "MaxAlpha": 0.9,
                "IsVolumeTexture": True,
                "TileSizeX": 64,
                "TileSizeY": 64,
                "SamplingFilterType": 1
            }
            
            writer.create_texture_file(str(test_image), str(test_texture_file), custom_settings)
            
            if not test_texture_file.exists():
                print("❌ 测试贴图文件创建失败")
                return False
            
            # 测试读取文件头
            print("\n步骤2: 测试读取文件头数据")
            header_data = writer.read_texture_header(str(test_texture_file))
            
            # 验证读取的数据
            print("验证读取的数据...")
            
            # 验证基本信息
            if header_data["texture_id"] != "Texture_V2":
                print(f"❌ Texture ID不匹配: {header_data['texture_id']}")
                return False
            
            if header_data["bson_data_length"] <= 0:
                print(f"❌ BSON数据长度无效: {header_data['bson_data_length']}")
                return False
            
            if header_data["image_data_length"] <= 0:
                print(f"❌ 图像数据长度无效: {header_data['image_data_length']}")
                return False
            
            # 验证设置数据
            settings = header_data["settings"]
            
            # 验证我们设置的自定义值
            expected_settings = {
                "MaxSize": 1024,
                "SRgb": False,
                "CompressType": 2,
                "Brightness": 1.5,
                "Saturation": 0.8,
                "Hue": 0.1,
                "MinAlpha": 0.2,
                "MaxAlpha": 0.9,
                "IsVolumeTexture": True,
                "TileSizeX": 64,
                "TileSizeY": 64,
                "SamplingFilterType": 1
            }
            
            for key, expected_value in expected_settings.items():
                if key not in settings:
                    print(f"❌ 设置项缺失: {key}")
                    return False
                
                actual_value = settings[key]
                if actual_value != expected_value:
                    print(f"❌ 设置项值不匹配: {key}, 期望: {expected_value}, 实际: {actual_value}")
                    return False
            
            print("✅ 文件头数据验证通过")
            
            # 测试打印详细信息
            print("\n步骤3: 测试打印详细信息")
            writer.print_texture_header_info(str(test_texture_file))
            
            # 测试JSON输出
            print("\n步骤4: 测试JSON输出")
            json_output_file = temp_path / "header_output.json"
            
            import json
            with open(json_output_file, 'w', encoding='utf-8') as f:
                json.dump(header_data, f, indent=2, ensure_ascii=False)
            
            # 验证JSON文件
            if json_output_file.exists():
                with open(json_output_file, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                
                # 验证JSON数据完整性
                if loaded_data["texture_id"] != header_data["texture_id"]:
                    print("❌ JSON数据不一致")
                    return False
                
                print("✅ JSON输出验证通过")
            else:
                print("❌ JSON文件创建失败")
                return False
            
            # 测试批量处理
            print("\n步骤5: 测试批量处理")
            batch_dir = temp_path / "batch_test"
            batch_dir.mkdir()
            
            # 创建多个测试文件
            for i in range(3):
                test_img = create_test_image(128, 128, batch_dir / f"test_{i}.png")
                test_texture = batch_dir / f"test_{i}.texture.ast"
                writer.create_texture_file(str(test_img), str(test_texture))
            
            # 批量读取
            texture_files = list(batch_dir.glob("*.texture.ast"))
            if len(texture_files) != 3:
                print(f"❌ 批量测试文件数量不正确: {len(texture_files)}")
                return False
            
            batch_success = True
            for texture_file in texture_files:
                try:
                    batch_header_data = writer.read_texture_header(str(texture_file))
                    if batch_header_data["texture_id"] != "Texture_V2":
                        batch_success = False
                        break
                except Exception as e:
                    print(f"❌ 批量读取失败: {texture_file} - {e}")
                    batch_success = False
                    break
            
            if batch_success:
                print("✅ 批量处理验证通过")
            else:
                print("❌ 批量处理验证失败")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ 贴图文件头读取功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_lightmap_texture_generator():
    """
    测试LightmapTextureGenerator功能
    """
    print("\n=== 测试LightmapTextureGenerator ===")
    
    try:
        from lightmap_texture_generator import LightmapTextureGenerator
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 创建测试光照图结构
            lightmap_dir = temp_path / "lightmap"
            dir_dir = temp_path / "dir"
            lightmap_dir.mkdir()
            dir_dir.mkdir()
            
            # 创建测试光照图
            for i in range(2):
                create_test_image(512, 512, lightmap_dir / f"packed_lightmap_{i}.png")
                create_test_image(512, 512, dir_dir / f"packed_lightmap_{i}_dir.png")
            
            # 创建LightmapTextureGenerator实例
            generator = LightmapTextureGenerator()
            
            # 测试1: 处理光照图文件夹
            print("\n测试1: 处理光照图文件夹")
            output_lightmap_dir = temp_path / "output_lightmap"
            output_dir_dir = temp_path / "output_dir"
            
            generator.process_lightmap_folder(lightmap_dir, output_lightmap_dir, "LQ")
            generator.process_lightmap_folder(dir_dir, output_dir_dir, "Dir")
            
            # 检查输出文件
            lq_files = list(output_lightmap_dir.glob("*.texture.ast"))
            dir_files = list(output_dir_dir.glob("*.texture.ast"))
            
            if len(lq_files) == 2 and len(dir_files) == 2:
                print("✅ 光照图文件夹处理成功")
                for file in lq_files + dir_files:
                    verify_texture_file(str(file))
            else:
                print(f"❌ 光照图文件夹处理失败: LQ={len(lq_files)}, Dir={len(dir_files)}")
                return False
            
            # 测试2: 自定义目录处理
            print("\n测试2: 自定义目录处理")
            custom_input_dir = temp_path / "custom_input"
            custom_output_dir = temp_path / "custom_output"
            custom_input_dir.mkdir()
            
            # 创建测试图像
            create_test_image(256, 256, custom_input_dir / "test_lightmap.png")
            
            generator.process_custom_lightmaps(
                str(custom_input_dir), 
                str(custom_output_dir), 
                "LQ"
            )
            
            # 检查输出文件
            custom_files = list(custom_output_dir.glob("*.texture.ast"))
            if len(custom_files) == 1:
                print("✅ 自定义目录处理成功")
                verify_texture_file(str(custom_files[0]))
            else:
                print(f"❌ 自定义目录处理失败: 期望1个文件, 实际{len(custom_files)}个")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ LightmapTextureGenerator测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """
    运行所有测试
    """
    print("开始运行贴图工具测试...")
    
    # 检查依赖
    try:
        import pymongo
        print("✅ pymongo依赖检查通过")
    except ImportError:
        print("❌ 缺少pymongo依赖，请运行: pip install pymongo")
        return False
    
    try:
        from PIL import Image
        print("✅ PIL依赖检查通过")
    except ImportError:
        print("❌ 缺少PIL依赖，请运行: pip install Pillow")
        return False
    
    # 运行测试
    test_results = []
    
    # 测试TextureHeaderWriter
    test_results.append(test_texture_header_writer())
    
    # 测试贴图文件头读取功能
    test_results.append(test_texture_header_reader())

    # 测试LightmapTextureGenerator
    test_results.append(test_lightmap_texture_generator())
    
    # 输出结果
    print("\n" + "="*50)
    print("测试结果汇总:")
    print("="*50)
    
    if all(test_results):
        print("✅ 所有测试通过!")
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 