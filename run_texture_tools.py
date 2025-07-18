#!/usr/bin/env python3
"""
Chaos引擎贴图工具运行脚本
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
import GlobalParameter

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
        print("运行贴图工具测试...")
        from test_texture_tools import run_all_tests
        basic_tests_result = run_all_tests()
        
        print("\n运行复制功能测试...")
        from test_copy_function import test_copy_function
        copy_tests_result = test_copy_function()
        
        overall_result = basic_tests_result and copy_tests_result
        
        if overall_result:
            print("\n✅ 所有测试通过!")
        else:
            print("\n❌ 部分测试失败!")
            
        return overall_result
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_texture_header_reader(args):
    """运行贴图文件头读取器"""
    try:
        from texture_header_writer import TextureHeaderWriter
        
        writer = TextureHeaderWriter()
        
        if args.input_file:
            # 读取单个文件
            print(f"读取贴图文件头: {args.input_file}")
            
            if args.json_output:
                # 输出JSON格式
                import json
                header_data = writer.read_texture_header(args.input_file)
                
                # 格式化输出
                if args.output_file:
                    with open(args.output_file, 'w', encoding='utf-8') as f:
                        json.dump(header_data, f, indent=2, ensure_ascii=False)
                    print(f"JSON数据已保存到: {args.output_file}")
                else:
                    print(json.dumps(header_data, indent=2, ensure_ascii=False))
            else:
                # 输出详细信息
                writer.print_texture_header_info(args.input_file)
                
        elif args.input_dir:
            # 批量读取目录中的所有.texture.ast文件
            from pathlib import Path
            
            input_path = Path(args.input_dir)
            if not input_path.exists():
                print(f"❌ 输入目录不存在: {args.input_dir}")
                return False
            
            # 查找所有.texture.ast文件
            texture_files = list(input_path.rglob("*.texture.ast"))
            if not texture_files:
                print(f"❌ 在目录中未找到任何.texture.ast文件: {args.input_dir}")
                return False
            
            print(f"找到 {len(texture_files)} 个贴图文件")
            
            if args.json_output:
                # 批量输出JSON格式
                import json
                all_headers = {}
                
                for texture_file in texture_files:
                    try:
                        header_data = writer.read_texture_header(str(texture_file))
                        relative_path = texture_file.relative_to(input_path)
                        all_headers[str(relative_path)] = header_data
                        print(f"✅ 已读取: {relative_path}")
                    except Exception as e:
                        print(f"❌ 读取失败: {texture_file} - {e}")
                
                # 保存或输出结果
                if args.output_file:
                    with open(args.output_file, 'w', encoding='utf-8') as f:
                        json.dump(all_headers, f, indent=2, ensure_ascii=False)
                    print(f"批量JSON数据已保存到: {args.output_file}")
                else:
                    print(json.dumps(all_headers, indent=2, ensure_ascii=False))
            else:
                # 批量输出详细信息
                for i, texture_file in enumerate(texture_files, 1):
                    try:
                        print(f"\n{'='*60}")
                        print(f"文件 {i}/{len(texture_files)}")
                        writer.print_texture_header_info(str(texture_file))
                    except Exception as e:
                        print(f"❌ 读取失败: {texture_file} - {e}")
        else:
            print("请指定 --input-file 或 --input-dir")
            return False
        
        print("✅ 贴图文件头读取完成")
        return True
        
    except Exception as e:
        print(f"❌ 贴图文件头读取失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def copy_lightmap_textures_to_chaos(scene_name):
    """
    将hybrid_lightmap_packer_nsh.py的输出复制到Chaos引擎目录
    
    Args:
        scene_name: 场景名称
        
    Returns:
        bool: 成功返回True，失败返回False
    """
    try:
        print(f"\n=== 复制光照图贴图到Chaos引擎 ===")
        print(f"场景: {scene_name}")
        
        # 检查场景是否存在
        if scene_name not in GlobalParameter.ALL_LIGHT_MAP_DATA:
            print(f"❌ 场景 '{scene_name}' 不存在")
            print(f"可用场景: {', '.join(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())}")
            return False
        
        # 获取场景配置
        scene_config = GlobalParameter.ALL_LIGHT_MAP_DATA[scene_name]
        
        # 获取路径信息
        source_lightmap_path = scene_config.get("source_lightmap_texture_path")
        target_lightmap_path = scene_config.get("lightmap_absolute_path")
        
        if not source_lightmap_path or not target_lightmap_path:
            print("❌ 缺少必要的路径配置")
            return False
        
        print(f"源路径: {source_lightmap_path}")
        print(f"目标路径: {target_lightmap_path}")
        
        # 构建BigMap路径
        bigmap_dir = Path(source_lightmap_path).parent / "BigMap"
        
        if not bigmap_dir.exists():
            print(f"❌ BigMap目录不存在: {bigmap_dir}")
            return False
        
        print(f"BigMap目录: {bigmap_dir}")
        
        # 确保目标目录存在
        target_path = Path(target_lightmap_path)
        target_path.mkdir(parents=True, exist_ok=True)
        
        # 导入贴图工具
        from texture_header_writer import TextureHeaderWriter
        writer = TextureHeaderWriter()
        
        # 获取光照图参数
        lightmap_settings = GlobalParameter.LightMapTextureParameter.copy()
        
        # 生成计数器
        generated_count = 0
        
        # 处理BigMap/lightmap文件夹中的所有图片
        lightmap_source_dir = bigmap_dir / "lightmap"
        if lightmap_source_dir.exists():
            print(f"\n处理lightmap文件夹: {lightmap_source_dir}")
            target_lightmap_dir = target_path / "lightmap"
            target_lightmap_dir.mkdir(parents=True, exist_ok=True)
            
            for png_file in lightmap_source_dir.glob("*.png"):
                # 直接基于源PNG文件生成.texture.ast文件，不复制PNG
                target_ast = target_lightmap_dir / f"{png_file.stem}.texture.ast"
                writer.create_texture_file(
                    str(png_file),
                    str(target_ast),
                    lightmap_settings
                )
                generated_count += 1
                print(f"  生成: {target_ast.name}")
        
        # 处理BigMap/dir文件夹中的所有图片
        dir_source_dir = bigmap_dir / "dir"
        if dir_source_dir.exists():
            print(f"\n处理dir文件夹: {dir_source_dir}")
            target_dir_dir = target_path / "dir"
            target_dir_dir.mkdir(parents=True, exist_ok=True)
            
            for png_file in dir_source_dir.glob("*.png"):
                # 直接基于源PNG文件生成.texture.ast文件，不复制PNG
                target_ast = target_dir_dir / f"{png_file.stem}.texture.ast"
                writer.create_texture_file(
                    str(png_file),
                    str(target_ast),
                    lightmap_settings
                )
                generated_count += 1
                print(f"  生成: {target_ast.name}")
        
        # 处理BigMap根目录下的Landscape_combine_lightmap.png
        landscape_file = bigmap_dir / "Landscape_combine_lightmap.png"
        if landscape_file.exists():
            print(f"\n处理地形文件: {landscape_file}")
            
            # 直接基于源PNG文件生成.texture.ast文件，不复制PNG
            target_landscape_ast = target_path / f"{landscape_file.stem}.texture.ast"
            writer.create_texture_file(
                str(landscape_file),
                str(target_landscape_ast),
                lightmap_settings
            )
            generated_count += 1
            print(f"  生成: {target_landscape_ast.name}")
        
        # 处理BigMap根目录下的Landscape_combine_lightmap_dir.png（如果存在）
        landscape_dir_file = bigmap_dir / "Landscape_combine_lightmap_dir.png"
        if landscape_dir_file.exists():
            print(f"\n处理地形方向文件: {landscape_dir_file}")
            
            # 直接基于源PNG文件生成.texture.ast文件，不复制PNG
            target_landscape_dir_ast = target_path / f"{landscape_dir_file.stem}.texture.ast"
            writer.create_texture_file(
                str(landscape_dir_file),
                str(target_landscape_dir_ast),
                lightmap_settings
            )
            generated_count += 1
            print(f"  生成: {target_landscape_dir_ast.name}")
        
        print(f"\n✅ 处理完成!")
        print(f"  共生成了 {generated_count} 个.texture.ast文件")
        print(f"  目标目录: {target_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ 复制光照图贴图失败: {e}")
        import traceback
        traceback.print_exc()
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
    
    # 复制光照图贴图子命令
    copy_parser = subparsers.add_parser('copy', help='复制光照图贴图到Chaos引擎')
    copy_parser.add_argument('--scene', '-s', required=True, help='场景名称')
    
    # 贴图文件头读取器子命令
    header_parser = subparsers.add_parser('header', help='读取贴图文件头')
    header_parser.add_argument('--input-file', '-i', help='输入文件')
    header_parser.add_argument('--input-dir', help='输入目录（批量模式）')
    header_parser.add_argument('--json-output', action='store_true', help='输出JSON格式')
    header_parser.add_argument('--output-file', '-o', help='输出文件')
    
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
    elif args.command == 'copy':
        success = copy_lightmap_textures_to_chaos(args.scene)
    elif args.command == 'header':
        success = run_texture_header_reader(args)
    else:
        # 显示帮助
        parser.print_help()
        return 0
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main()) 