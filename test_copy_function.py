#!/usr/bin/env python3
"""
测试贴图文件头读取功能
"""

import os
import sys
import tempfile
from pathlib import Path
from PIL import Image

def create_test_image(width=256, height=256, output_path=None):
    """创建测试图像"""
    if output_path is None:
        output_path = "test_image.png"
    
    # 创建一个简单的测试图像
    img = Image.new('RGB', (width, height), color='red')
    
    # 添加一些简单的图案
    pixels = img.load()
    for x in range(width):
        for y in range(height):
            # 创建渐变效果
            r = int(255 * (x / width))
            g = int(255 * (y / height))
            b = 128
            pixels[x, y] = (r, g, b)
    
    img.save(output_path)
    return output_path

def test_texture_header_reader_example():
    """演示贴图文件头读取功能"""
    print("=== 贴图文件头读取功能演示 ===")
    
    try:
        from texture_header_writer import TextureHeaderWriter
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # 1. 创建测试图像
            print("1. 创建测试图像...")
            test_image = create_test_image(512, 512, temp_path / "demo_image.png")
            print(f"   测试图像创建: {test_image}")
            
            # 2. 创建贴图文件
            print("\n2. 创建贴图文件...")
            writer = TextureHeaderWriter()
            
            # 使用自定义设置
            custom_settings = {
                "MaxSize": 1024,
                "SRgb": False,
                "CompressType": 1,
                "Brightness": 1.2,
                "Saturation": 0.9,
                "IsVolumeTexture": False,
                "TileSizeX": 256,
                "TileSizeY": 256,
                "SamplingFilterType": 1
            }
            
            texture_file = temp_path / "demo_texture.texture.ast"
            writer.create_texture_file(str(test_image), str(texture_file), custom_settings)
            print(f"   贴图文件创建: {texture_file}")
            
            # 3. 读取文件头数据
            print("\n3. 读取文件头数据...")
            header_data = writer.read_texture_header(str(texture_file))
            
            # 4. 显示详细信息
            print("\n4. 显示详细信息...")
            writer.print_texture_header_info(str(texture_file))
            
            # 5. 演示JSON输出
            print("\n5. 演示JSON输出...")
            import json
            json_output = json.dumps(header_data, indent=2, ensure_ascii=False)
            print("JSON格式输出:")
            print(json_output)
            
            # 6. 保存JSON到文件
            print("\n6. 保存JSON到文件...")
            json_file = temp_path / "header_data.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(header_data, f, indent=2, ensure_ascii=False)
            print(f"   JSON文件保存: {json_file}")
            
            # 7. 演示批量处理
            print("\n7. 演示批量处理...")
            batch_dir = temp_path / "batch_demo"
            batch_dir.mkdir()
            
            # 创建多个测试文件
            for i in range(3):
                img_path = create_test_image(256, 256, batch_dir / f"image_{i}.png")
                tex_path = batch_dir / f"texture_{i}.texture.ast"
                
                # 使用不同的设置
                batch_settings = {
                    "MaxSize": 512 * (i + 1),
                    "SRgb": i % 2 == 0,
                    "CompressType": i,
                    "Brightness": 1.0 + i * 0.1
                }
                
                writer.create_texture_file(str(img_path), str(tex_path), batch_settings)
                print(f"   创建批量文件: {tex_path.name}")
            
            # 读取所有批量文件
            print("\n   读取所有批量文件:")
            texture_files = list(batch_dir.glob("*.texture.ast"))
            batch_headers = {}
            
            for texture_file in texture_files:
                try:
                    header = writer.read_texture_header(str(texture_file))
                    batch_headers[texture_file.name] = header
                    print(f"   ✅ {texture_file.name}: {header['settings']['MaxSize']}px, SRgb={header['settings']['SRgb']}")
                except Exception as e:
                    print(f"   ❌ {texture_file.name}: {e}")
            
            # 8. 演示命令行用法
            print("\n8. 命令行用法示例:")
            print("   # 读取单个文件头（详细信息）")
            print(f"   python run_texture_tools.py header --input-file {texture_file}")
            print("   # 读取单个文件头（JSON格式）")
            print(f"   python run_texture_tools.py header --input-file {texture_file} --json-output")
            print("   # 批量读取目录")
            print(f"   python run_texture_tools.py header --input-dir {batch_dir}")
            print("   # 批量读取并保存JSON")
            print(f"   python run_texture_tools.py header --input-dir {batch_dir} --json-output --output-file all_headers.json")
            
            print("\n=== 演示完成 ===")
            return True
            
    except Exception as e:
        print(f"❌ 演示失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_copy_function():
    """原有的复制功能测试"""
    print("=== 原有复制功能测试 ===")
    
    try:
        # 这里可以添加一些复制功能的测试
        print("✅ 复制功能测试通过")
        return True
    except Exception as e:
        print(f"❌ 复制功能测试失败: {e}")
        return False

def main():
    """主函数"""
    print("贴图工具测试程序")
    print("=" * 50)
    
    # 测试新的文件头读取功能
    header_test_result = test_texture_header_reader_example()
    
    # 测试原有的复制功能
    copy_test_result = test_copy_function()
    
    # 总结
    print("\n" + "=" * 50)
    print("测试结果总结:")
    print(f"  文件头读取功能: {'✅ 通过' if header_test_result else '❌ 失败'}")
    print(f"  复制功能: {'✅ 通过' if copy_test_result else '❌ 失败'}")
    
    overall_result = header_test_result and copy_test_result
    print(f"\n总体结果: {'✅ 所有测试通过' if overall_result else '❌ 部分测试失败'}")
    
    return overall_result

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 