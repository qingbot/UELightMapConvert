#!/usr/bin/env python3
"""
Chaos引擎贴图工具运行脚本
"""

import os
import sys
import argparse
from pathlib import Path

def check_dependencies():
    """检查必要的依赖"""
    missing_deps = []
    
    try:
        import pymongo
    except ImportError:
        missing_deps.append("pymongo")
    
    try:
        from PIL import Image
    except ImportError:
        missing_deps.append("Pillow")
    
    if missing_deps:
        print(f"❌ 缺少以下依赖: {', '.join(missing_deps)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    return True

def run_texture_header_writer(args):
    """运行TextureHeaderWriter"""
    try:
        from texture_header_writer import TextureHeaderWriter
        
        writer = TextureHeaderWriter()
        
        if args.batch_mode:
            # 批量模式
            if not args.input_dir or not args.output_dir:
                print("批量模式需要指定 --input-dir 和 --output-dir")
                return False
            
            print(f"批量转换贴图...")
            print(f"源目录: {args.input_dir}")
            print(f"输出目录: {args.output_dir}")
            
            writer.batch_convert_textures(args.input_dir, args.output_dir)
            
        else:
            # 单文件模式
            if not args.input_file or not args.output_file:
                print("单文件模式需要指定 --input-file 和 --output-file")
                return False
            
            print(f"转换单个贴图...")
            print(f"源文件: {args.input_file}")
            print(f"输出文件: {args.output_file}")
            
            # 准备自定义设置
            custom_settings = {}
            if args.max_size:
                custom_settings["MaxSize"] = args.max_size
            if args.compress_type is not None:
                custom_settings["CompressType"] = args.compress_type
            if args.no_srgb:
                custom_settings["SRgb"] = False
            
            writer.create_texture_file(args.input_file, args.output_file, custom_settings)
        
        print("✅ TextureHeaderWriter完成")
        return True
        
    except Exception as e:
        print(f"❌ TextureHeaderWriter失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_lightmap_texture_generator(args):
    """运行LightmapTextureGenerator"""
    try:
        from lightmap_texture_generator import LightmapTextureGenerator
        
        generator = LightmapTextureGenerator()
        
        if args.custom_mode:
            # 自定义模式
            if not args.input_dir or not args.output_dir:
                print("自定义模式需要指定 --input-dir 和 --output-dir")
                return False
            
            print(f"处理自定义光照图目录...")
            print(f"源目录: {args.input_dir}")
            print(f"输出目录: {args.output_dir}")
            print(f"纹理类型: {args.texture_type}")
            
            generator.process_custom_lightmaps(
                args.input_dir, 
                args.output_dir, 
                args.texture_type
            )
            
        else:
            # 场景模式
            if not args.scene:
                print("场景模式需要指定 --scene")
                return False
            
            print(f"处理场景光照图...")
            print(f"场景: {args.scene}")
            
            generator.process_scene_lightmaps(args.scene)
        
        print("✅ LightmapTextureGenerator完成")
        return True
        
    except Exception as e:
        print(f"❌ LightmapTextureGenerator失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_tests():
    """运行测试"""
    try:
        from test_texture_tools import run_all_tests
        return run_all_tests()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Chaos引擎贴图工具")
    
    # 添加子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # TextureHeaderWriter子命令
    thw_parser = subparsers.add_parser('texture', help='通用贴图转换')
    thw_parser.add_argument('--input-file', '-i', help='输入文件')
    thw_parser.add_argument('--output-file', '-o', help='输出文件')
    thw_parser.add_argument('--input-dir', help='输入目录（批量模式）')
    thw_parser.add_argument('--output-dir', help='输出目录（批量模式）')
    thw_parser.add_argument('--batch-mode', '-b', action='store_true', help='批量模式')
    thw_parser.add_argument('--max-size', type=int, help='最大尺寸')
    thw_parser.add_argument('--compress-type', type=int, help='压缩类型')
    thw_parser.add_argument('--no-srgb', action='store_true', help='不使用sRGB')
    
    # LightmapTextureGenerator子命令
    ltg_parser = subparsers.add_parser('lightmap', help='光照图贴图生成')
    ltg_parser.add_argument('--scene', '-s', help='场景名称')
    ltg_parser.add_argument('--input-dir', help='输入目录（自定义模式）')
    ltg_parser.add_argument('--output-dir', help='输出目录（自定义模式）')
    ltg_parser.add_argument('--texture-type', choices=['LQ', 'Dir'], default='LQ', help='纹理类型')
    ltg_parser.add_argument('--custom-mode', action='store_true', help='自定义模式')
    
    # 测试子命令
    test_parser = subparsers.add_parser('test', help='运行测试')
    
    args = parser.parse_args()
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 运行相应的命令
    if args.command == 'texture':
        success = run_texture_header_writer(args)
    elif args.command == 'lightmap':
        success = run_lightmap_texture_generator(args)
    elif args.command == 'test':
        success = run_tests()
    else:
        # 显示帮助
        parser.print_help()
        return 0
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 