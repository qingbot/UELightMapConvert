#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
混合架构灯光贴图打包工具

Python负责:
- 读取和解析JSON数据
- 加载和提取灯光贴图
- 按参数分组
- 根据C++返回的最佳方案处理贴图
- 更新JSON数据并保存结果

C++ DLL负责:
- 高性能矩形装箱算法
- 模拟退火优化
- 多线程并行计算
"""

import os
import json
import time
import argparse
import numpy as np
from PIL import Image
import ctypes
from datetime import datetime
from pathlib import Path
import sys
import traceback
from typing import Dict, List, Tuple, Any
import GlobalParameter
# 从CPP目录导入C++ DLL包装类
sys.path.append(os.path.join(os.path.dirname(__file__), "CPP"))

from python_example import LightmapPackerPython, default_log_callback
from lightmap_structures import InputGroupData
from lightmap_structures import OutputGroupData


# 从ReCode_LQ.py提取的关键类和函数
def get_new_json_path():
    """使用时间戳创建新的文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"current_scene_data_source_{timestamp}.json"

def load_json_data(json_path):
    """加载JSON数据"""
    print(f"加载JSON数据: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_lightmap_path(scene_name):
    """获取场景的灯光贴图路径"""
    return GlobalParameter.ALL_LIGHT_MAP_DATA[scene_name]["source_lightmap_json_path"]

def get_lightmap_size_from_bias_scale(bias_scale,texture_size):
    """根据bias_scale计算灯光贴图的尺寸"""
    # 原始数组在计算BiasScale时，为了linear采样，将biasscale向内收缩了，所以需要向外扩展
    # 计算的C++代码如下
    # if ((PaddedSizeX - 2 > 0) && ((PaddedSizeY - 2) > 0))
    # {
    # 	PaddedSizeX -= 2;
    # 	PaddedSizeY -= 2;
    # 	BaseX += 1;
    # 	BaseY += 1;
    # }
    # FVector2D Scale((float)PaddedSizeX / (float)GetSizeX(), (float)PaddedSizeY / (float)GetSizeY());
    # FVector2D Bias((float)BaseX / (float)GetSizeX(), (float)BaseY / (float)GetSizeY());
    
    # 图片的下半部分是其他数据，上半部分才是我需要的物体，所以需要裁剪
    padded_size_x = texture_size[0] * bias_scale[2] + 2
    padded_size_y = texture_size[1] * bias_scale[3] * 0.5 + 2

    base_x = texture_size[0] * ( 0 + bias_scale[0] ) + 1
    base_y = texture_size[1] * ( 0 + bias_scale[1] ) * 0.5 + 1

    return padded_size_x, padded_size_y, base_x, base_y
    
    
    

def extract_lightmap(lightmap_path, bias_scale):
    """根据bias_scale提取灯光贴图"""
    if not os.path.exists(lightmap_path):
        print(f"警告: 找不到灯光贴图: {lightmap_path}")
        # 返回一个占位图像
        return np.zeros((64, 64, 4), dtype=np.uint8)
    
    try:
        img = Image.open(lightmap_path)
        img_array = np.array(img)
        
        # 如果bias_scale为空或无效，返回整个图像
        if not bias_scale or len(bias_scale) < 4:
            return img_array
        
        u_min, v_min, width, height = bias_scale
        img_height, img_width = img_array.shape[:2]
        
        padded_size_x, padded_size_y, base_x, base_y = get_lightmap_size_from_bias_scale(bias_scale,  img_array.shape[:2])

        x_min = int(base_x )
        y_min = int(base_y )
        x_max = int((base_x + padded_size_x))
        y_max = int((base_y + padded_size_y))
        # 边界检查
        x_min = max(0, min(x_min, img_width - 1))
        y_min = max(0, min(y_min, img_height - 1))
        x_max = max(x_min + 1, min(x_max, img_width))
        y_max = max(y_min + 1, min(y_max, img_height))
        
        return img_array[y_min:y_max, x_min:x_max]
    except Exception as e:
        print(f"提取灯光贴图时出错: {lightmap_path}, 错误: {e}")
        return np.zeros((64, 64, 4), dtype=np.uint8)
    

def group_by_parameters(json_data):
    """按模型URL参数分组物体"""
    groups = {}
    
    # 检查是否存在"Static Mesh"键
    if "Static Mesh" in json_data:
        print("检测到'Static Mesh'格式的JSON...")
        static_mesh_data = json_data["Static Mesh"]
        
        # 遍历所有静态网格物体
        for mesh_id, mesh_data in static_mesh_data.items():
            # 检查物体是否有Parameters
            parameters = mesh_data.get("Parameters", {})
            if not parameters:
                continue
                
            # 获取mesh URL信息
            mesh_json_url = parameters.get("MeshJsonURL", "")
            mesh_data_url = parameters.get("MeshDataURL", "")
            
            if not mesh_json_url or not mesh_data_url:
                continue
            
            # 检查是否有LightMap信息
            lightmap_info = mesh_data.get("LightMap", {})
            if not lightmap_info:
                print(f"警告: 物体 {mesh_id} 没有LightMap信息，跳过")
                continue
            
            # 获取Lightmap信息
            bias_scale = lightmap_info.get("BiasScale", [])
            lightmap_lq = lightmap_info.get("LQ", "")
            lightmap_hq = lightmap_info.get("HQ", "")
            
            # 如果没有必要的灯光贴图信息，则跳过
            if not bias_scale or len(bias_scale) < 4 or not lightmap_lq:
                print(f"警告: 物体 {mesh_id} 的LightMap信息不完整，跳过")
                continue
            
            # 创建分组键 (使用mesh URL作为键)
            group_key = f"{mesh_json_url}|{mesh_data_url}"
            
            if group_key not in groups:
                groups[group_key] = []
            
            # 添加到分组
            groups[group_key].append({
                "mesh_id": mesh_id,  # 物体ID
                "name": mesh_data.get("Name", mesh_id),  # 物体名称
                "lightmap_lq": lightmap_lq,  # 灯光贴图LQ路径
                "lightmap_hq": lightmap_hq,    # 灯光贴图HQ路径
                "bias_scale": bias_scale,      # BiasScale参数
                "mesh_json_url": mesh_json_url, # 保存原始URL信息
                "mesh_data_url": mesh_data_url
            })
    # 如果是直接以物体名为键的格式
    elif is_direct_actor_format(json_data):
        print("检测到直接物体格式的JSON...")
        for actor_name, actor_data in json_data.items():
            # 跳过非字典类型的值
            if not isinstance(actor_data, dict):
                continue
                
            # 检查物体是否有Parameters和Lightmap
            parameters = actor_data.get("Parameters", {})
            lightmap_info = actor_data.get("LightMap", {})
            
            # 如果没有Parameters或Lightmap信息，则跳过
            if not parameters or not lightmap_info:
                continue
            
            # 获取mesh URL信息
            mesh_json_url = parameters.get("MeshJsonURL", "")
            mesh_data_url = parameters.get("MeshDataURL", "")
            
            if not mesh_json_url or not mesh_data_url:
                continue
            
            # 创建分组键 (使用mesh URL作为键)
            group_key = f"{mesh_json_url}|{mesh_data_url}"
            
            # 获取Lightmap信息
            bias_scale = lightmap_info.get("BiasScale", [])
            lightmap_lq = lightmap_info.get("LQ", "")
            lightmap_hq = lightmap_info.get("HQ", "")
            
            # 如果没有必要的灯光贴图信息，则跳过
            if not bias_scale or len(bias_scale) < 4 or not lightmap_lq:
                continue
            
            if group_key not in groups:
                groups[group_key] = []
            
            # 添加到分组
            groups[group_key].append({
                "mesh_id": actor_name,  # 使用物体名称作为ID
                "name": actor_data.get("Name", actor_name),  # 使用Name字段或默认为actor_name
                "lightmap_lq": lightmap_lq,  # 灯光贴图LQ路径
                "lightmap_hq": lightmap_hq,    # 灯光贴图HQ路径
                "bias_scale": bias_scale,      # BiasScale参数
                "mesh_json_url": mesh_json_url, # 保存原始URL信息
                "mesh_data_url": mesh_data_url
            })
    
    # 打印分组结果统计
    total_items = sum(len(items) for items in groups.values())
    print(f"按模型URL参数分组完成: {len(groups)} 个组, 共 {total_items} 个物体")
    for group_key, items in groups.items():
        model_name = group_key.split("/")[-1].split(".")[0] if "/" in group_key else group_key
        print(f"  - 组 '{model_name}': {len(items)} 个物体")
    
    return groups

def is_direct_actor_format(json_data):
    """判断是否是直接以物体名为键的JSON格式"""
    return (
        isinstance(json_data, dict) and 
        "actors" not in json_data and
        "Static Mesh" not in json_data and
        "world_mesh_renderers" not in json_data and
        any("Parameters" in value for value in json_data.values() if isinstance(value, dict))
    )

def update_json_data(json_data, new_lightmap_info):
    """更新JSON数据中的灯光贴图信息"""
    texture_indices = {}
    
    # 先统计每个纹理的使用次数
    for mesh_id, info in new_lightmap_info.items():
        texture_index = info.get("texture_index", 0)
        if texture_index not in texture_indices:
            texture_indices[texture_index] = 0
        texture_indices[texture_index] += 1
    
    print(f"更新JSON数据，涉及 {len(texture_indices)} 个纹理")
    
    updated_count = 0
    
    # 检查是否存在"Static Mesh"键
    if "Static Mesh" in json_data:
        print("更新'Static Mesh'格式的JSON...")
        static_mesh_data = json_data["Static Mesh"]
        
        # 遍历所有静态网格物体
        for mesh_id, mesh_data in static_mesh_data.items():
            if mesh_id in new_lightmap_info:
                info = new_lightmap_info[mesh_id]
                
                # 如果存在LightMap字段
                if "LightMap" in mesh_data:
                    # 更新灯光贴图路径
                    mesh_data["LightMap"]["LQ"] = info["new_lq"]
                    # 更新BiasScale
                    mesh_data["LightMap"]["BiasScale"] = info["new_bias_scale"]
                    updated_count += 1
                else:
                    print(f"警告: 物体 {mesh_id} 没有LightMap字段，无法更新")
    # 如果是直接以物体名为键的格式
    elif is_direct_actor_format(json_data):
        # 处理直接以物体名为键的JSON格式
        print("更新直接物体格式的JSON...")
        for actor_name, actor_data in json_data.items():
            if not isinstance(actor_data, dict):
                continue
                
            if actor_name in new_lightmap_info:
                info = new_lightmap_info[actor_name]
                
                # 如果存在LightMap字段
                if "LightMap" in actor_data:
                    # 更新灯光贴图路径
                    actor_data["LightMap"]["LQ"] = info["new_lq"]
                    # 更新BiasScale
                    actor_data["LightMap"]["BiasScale"] = info["new_bias_scale"]
                    updated_count += 1
    
    print(f"已更新 {updated_count} 个物体的灯光贴图信息")
    return json_data

def save_packing_results_to_json(results, groups_data, output_path=None):
    """保存打包结果到JSON文件，方便调试和可视化"""
    if output_path is None:
        output_path = f"packing_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    output_data = {
        "texture_count": len(set(r["texture_index"] for r in results)),
        "total_items": len(results),
        "textures": {}
    }
    
    # 按纹理索引组织数据
    for result in results:
        texture_idx = result["texture_index"]
        if str(texture_idx) not in output_data["textures"]:
            output_data["textures"][str(texture_idx)] = []
        
        # 获取组信息
        group_info = None
        for group in groups_data:
            for item in groups_data[group]:
                if item["mesh_id"] == result["mesh_id"]:
                    group_info = {
                        "group": group,
                        "original_bias_scale": item["bias_scale"],
                        "original_lightmap_lq": item["lightmap_lq"],
                        "original_lightmap_hq": item["lightmap_hq"]
                    }
                    break
            if group_info:
                break
        
        # 添加到输出数据
        output_data["textures"][str(texture_idx)].append({
            "mesh_id": result["mesh_id"],
            "name": result["name"],
            "new_lightmap": result["new_lq"],
            "new_bias_scale": result["new_bias_scale"],
            "scale_factor": result["scale_factor"],
            "position": list(result["position"]),
            "size": list(result["size"]),
            "group_info": group_info
        })
    
    # 保存到文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)
    
    print(f"打包结果已保存到: {output_path}")
    return output_path

def process_and_save_packed_textures(results, group_rectangles, texture_size=4096, output_dir=None, lightmap_base_dir=None):
    """根据C++返回的布局信息处理并保存打包后的纹理"""
    if output_dir is None:
        output_dir = "packed_lightmaps"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 确定需要创建的纹理数量
    texture_count = max([r["texture_index"] for r in results], default=0) + 1
    
    # 创建空白纹理
    packed_textures = []
    for _ in range(texture_count):
        # 创建RGBA纹理，初始为全透明
        texture = np.zeros((texture_size, texture_size, 4), dtype=np.uint8)
        packed_textures.append(texture)
    
    # 按纹理索引对结果分组
    results_by_texture = {}
    for r in results:
        texture_idx = r["texture_index"]
        if texture_idx not in results_by_texture:
            results_by_texture[texture_idx] = []
        results_by_texture[texture_idx].append(r)
    
    # 处理每个纹理
    for texture_idx, items in results_by_texture.items():
        print(f"处理纹理 {texture_idx}，包含 {len(items)} 个项目")
        
        for item in items:
            mesh_id = item["mesh_id"]
            
            # 查找原始灯光贴图信息
            original_info = None
            
            # 在所有组中查找该物体的信息
            for group_key, rectangles in group_rectangles.items():
                for rect in rectangles:
                    if rect["mesh_id"] == mesh_id:
                        original_info = rect
                        break
                if original_info:
                    break
            
            if not original_info:
                print(f"警告: 找不到物体 {mesh_id} 的原始信息，跳过")
                continue
            
            # 获取原始灯光贴图路径
            lightmap_lq = original_info["lightmap_lq"]
            
            # 获取完整的灯光贴图路径
            if not os.path.isabs(lightmap_lq):
                full_lightmap_path = os.path.join(lightmap_base_dir, lightmap_lq)
            else:
                full_lightmap_path = lightmap_lq
            
            print(f"处理物体 {mesh_id} 的灯光贴图: {full_lightmap_path}")
            
            # 获取原始的bias_scale
            original_bias_scale = original_info["original_bias_scale"]
            
            try:
                # 加载原始图像
                img = Image.open(full_lightmap_path)
                img_array = np.array(img)
                img_height, img_width = img_array.shape[:2]
                
                # 提取原始灯光贴图的区域
                # 计算UV区域，注意y坐标和高度需要乘以0.5
                u_min, v_min, width, height = original_bias_scale
                
                # 应用0.5缩放到v坐标和高度
                v_min = v_min * 0.5
                height = height * 0.5
                
                # 计算像素坐标
                x_min = int(u_min * img_width)
                y_min = int(v_min * img_height)
                x_max = int((u_min + width) * img_width)
                y_max = int((v_min + height) * img_height)
                
                # 边界检查
                x_min = max(0, min(x_min, img_width - 1))
                y_min = max(0, min(y_min, img_height - 1))
                x_max = max(x_min + 1, min(x_max, img_width))
                y_max = max(y_min + 1, min(y_max, img_height))
                
                # 提取区域
                rect_region = img_array[y_min:y_max, x_min:x_max]
                
                # 应用缩放（如果需要）
                scale_factor = item.get("scale_factor", 1.0)
                if scale_factor != 1.0:
                    new_height = int(rect_region.shape[0] * scale_factor)
                    new_width = int(rect_region.shape[1] * scale_factor)
                    
                    if new_height > 0 and new_width > 0:
                        # 使用PIL进行更高质量的缩放
                        resized_img = Image.fromarray(rect_region)
                        resized_img = resized_img.resize((new_width, new_height), Image.LANCZOS)
                        rect_region = np.array(resized_img)
                    else:
                        print(f"警告: 缩放因子 {scale_factor} 导致尺寸无效，跳过缩放")
                
                # 获取在打包纹理中的位置
                target_x, target_y = item["position"]
                
                # 确保不会超出边界
                try:
                    h, w = rect_region.shape[:2]
                    
                    if target_x + w <= texture_size and target_y + h <= texture_size:
                        # 将提取的区域复制到目标纹理
                        packed_textures[texture_idx][target_y:target_y+h, target_x:target_x+w] = rect_region
                    else:
                        print(f"警告: 物体 {mesh_id} 的灯光贴图区域 ({w}x{h}) 在位置 ({target_x},{target_y}) 超出纹理边界 {texture_size}x{texture_size}")
                except Exception as e:
                    print(f"警告: 处理物体 {mesh_id} 时出错: {e}")
            
            except Exception as e:
                print(f"警告: 处理 {mesh_id} 的灯光贴图时出错: {e}")
    
    # 保存打包后的纹理
    saved_paths = []
    for i, texture in enumerate(packed_textures):
        output_path = os.path.join(output_dir, f"packed_lightmap_{i}.png")
        Image.fromarray(texture).save(output_path)
        saved_paths.append(output_path)
        print(f"已保存打包纹理: {output_path}")
    
    return saved_paths

def main():
    parser = argparse.ArgumentParser(description="混合架构灯光贴图打包工具")
    parser.add_argument("--json", type=str, default=None, 
                        help="JSON文件路径")
    parser.add_argument("--lightmap", type=str, default="./light/light_map",
                        help="灯光贴图目录路径")
    parser.add_argument("--output", type=str, default=None,
                        help="输出目录路径，默认为./output/lightmaps")
    # parser.add_argument("--algorithm", type=str, choices=["simulated_annealing", "traditional"],
    #                     default="simulated_annealing", help="打包算法")
    parser.add_argument("--texture-size", type=int, default=4096,
                        help="输出纹理大小，默认为4096")
    parser.add_argument("--min-texture-size", type=int, default=32,
                        help="最小纹理大小，默认为32")
    parser.add_argument("--dll", type=str, default=None,
                        help="LightmapPacker.dll路径，如果不指定则自动搜索")
    
    parser.add_argument("--scene", type=str, default=GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME,
                        help="场景名称，默认为basic_level")
    
    args = parser.parse_args()
    
    # 根据场景名称获取JSON路径（如果未指定）
    if args.json is None:
        try:
            args.json = get_lightmap_path(args.scene)
            print(f"根据场景名称'{args.scene}'获取JSON路径: {args.json}")
        except Exception as e:
            print(f"无法根据场景名称获取JSON路径: {e}")
            print("请指定--json参数")
            return
    
    # 设置输出路径
    if args.output is None:
        args.output = os.path.join("./output/lightmaps", args.scene)
    
    # 确保输出目录存在
    os.makedirs(args.output, exist_ok=True)
    
    # 获取新的JSON路径
    new_json_path = os.path.join(args.output, get_new_json_path())
    
    try:
        total_start_time = time.time()
        
        # 步骤1: 加载JSON数据
        step1_start_time = time.time()
        json_data = load_json_data(args.json)
        step1_time = time.time() - step1_start_time
        print(f"步骤1: 加载JSON数据完成，耗时: {step1_time:.2f}秒")
        
        # 步骤2: 按组整理数据
        step2_start_time = time.time()
        global groups  # 使其成为全局变量，以便在其他函数中访问
        groups = group_by_parameters(json_data)
        step2_time = time.time() - step2_start_time
        print(f"步骤2: 按组整理数据完成，找到 {len(groups)} 个组，耗时: {step2_time:.2f}秒")
        
        if len(groups) == 0:
            print("警告: 未找到有效的分组数据，请检查JSON格式")
            return
        
        # 步骤2.5: 计算每个物体实际需要的lightmap大小
        # print("步骤2.5: 计算每个物体的lightmap实际大小...")
        # 获取灯光贴图基础路径
        lightmap_base_dir = args.lightmap
        if args.scene in GlobalParameter.ALL_LIGHT_MAP_DATA:
            texture_base_path = GlobalParameter.ALL_LIGHT_MAP_DATA[args.scene].get(
                "source_lightmap_texture_path", lightmap_base_dir)
            if texture_base_path:
                lightmap_base_dir = texture_base_path
        
        print(f"灯光贴图基础路径: {lightmap_base_dir}")
        
        # 遍历每个组，计算实际的lightmap大小
        group_rectangles = {}
        
        for group_key, items in groups.items():
            print(f"处理组 '{group_key}' 中的 {len(items)} 个物体...")
            group_rectangles[group_key] = []
            
            for item in items:
                mesh_id = item["mesh_id"]
                lightmap_lq = item["lightmap_lq"]
                bias_scale = item["bias_scale"]
                
                # 构建完整的贴图路径
                if not os.path.isabs(lightmap_lq):
                    full_lightmap_path = os.path.join(lightmap_base_dir, lightmap_lq + ".png")
                else:
                    full_lightmap_path = lightmap_lq
                
                # 加载贴图获取尺寸
                try:
                    img = Image.open(full_lightmap_path)
                    img_width, img_height = img.size
                    
                    # 计算实际的UV区域，y坐标和高度需要考虑只使用上半部分
                    # u_min, v_min, width, height = bias_scale
                    
                    padded_size_x, padded_size_y, base_x, base_y = get_lightmap_size_from_bias_scale(bias_scale, img.size)
                    # 注意：贴图只使用上半部分，所以v坐标和高度都需要乘以0.5
                    
                    # 计算宽高
                    pixel_width = int(padded_size_x)
                    pixel_height = int(padded_size_y)
                    
                    # 确保最小尺寸
                    pixel_width = max(pixel_width, args.min_texture_size)
                    pixel_height = max(pixel_height, args.min_texture_size)
                    
                    # 添加到组的矩形列表，增加rectangle_id字段
                    group_rectangles[group_key].append({
                        "mesh_id": mesh_id,
                        "name": item.get("name", mesh_id),
                        "lightmap_lq": lightmap_lq,
                        "original_bias_scale": bias_scale,
                        "width": pixel_width,
                        "height": pixel_height,
                        "rectangle_id": int(hash(mesh_id)),  # 为每个矩形添加ID
                    })
                    
                except Exception as e:
                    print(f"警告: 处理 {mesh_id} 的灯光贴图时出错: {e}")
                    raise e
                    # # 使用默认值
                    # group_rectangles[group_key].append({
                    #     "mesh_id": mesh_id,
                    #     "name": item.get("name", mesh_id),
                    #     "lightmap_lq": lightmap_lq,
                    #     # "lightmap_hq": item.get("lightmap_hq", ""),
                    #     "original_bias_scale": bias_scale,
                    #     "width": args.min_texture_size,
                    #     "height": args.min_texture_size,
                    #     "rectangle_id": hash(mesh_id),
                    # })
        
        print(f"已计算 {sum(len(rects) for rects in group_rectangles.values())} 个物体的lightmap大小")

        # 步骤3: 加载C++ DLL并执行贴图打包
        step3_start_time = time.time()
        
        # 初始化C++ DLL
        try:
            packer = LightmapPackerPython(args.dll)
            print("成功加载LightmapPacker DLL")
        except Exception as e:
            print(f"加载LightmapPacker DLL失败: {e}")
            return
        
        packer.set_log_callback(default_log_callback)
        
        # 设置DLL参数
        packer.set_texture_size(args.texture_size)
        
        # 向C++传递组和矩形信息
        print(f"向C++传递 {len(group_rectangles)} 个组的矩形信息...")

        for group_key, rectangles in group_rectangles.items():
            if not rectangles:
                continue
            # 创建一个列表来存储矩形ID
            rectangle_ids = [rectangle["rectangle_id"] for rectangle in rectangles]
            print(f"添加组 '{group_key}' 到C++，矩形ID: {rectangle_ids}")
            cpp_input_group_data = InputGroupData(rectangles[0]["width"], rectangles[0]["height"], rectangle_ids)
            if not packer.add_group(cpp_input_group_data):
                print(f"警告: 添加组 '{group_key}' 到C++失败")
        
        if not packer.pack_lightmaps():
            print("贴图打包失败")
            return
        
        print("test over")
        return
        # 获取结果
        texture_count = packer.get_texture_count()
        packing_efficiency = packer.get_packing_efficiency()
        print(f"贴图打包成功！生成了 {texture_count} 个纹理")
        print(f"打包效率: {packing_efficiency * 100:.2f}%")
        
        # 获取所有打包结果
        results = packer.get_all_results()
        print(f"获取到 {len(results)} 个打包结果")
        
        step3_time = time.time() - step3_start_time
        print(f"步骤3: 执行贴图打包完成，耗时: {step3_time:.2f}秒")
        
        # 保存打包结果到JSON
        debug_output_path = os.path.join(args.output, "packing_debug.json")
        save_packing_results_to_json(results, groups, debug_output_path)
        
        # 步骤4: 处理并保存打包纹理
        step4_start_time = time.time()
        packed_textures = process_and_save_packed_textures(
            results, 
            group_rectangles,
            texture_size=args.texture_size, 
            output_dir=args.output,
            lightmap_base_dir=lightmap_base_dir
        )
        step4_time = time.time() - step4_start_time
        print(f"步骤4: 处理并保存打包纹理完成，耗时: {step4_time:.2f}秒")
        
        # 步骤5: 更新JSON数据
        step5_start_time = time.time()
        
        # 将结果转换为更新JSON所需的格式
        new_lightmap_info = {}
        for result in results:
            new_lightmap_info[result["mesh_id"]] = {
                "texture_index": result["texture_index"],
                "new_lq": result["new_lq"],
                "new_bias_scale": result["new_bias_scale"],
                "scale_factor": result.get("scale_factor", 1.0)
            }
        
        # 更新JSON数据
        updated_json_data = update_json_data(json_data, new_lightmap_info)
        
        # 保存更新后的JSON
        with open(new_json_path, 'w', encoding='utf-8') as f:
            json.dump(updated_json_data, f, indent=4)
        
        step5_time = time.time() - step5_start_time
        print(f"步骤5: 更新JSON数据完成，耗时: {step5_time:.2f}秒")
        
        # 总结
        total_time = time.time() - total_start_time
        print("\n=== 处理完成 ===")
        print(f"总共处理了 {len(results)} 个对象")
        print(f"生成了 {texture_count} 个打包贴图")
        print(f"总耗时: {total_time:.2f}秒")
        
        # 显示每个步骤占用的时间百分比
        print("\n时间分布:")
        print(f"- 加载JSON数据: {step1_time/total_time*100:.1f}%")
        print(f"- 按组整理数据: {step2_time/total_time*100:.1f}%")
        print(f"- 执行贴图打包: {step3_time/total_time*100:.1f}%")
        print(f"- 生成新贴图: {step4_time/total_time*100:.1f}%")
        print(f"- 更新JSON数据: {step5_time/total_time*100:.1f}%")
        
        print(f"\n新的JSON文件已保存为: {new_json_path}")
        print(f"新的光照图文件保存在: {args.output}")
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 