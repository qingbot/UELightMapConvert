#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
混合架构灯光贴图打包工具
负责处理场景内的静态物体，地形由Caculate_Landscape_Lightmap.py处理

Python负责:
- 读取和解析JSON数据
- 加载和提取灯光贴图
- 按参数分组
- 根据C++返回的最佳方案处理贴图
- 更新JSON数据并保存结果

C++ DLL负责:
- 高性能矩形装箱算法
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
import hashlib
import struct
from typing import Dict, List, Tuple, Any
import GlobalParameter
# 导入ReCode_Terrain_LQ中的地形处理函数
import ReCode_Terrain_LQ
# 从CPP目录导入C++ DLL包装类
sys.path.append(os.path.join(os.path.dirname(__file__), "CPP"))

from python_example import LightmapPackerPython, default_log_callback
from lightmap_structures import InputGroupData
from lightmap_structures import OutputGroupData


# 创建一个全局字典用于存储矩形ID映射
rectangle_id_map = {}
# 全局计数器用于生成顺序ID
rectangle_id_counter = 1

def generate_world_single_area_size(lod_distance):
    """根据lod_distance生成世界单个区域的尺寸"""
    
    # 计算每个LOD距离的加权值
    weighted_values = []
    for i, distance in enumerate(lod_distance):
        weight = 1.0 / (2 ** i)  # 第0位乘以1，第1位乘以0.5，第2位乘以0.25，以此类推
        weighted_values.append(distance * weight)
        
    return max(weighted_values) 

def generate_sequential_id(mesh_id, info=None):
    """生成简单的顺序ID，并维护映射用于后续查找
    
    Args:
        mesh_id: 物体ID/名称
        group_key: 组键值
        
    Returns:
        一个简单的整数ID
    """
    global rectangle_id_counter

    # 分配新ID
    new_id = rectangle_id_counter
    rectangle_id_counter += 1
    
    # 创建反向映射用于查找
    rectangle_id_map[new_id] = info
    
    return new_id

def get_mesh_id_by_rect_id(rect_id):
    """通过矩形ID查找对应的mesh_id
    
    Args:
        rect_id: 矩形ID
        
    Returns:
        对应的mesh_id，如果找不到则返回None
    """
    if rect_id in rectangle_id_map:
        info = rectangle_id_map[rect_id]
        return info["mesh_id"] if isinstance(info, dict) and "mesh_id" in info else None
    return None

def parse_grid_key(grid_key):
    """解析格子键为坐标
    
    Args:
        grid_key: 格子键，格式为 "grid_x_y"
        
    Returns:
        (grid_x, grid_y) 坐标元组，如果解析失败返回None
    """
    try:
        parts = grid_key.split('_')
        if len(parts) == 3 and parts[0] == 'grid':
            grid_x = int(parts[1])
            grid_y = int(parts[2])
            return (grid_x, grid_y)
    except ValueError:
        pass
    return None

def create_grid_key(grid_x, grid_y):
    """根据坐标创建格子键
    
    Args:
        grid_x: x坐标
        grid_y: y坐标
        
    Returns:
        格子键字符串
    """
    return f"grid_{grid_x}_{grid_y}"

def organize_grids_by_mip_levels(groups, max_mip_level):
    """按位置组织grid为不同mip级别的合并组
    
    Args:
        groups: 原始的grid组织结构 {grid_key: items}
        max_mip_level: 最大mip级别
        
    Returns:
        字典，包含每个mip级别的组织信息
        {
            0: {grid_key: {'grids': [grid_key], 'index': 0}},  # mip0保持原样
            1: {merge_key: {'grids': [grid_keys], 'index': merge_index}},  # mip1: 2x2合并
            2: {merge_key: {'grids': [grid_keys], 'index': merge_index}},  # mip2: 4x4合并
        }
    """
    mip_organizations = {}
    
    # 解析所有grid坐标
    grid_coords = {}
    for grid_key in groups.keys():
        coord = parse_grid_key(grid_key)
        if coord:
            grid_coords[grid_key] = coord
    
    if not grid_coords:
        print("警告: 没有找到有效的grid坐标")
        return mip_organizations
    
    # 计算边界
    all_x = [coord[0] for coord in grid_coords.values()]
    all_y = [coord[1] for coord in grid_coords.values()]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    print(f"Grid边界: x=[{min_x}, {max_x}], y=[{min_y}, {max_y}]")
    
    # mip0: 保持原样，每个grid独立
    mip_organizations[0] = {}
    index = 0
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            grid_key = create_grid_key(x, y)
            if grid_key in groups:
                mip_organizations[0][grid_key] = {
                    'grids': [grid_key],
                    'index': index
                }
                index += 1
    
    # 为每个mip级别创建合并组
    for mip_level in range(1, max_mip_level + 1):
        mip_organizations[mip_level] = {}
        merge_size = 2 ** mip_level  # mip1=2x2, mip2=4x4
        
        merge_index = 0
        
        # 从左下角开始，按merge_size的块遍历
        for base_y in range(min_y, max_y + 1, merge_size):
            for base_x in range(min_x, max_x + 1, merge_size):
                # 收集当前块内的所有grid
                grids_in_block = []
                for dy in range(merge_size):
                    for dx in range(merge_size):
                        grid_x = base_x + dx
                        grid_y = base_y + dy
                        grid_key = create_grid_key(grid_x, grid_y)
                        if grid_key in groups:
                            grids_in_block.append(grid_key)
                
                # 如果块内有任何grid，创建合并项
                if grids_in_block:
                    merge_key = f"mip{mip_level}_merge_{base_x}_{base_y}"
                    mip_organizations[mip_level][merge_key] = {
                        'grids': grids_in_block,
                        'index': merge_index,
                        'base_x': base_x,
                        'base_y': base_y,
                        'merge_size': merge_size
                    }
                    merge_index += 1
    
    # 打印组织结果
    for mip_level in range(max_mip_level + 1):
        count = len(mip_organizations[mip_level])
        if mip_level == 0:
            print(f"mip{mip_level}: {count} 个独立grid (输出: lightmap/packed_lightmap_X.png, dir/packed_lightmap_X_dir.png)")
        else:
            merge_size = 2 ** mip_level
            print(f"mip{mip_level}: {count} 个 {merge_size}x{merge_size} 合并块 (输出: lightmap/packed_lightmap_mip{mip_level}_Y.png, dir/packed_lightmap_mip{mip_level}_Y_dir.png)")
    
    return mip_organizations

def merge_grid_textures_for_mip(merge_info, grid_texture_paths, texture_size, is_dir=False):
    """合并多个grid的纹理为一个mip级别的大纹理
    
    Args:
        merge_info: 合并信息，包含'grids', 'base_x', 'base_y', 'merge_size'等
        grid_texture_paths: 每个grid的纹理路径字典 {grid_key: texture_path}
        texture_size: 单个纹理的尺寸
        is_dir: 是否是方向纹理
        
    Returns:
        合并后的纹理数组
    """
    grids = merge_info['grids']
    base_x = merge_info['base_x']
    base_y = merge_info['base_y']
    merge_size = merge_info['merge_size']
    
    # 创建合并后的纹理（与原始纹理一样大）
    merged_texture = np.zeros((texture_size, texture_size, 4), dtype=np.uint8)
    
    # 计算每个小纹理在合并纹理中的尺寸
    cell_size = texture_size // merge_size
    
    # 遍历合并块中的每个位置
    for dy in range(merge_size):
        for dx in range(merge_size):
            grid_x = base_x + dx
            grid_y = base_y + dy
            grid_key = create_grid_key(grid_x, grid_y)
            
            # 计算在合并纹理中的位置（从左下角开始）
            target_x = dx * cell_size
            target_y = (merge_size - 1 - dy) * cell_size  # 翻转Y坐标，因为从左下角开始
            
            if grid_key in grid_texture_paths:
                # 加载并缩放纹理
                texture_path = grid_texture_paths[grid_key]
                try:
                    img = Image.open(texture_path)
                    img = img.resize((cell_size, cell_size), Image.NEAREST)
                    texture_array = np.array(img)
                    
                    # 确保纹理有4个通道
                    if texture_array.shape[2] == 3:
                        # 如果是RGB，添加alpha通道
                        alpha = np.ones((texture_array.shape[0], texture_array.shape[1], 1), dtype=np.uint8) * 255
                        texture_array = np.concatenate([texture_array, alpha], axis=2)
                    
                    # 复制到合并纹理中
                    merged_texture[target_y:target_y+cell_size, target_x:target_x+cell_size] = texture_array
                    
                except Exception as e:
                    print(f"警告: 加载纹理 {texture_path} 时出错: {e}")
                    # 用黑色填充
                    merged_texture[target_y:target_y+cell_size, target_x:target_x+cell_size] = 0
            else:
                # 用黑色填充缺失的grid
                merged_texture[target_y:target_y+cell_size, target_x:target_x+cell_size] = 0
    
    return merged_texture

def create_and_save_merged_mip_textures(mip_organizations, groups, all_results, output_dir, texture_size, max_mip_level):
    """创建并保存合并的mip纹理
    
    Args:
        mip_organizations: 按mip级别组织的grid信息
        groups: 原始grid组织结构
        all_results: 所有的纹理结果
        output_dir: 输出目录
        texture_size: 纹理尺寸
        max_mip_level: 最大mip级别
        
    Returns:
        保存的文件路径列表
    """
    saved_paths = []
    
    # 创建lightmap和dir两个子文件夹
    lightmap_dir = os.path.join(output_dir, "lightmap")
    dir_dir = os.path.join(output_dir, "dir")
    os.makedirs(lightmap_dir, exist_ok=True)
    os.makedirs(dir_dir, exist_ok=True)
    
    # 创建grid到纹理路径的映射
    grid_texture_paths = {}
    for result in all_results:
        texture_index = result.texture_index
        
        # 查找该纹理对应的grid
        for grid_key, items in groups.items():
            if any(rectangle_id_map.get(rect.rectangle_id, {}).get("mesh_id") in 
                   [item["mesh_id"] for item in items] for rect in 
                   [result.rectangles[i] for i in range(result.rectangle_count)]):
                
                # 只为mip0创建路径映射，中间的单独mip级别不再保存
                # 使用新的文件夹结构：lightmap和dir分开存放
                lq_path = os.path.join(output_dir, "lightmap", f"packed_lightmap_{texture_index}.png")
                dir_path = os.path.join(output_dir, "dir", f"packed_lightmap_{texture_index}_dir.png")
                
                if 0 not in grid_texture_paths:
                    grid_texture_paths[0] = {}
                
                grid_texture_paths[0][grid_key] = {
                    'lq': lq_path,
                    'dir': dir_path
                }
                break
    
    # 为每个mip级别创建合并纹理
    for mip_level in range(1, max_mip_level + 1):  # 从mip1开始，mip0保持原样
        if mip_level not in mip_organizations:
            continue
            
        for merge_key, merge_info in mip_organizations[mip_level].items():
            merge_index = merge_info['index']
            
            # 创建LQ合并纹理（基于mip0的纹理）
            if 0 in grid_texture_paths:
                lq_merged = merge_grid_textures_for_mip(
                    merge_info, 
                    {grid_key: paths['lq'] for grid_key, paths in grid_texture_paths[0].items()},
                    texture_size, 
                    is_dir=False
                )
                
                # 保存LQ合并纹理到lightmap文件夹
                lq_output_path = os.path.join(lightmap_dir, f"packed_lightmap_mip{mip_level}_{merge_index}.png")
                Image.fromarray(lq_merged).save(lq_output_path)
                saved_paths.append(lq_output_path)
                print(f"已保存LQ合并纹理 mip{mip_level}: {lq_output_path}")
                
                # 创建Dir合并纹理（基于mip0的纹理）
                dir_merged = merge_grid_textures_for_mip(
                    merge_info, 
                    {grid_key: paths['dir'] for grid_key, paths in grid_texture_paths[0].items()},
                    texture_size, 
                    is_dir=True
                )
                
                # 保存Dir合并纹理到dir文件夹
                dir_output_path = os.path.join(dir_dir, f"packed_lightmap_mip{mip_level}_{merge_index}_dir.png")
                Image.fromarray(dir_merged).save(dir_output_path)
                saved_paths.append(dir_output_path)
                print(f"已保存Dir合并纹理 mip{mip_level}: {dir_output_path}")
    
    return saved_paths

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

    base_x = texture_size[0] * ( 0 + bias_scale[0] ) - 1
    base_y = texture_size[1] * ( 0 + bias_scale[1] ) * 0.5 - 1

    return padded_size_x, padded_size_y, base_x, base_y

def caculate_bias_scale(width,height,position_x,position_y,texture_size):
    """根据width,height,position_x,position_y,texture_size计算bias_scale"""
    bias_scale = [0,0,0,0]
    bias_scale[0] = (position_x + 1) / texture_size
    bias_scale[1] = (position_y + 1) / texture_size
    bias_scale[2] = (width-2) / texture_size
    bias_scale[3] = (height-2) / texture_size
    return bias_scale

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
    

def group_by_spatial_location(json_data, level_left_pos, level_right_pos, grid_size):
    """按世界空间位置分组物体"""
    groups = {}
    
    # 计算世界边界和格子数量
    world_min_x, world_min_y = level_left_pos
    world_max_x, world_max_y = level_right_pos
    
    # 计算格子数量
    grid_count_x = int(np.ceil((world_max_x - world_min_x) / grid_size))
    grid_count_y = int(np.ceil((world_max_y - world_min_y) / grid_size))
    
    print(f"世界边界: [{world_min_x}, {world_min_y}] 到 [{world_max_x}, {world_max_y}]")
    print(f"格子大小: {grid_size}, 格子数量: {grid_count_x} x {grid_count_y}")
    
    def get_grid_key(x, y):
        """根据世界坐标计算格子键"""
        grid_x = int((x - world_min_x) / grid_size)
        grid_y = int((y - world_min_y) / grid_size)
        # 确保在边界内
        grid_x = max(0, min(grid_x, grid_count_x - 1))
        grid_y = max(0, min(grid_y, grid_count_y - 1))
        return f"grid_{grid_x}_{grid_y}"
    
    # 检查是否存在"Static Mesh"键
    if "Static Mesh" in json_data:
        print("检测到'Static Mesh'格式的JSON...")
        static_mesh_data = json_data["Static Mesh"]
        
        # 遍历所有静态网格物体
        for mesh_id, mesh_data in static_mesh_data.items():
            # 获取物体位置
            location = mesh_data.get("Location", None)
            if not location or len(location) < 2:
                print(f"警告: 物体 {mesh_id} 没有有效的Location信息，跳过")
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
            
            # 根据位置计算格子键
            x, y = location[0], location[1]
            grid_key = get_grid_key(x, y)
            
            if grid_key not in groups:
                groups[grid_key] = []
            
            # 添加到对应格子
            groups[grid_key].append({
                "mesh_id": mesh_id,  # 物体ID
                "name": mesh_data.get("Name", mesh_id),  # 物体名称
                "location": location,  # 物体位置
                "lightmap_lq": lightmap_lq,  # 灯光贴图LQ路径
                "lightmap_hq": lightmap_hq,    # 灯光贴图HQ路径
                "bias_scale": bias_scale,      # BiasScale参数
                "grid_key": grid_key  # 格子键
            })
    # 如果是直接以物体名为键的格式，也做相同的处理
    elif is_direct_actor_format(json_data):
        # 类似的逻辑处理直接以物体名为键的格式
        print("检测到直接物体格式的JSON...")
        for actor_name, actor_data in json_data.items():
            # 跳过非字典类型的值
            if not isinstance(actor_data, dict):
                continue
                
            # 获取物体位置
            location = actor_data.get("Location", None)
            if not location or len(location) < 2:
                print(f"警告: 物体 {actor_name} 没有有效的Location信息，跳过")
                continue
            
            # 检查是否有Lightmap信息
            lightmap_info = actor_data.get("LightMap", {})
            if not lightmap_info:
                print(f"警告: 物体 {actor_name} 没有LightMap信息，跳过")
                continue
            
            # 获取Lightmap信息
            bias_scale = lightmap_info.get("BiasScale", [])
            lightmap_lq = lightmap_info.get("LQ", "")
            lightmap_hq = lightmap_info.get("HQ", "")
            
            # 如果没有必要的灯光贴图信息，则跳过
            if not bias_scale or len(bias_scale) < 4 or not lightmap_lq:
                print(f"警告: 物体 {actor_name} 的LightMap信息不完整，跳过")
                continue
            
            # 根据位置计算格子键
            x, y = location[0], location[1]
            grid_key = get_grid_key(x, y)
            
            if grid_key not in groups:
                groups[grid_key] = []
            
            # 添加到对应格子
            groups[grid_key].append({
                "mesh_id": actor_name,  # 使用物体名称作为ID
                "name": actor_data.get("Name", actor_name),  # 使用Name字段或默认为actor_name
                "location": location,  # 物体位置
                "lightmap_lq": lightmap_lq,  # 灯光贴图LQ路径
                "lightmap_hq": lightmap_hq,    # 灯光贴图HQ路径
                "bias_scale": bias_scale,      # BiasScale参数
                "grid_key": grid_key  # 格子键
            })
    
    # 打印分组结果统计
    total_items = sum(len(items) for items in groups.values())
    print(f"按空间位置分组完成: {len(groups)} 个格子, 共 {total_items} 个物体")
    for grid_key, items in groups.items():
        grid_info = grid_key.replace("grid_", "").split("_")
        grid_x, grid_y = int(grid_info[0]), int(grid_info[1])
        world_x = world_min_x + grid_x * grid_size
        world_y = world_min_y + grid_y * grid_size
        print(f"  - 格子 '{grid_key}' (世界坐标: [{world_x:.0f}, {world_y:.0f}]): {len(items)} 个物体")
    
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
                    # 添加Dir信息
                    if "new_dir" in info:
                        mesh_data["LightMap"]["Dir"] = info["new_dir"]
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
                    # 添加Dir信息
                    if "new_dir" in info:
                        actor_data["LightMap"]["Dir"] = info["new_dir"]
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
        "texture_count": len(results),
        "total_items": sum(result.rectangle_count for result in results),
        "textures": {}
    }
    
    # 按纹理索引组织数据
    for texture in results:
        texture_idx = texture.texture_index
        if str(texture_idx) not in output_data["textures"]:
            output_data["textures"][str(texture_idx)] = {
                "width": texture.texture_width,
                "height": texture.texture_height,
                "rectangle_count": texture.rectangle_count,
                "rectangles": []
            }
        
        # 获取该纹理中的所有矩形
        for i in range(texture.rectangle_count):
            rect = texture.rectangles[i]
            rect_id = rect.rectangle_id
            
            # 直接从ID映射中获取原始lightmap信息
            if rect_id not in rectangle_id_map:
                print(f"警告: 在保存JSON时找不到矩形ID {rect_id} 对应的lightmap信息")
                continue
                
            # 获取原始信息
            original_info = rectangle_id_map[rect_id]
            mesh_id = original_info["mesh_id"]
            
            # 寻找对应的组
            group_key = None
            for g_key, items in groups_data.items():
                for item in items:
                    if item["mesh_id"] == mesh_id:
                        group_key = g_key
                        break
                if group_key:
                    break
            
            # 添加到输出数据
            output_data["textures"][str(texture_idx)]["rectangles"].append({
                "mesh_id": mesh_id,
                "name": original_info.get("name", mesh_id),
                "position": [rect.position_x, rect.position_y],
                "width": rect.width,
                "height": rect.height,
                "rectangle_id": rect_id,
                "original_lightmap_lq": original_info.get("lightmap_lq", ""),
                "original_bias_scale": original_info.get("original_bias_scale", []),
                "group_key": group_key
            })
    
    # 保存到文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4)
    
    print(f"打包结果已保存到: {output_path}")
    return output_path

def process_and_save_single_packed_texture(texture_result, rectangles, texture_index, grid_key, output_dir, lightmap_base_dir, max_mip_level=0):
    """处理并保存单个格子的打包纹理，包括所有mip级别"""
    updated_lightmap_info = {}
    
    # 创建空白纹理 - 为每个mip级别创建LQ和Dir纹理
    texture_width = texture_result.texture_width
    texture_height = texture_result.texture_height
    
    # 为每个mip级别创建纹理数组
    mip_textures_lq = []  # LQ纹理的各个mip级别
    mip_textures_dir = [] # Dir纹理的各个mip级别
    
    for mip_level in range(max_mip_level + 1):
        # 计算当前mip级别的分辨率
        mip_width = max(1, texture_width >> mip_level)
        mip_height = max(1, texture_height >> mip_level)
        
        # 创建LQ纹理
        texture_array_lq = np.zeros((mip_height, mip_width, 4), dtype=np.uint8)
        mip_textures_lq.append(texture_array_lq)
        
        # 创建Dir纹理
        texture_array_dir = np.zeros((mip_height, mip_width, 4), dtype=np.uint8)
        mip_textures_dir.append(texture_array_dir)
    
    print(f"处理格子 '{grid_key}' 的纹理 {texture_index}，包含 {texture_result.rectangle_count} 个矩形，生成mip0纹理 (中间mip级别不再单独输出)")
    
    # 遍历该纹理中的所有矩形
    for i in range(texture_result.rectangle_count):
        rect = texture_result.rectangles[i]
        rect_id = rect.rectangle_id
        
        # 直接从ID映射中获取原始lightmap信息
        if rect_id not in rectangle_id_map:
            print(f"警告: 找不到矩形ID {rect_id} 对应的lightmap信息，跳过")
            continue
            
        # 获取原始的lightmap信息
        original_info = rectangle_id_map[rect_id]
        mesh_id = original_info["mesh_id"]
        lightmap_lq = original_info["lightmap_lq"]
        original_bias_scale = original_info["original_bias_scale"]
        
        # 处理每个mip级别
        for mip_level in range(max_mip_level + 1):
            # 构建mip级别的文件路径
            if mip_level == 0:
                # mip0就是原始文件，没有_Mip_0后缀，但需要确保有.png扩展名
                if lightmap_lq.lower().endswith(('.png', '.jpg', '.jpeg')):
                    mip_lightmap_name = lightmap_lq
                else:
                    mip_lightmap_name = f"{lightmap_lq}.png"
            else:
                # mip1, mip2, etc. 格式为：原始名_Mip_1.png
                if lightmap_lq.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # 如果已经有扩展名，在扩展名前插入mip后缀
                    name_without_ext = os.path.splitext(lightmap_lq)[0]
                    mip_lightmap_name = f"{name_without_ext}_Mip_{mip_level}.png"
                else:
                    # 如果没有扩展名，直接添加mip后缀和.png
                    mip_lightmap_name = f"{lightmap_lq}_Mip_{mip_level}.png"
            
            # 获取完整的灯光贴图路径
            if not os.path.isabs(mip_lightmap_name):
                full_lightmap_path = os.path.join(lightmap_base_dir, mip_lightmap_name)
            else:
                full_lightmap_path = mip_lightmap_name
            
            # 检查文件是否存在
            if not os.path.exists(full_lightmap_path):
                print(f"警告: mip级别 {mip_level} 的文件不存在: {full_lightmap_path}")
                continue
            
            try:
                # 加载原始图像
                img = Image.open(full_lightmap_path)
                img_array = np.array(img)
                img_height, img_width = img_array.shape[:2]
                
                # 从原始灯光贴图中提取区域
                # 使用get_lightmap_size_from_bias_scale计算实际位置和大小
                padded_size_x, padded_size_y, base_x, base_y = get_lightmap_size_from_bias_scale(
                    original_bias_scale, (img_width, img_height))
                
                # 计算像素坐标（上半部分 - LQ）
                x_min = int(base_x)
                y_min = int(base_y)
                x_max = int(x_min + padded_size_x)
                y_max = int(y_min + padded_size_y)
                
                # 边界检查（上半部分）
                x_min = max(0, min(x_min, img_width - 1))
                y_min = max(0, min(y_min, img_height - 1))
                x_max = max(x_min + 1, min(x_max, img_width))
                y_max = max(y_min + 1, min(y_max, img_height))
                
                # 提取上半部分区域（LQ）
                rect_region = img_array[y_min:y_max, x_min:x_max]
                
                # 计算下半部分坐标（Dir）- 与上半部分相对应，但y坐标偏移到下半部分
                y_min_dir = int(base_y + img_height / 2)  # 移动到下半部分
                y_max_dir = int(y_min_dir + padded_size_y)
                
                # 边界检查（下半部分）
                y_min_dir = max(0, min(y_min_dir, img_height - 1))
                y_max_dir = max(y_min_dir + 1, min(y_max_dir, img_height))
                
                # 提取下半部分区域（Dir）
                rect_region_dir = img_array[y_min_dir:y_max_dir, x_min:x_max]
                
                # 计算当前mip级别的目标大小
                mip_scale = 1.0 / (2 ** mip_level)
                target_width = max(1, int(rect.width * mip_scale))
                target_height = max(1, int(rect.height * mip_scale))
                
                # 缩放上半部分（LQ）
                if rect_region.shape[0] != target_height or rect_region.shape[1] != target_width:
                    # 使用PIL进行高质量缩放
                    resized_img = Image.fromarray(rect_region)
                    resized_img = resized_img.resize((target_width, target_height), Image.NEAREST)
                    rect_region = np.array(resized_img)
                
                # 缩放下半部分（Dir）
                if rect_region_dir.shape[0] != target_height or rect_region_dir.shape[1] != target_width:
                    # 使用PIL进行高质量缩放
                    resized_img_dir = Image.fromarray(rect_region_dir)
                    resized_img_dir = resized_img_dir.resize((target_width, target_height), Image.NEAREST)
                    rect_region_dir = np.array(resized_img_dir)
                
                # 获取在打包纹理中的位置（按mip级别缩放）
                target_x = max(0, int(rect.position_x * mip_scale))
                target_y = max(0, int(rect.position_y * mip_scale))
                
                # 获取当前mip级别的纹理数组
                current_mip_texture_lq = mip_textures_lq[mip_level]
                current_mip_texture_dir = mip_textures_dir[mip_level]
                
                # 确保不会超出边界
                try:
                    h, w = rect_region.shape[:2]
                    h_dir, w_dir = rect_region_dir.shape[:2]
                    
                    if target_x + w <= current_mip_texture_lq.shape[1] and target_y + h <= current_mip_texture_lq.shape[0]:
                        # 将上半部分区域复制到LQ纹理
                        current_mip_texture_lq[target_y:target_y+h, target_x:target_x+w] = rect_region
                        
                        # 将下半部分区域复制到Dir纹理
                        current_mip_texture_dir[target_y:target_y+h_dir, target_x:target_x+w_dir] = rect_region_dir
                        
                    else:
                        print(f"警告: 物体 {mesh_id} mip级别 {mip_level} 的灯光贴图区域 ({w}x{h}) "
                              f"在位置 ({target_x},{target_y}) 超出纹理边界 "
                              f"{current_mip_texture_lq.shape[1]}x{current_mip_texture_lq.shape[0]}")
                except Exception as e:
                    print(f"警告: 处理物体 {mesh_id} mip级别 {mip_level} 时出错: {e}")
                    print(traceback.format_exc())
            
            except Exception as e:
                print(f"警告: 处理 {mesh_id} mip级别 {mip_level} 的灯光贴图时出错: {e}")
                print(traceback.format_exc())
        
        # 处理完所有mip级别后更新lightmap信息（使用mip0的信息）
        # 计算新的BiasScale (基于打包纹理的UV坐标)
        new_bias_scale = caculate_bias_scale(rect.width, rect.height, rect.position_x, rect.position_y, texture_width)
        
        # 更新lightmap信息，增加Dir信息
        updated_lightmap_info[mesh_id] = {
            "mesh_id": mesh_id,
            "texture_index": texture_index,
            "new_lq": f"packed_lightmap_{texture_index}",
            "new_dir": f"packed_lightmap_{texture_index}_dir",  # 新增Dir信息
            "new_bias_scale": new_bias_scale,
            "scale_factor": 1.0  # 默认缩放因子
        }
    
    # 创建lightmap和dir两个子文件夹
    lightmap_dir = os.path.join(output_dir, "lightmap")
    dir_dir = os.path.join(output_dir, "dir")
    os.makedirs(lightmap_dir, exist_ok=True)
    os.makedirs(dir_dir, exist_ok=True)
    
    # 只保存mip0的打包纹理，跳过中间的单独mip级别
    # 保存LQ纹理 (mip0) 到lightmap文件夹
    output_path = os.path.join(lightmap_dir, f"packed_lightmap_{texture_index}.png")
    Image.fromarray(mip_textures_lq[0]).save(output_path)
    print(f"已保存LQ打包纹理 mip0: {output_path}")
    
    # 保存Dir纹理 (mip0) 到dir文件夹
    output_path_dir = os.path.join(dir_dir, f"packed_lightmap_{texture_index}_dir.png")
    Image.fromarray(mip_textures_dir[0]).save(output_path_dir)
    print(f"已保存Dir打包纹理 mip0: {output_path_dir}")
    
    # 中间的单独mip级别(mip1, mip2等)不再保存，只使用合并后的mip纹理
    
    return updated_lightmap_info

def process_and_save_packed_textures(results, group_rectangles, texture_size=4096, output_dir=None, lightmap_base_dir=None, max_mip_level=0):
    """根据C++返回的布局信息处理并保存打包后的纹理，更新BiasScale信息，包括所有mip级别"""
    if output_dir is None:
        output_dir = "packed_lightmaps"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 确保lightmap_base_dir存在
    if not lightmap_base_dir:
        lightmap_base_dir = "."
    
    # 创建空白纹理 - 为每个mip级别创建LQ和Dir纹理
    packed_textures_mip = []  # 存储所有mip级别的LQ纹理
    packed_textures_dir_mip = []  # 存储所有mip级别的Dir纹理
    
    for texture in results:
        # 为每个纹理创建所有mip级别
        texture_mip_levels = []
        texture_dir_mip_levels = []
        
        for mip_level in range(max_mip_level + 1):
            # 计算当前mip级别的分辨率
            mip_width = max(1, texture.texture_width >> mip_level)
            mip_height = max(1, texture.texture_height >> mip_level)
            
            # 创建LQ纹理
            texture_array = np.zeros((mip_height, mip_width, 4), dtype=np.uint8)
            texture_mip_levels.append({
                "texture_index": texture.texture_index,
                "mip_level": mip_level,
                "width": mip_width,
                "height": mip_height,
                "array": texture_array,
                "rectangles": []
            })
            
            # 创建Dir纹理
            texture_array_dir = np.zeros((mip_height, mip_width, 4), dtype=np.uint8)
            texture_dir_mip_levels.append({
                "texture_index": texture.texture_index,
                "mip_level": mip_level,
                "width": mip_width,
                "height": mip_height,
                "array": texture_array_dir,
                "rectangles": []
            })
        
        packed_textures_mip.append(texture_mip_levels)
        packed_textures_dir_mip.append(texture_dir_mip_levels)
    
    # 用于返回更新的lightmap信息
    updated_lightmap_info = {}
    
    # 处理每个纹理和其中的矩形
    for texture_idx, texture_mip_levels in enumerate(packed_textures_mip):
        texture = results[texture_idx]
        texture_dir_mip_levels = packed_textures_dir_mip[texture_idx]  # 获取对应的Dir纹理信息
        print(f"处理纹理 {texture.texture_index}，包含 {texture.rectangle_count} 个矩形，生成mip0纹理 (中间mip级别不再单独输出)")
        
        # 遍历该纹理中的所有矩形
        for i in range(texture.rectangle_count):
            rect = texture.rectangles[i]
            rect_id = rect.rectangle_id
            
            # 直接从ID映射中获取原始lightmap信息
            if rect_id not in rectangle_id_map:
                print(f"警告: 找不到矩形ID {rect_id} 对应的lightmap信息，跳过")
                continue
                
            # 获取原始的lightmap信息
            original_info = rectangle_id_map[rect_id]
            mesh_id = original_info["mesh_id"]
            lightmap_lq = original_info["lightmap_lq"]
            original_bias_scale = original_info["original_bias_scale"]
            
            # 处理每个mip级别
            for mip_level in range(max_mip_level + 1):
                # 构建mip级别的文件路径
                if mip_level == 0:
                    # mip0就是原始文件，没有_Mip_0后缀，但需要确保有.png扩展名
                    if lightmap_lq.lower().endswith(('.png', '.jpg', '.jpeg')):
                        mip_lightmap_name = lightmap_lq
                    else:
                        mip_lightmap_name = f"{lightmap_lq}.png"
                else:
                    # mip1, mip2, etc. 格式为：原始名_Mip_1.png
                    if lightmap_lq.lower().endswith(('.png', '.jpg', '.jpeg')):
                        # 如果已经有扩展名，在扩展名前插入mip后缀
                        name_without_ext = os.path.splitext(lightmap_lq)[0]
                        mip_lightmap_name = f"{name_without_ext}_Mip_{mip_level}.png"
                    else:
                        # 如果没有扩展名，直接添加mip后缀和.png
                        mip_lightmap_name = f"{lightmap_lq}_Mip_{mip_level}.png"
                
                # 获取完整的灯光贴图路径
                if not os.path.isabs(mip_lightmap_name):
                    full_lightmap_path = os.path.join(lightmap_base_dir, mip_lightmap_name)
                else:
                    full_lightmap_path = mip_lightmap_name
                
                # 检查文件是否存在
                if not os.path.exists(full_lightmap_path):
                    print(f"警告: mip级别 {mip_level} 的文件不存在: {full_lightmap_path}")
                    continue
            
                try:
                    # 加载原始图像
                    img = Image.open(full_lightmap_path)
                    img_array = np.array(img)
                    img_height, img_width = img_array.shape[:2]
                    
                    # 从原始灯光贴图中提取区域
                    # 使用get_lightmap_size_from_bias_scale计算实际位置和大小
                    padded_size_x, padded_size_y, base_x, base_y = get_lightmap_size_from_bias_scale(
                        original_bias_scale, (img_width, img_height))
                    
                    # 计算像素坐标（上半部分 - LQ）
                    x_min = int(base_x)
                    y_min = int(base_y)
                    x_max = int(x_min + padded_size_x)
                    y_max = int(y_min + padded_size_y)
                    
                    # 边界检查（上半部分）
                    x_min = max(0, min(x_min, img_width - 1))
                    y_min = max(0, min(y_min, img_height - 1))
                    x_max = max(x_min + 1, min(x_max, img_width))
                    y_max = max(y_min + 1, min(y_max, img_height))
                    
                    # 提取上半部分区域（LQ）
                    rect_region = img_array[y_min:y_max, x_min:x_max]
                    
                    # 计算下半部分坐标（Dir）- 与上半部分相对应，但y坐标偏移到下半部分
                    y_min_dir = int(base_y + img_height / 2)  # 移动到下半部分
                    y_max_dir = int(y_min_dir + padded_size_y)
                    
                    # 边界检查（下半部分）
                    y_min_dir = max(0, min(y_min_dir, img_height - 1))
                    y_max_dir = max(y_min_dir + 1, min(y_max_dir, img_height))
                    
                    # 提取下半部分区域（Dir）
                    rect_region_dir = img_array[y_min_dir:y_max_dir, x_min:x_max]
                    
                    # 计算当前mip级别的目标大小
                    mip_scale = 1.0 / (2 ** mip_level)
                    target_width = max(1, int(rect.width * mip_scale))
                    target_height = max(1, int(rect.height * mip_scale))
                    
                    # 缩放上半部分（LQ）
                    if rect_region.shape[0] != target_height or rect_region.shape[1] != target_width:
                        # 使用PIL进行高质量缩放
                        resized_img = Image.fromarray(rect_region)
                        resized_img = resized_img.resize((target_width, target_height), Image.NEAREST)
                        rect_region = np.array(resized_img)
                    
                    # 缩放下半部分（Dir）
                    if rect_region_dir.shape[0] != target_height or rect_region_dir.shape[1] != target_width:
                        # 使用PIL进行高质量缩放
                        resized_img_dir = Image.fromarray(rect_region_dir)
                        resized_img_dir = resized_img_dir.resize((target_width, target_height), Image.NEAREST)
                        rect_region_dir = np.array(resized_img_dir)
                    
                    # 获取在打包纹理中的位置（按mip级别缩放）
                    target_x = max(0, int(rect.position_x * mip_scale))
                    target_y = max(0, int(rect.position_y * mip_scale))
                    
                    # 获取当前mip级别的纹理信息
                    texture_info = texture_mip_levels[mip_level]
                    texture_dir_info = texture_dir_mip_levels[mip_level]
                    
                    # 确保不会超出边界
                    try:
                        h, w = rect_region.shape[:2]
                        h_dir, w_dir = rect_region_dir.shape[:2]
                        
                        if target_x + w <= texture_info["width"] and target_y + h <= texture_info["height"]:
                            # 将上半部分区域复制到LQ纹理
                            texture_info["array"][target_y:target_y+h, target_x:target_x+w] = rect_region
                            
                            # 将下半部分区域复制到Dir纹理
                            texture_dir_info["array"][target_y:target_y+h_dir, target_x:target_x+w_dir] = rect_region_dir
                            
                            # 记录矩形信息（LQ）
                            texture_info["rectangles"].append({
                                "mesh_id": mesh_id,
                                "position": (target_x, target_y),
                                "size": (w, h),
                                "rectangle_id": rect_id
                            })
                            
                            # 记录矩形信息（Dir）
                            texture_dir_info["rectangles"].append({
                                "mesh_id": mesh_id,
                                "position": (target_x, target_y),
                                "size": (w_dir, h_dir),
                                "rectangle_id": rect_id
                            })
                            
                        else:
                            print(f"警告: 物体 {mesh_id} mip级别 {mip_level} 的灯光贴图区域 ({w}x{h}) "
                                  f"在位置 ({target_x},{target_y}) 超出纹理边界 "
                                  f"{texture_info['width']}x{texture_info['height']}")
                    except Exception as e:
                        print(f"警告: 处理物体 {mesh_id} mip级别 {mip_level} 时出错: {e}")
                        print(traceback.format_exc())
                
                except Exception as e:
                    print(f"警告: 处理 {mesh_id} mip级别 {mip_level} 的灯光贴图时出错: {e}")
                    print(traceback.format_exc())
            
            # 处理完所有mip级别后更新lightmap信息（使用mip0的信息）
            # 计算新的BiasScale (基于打包纹理的UV坐标)
            texture_width = texture_mip_levels[0]["width"]
            texture_height = texture_mip_levels[0]["height"]
            new_bias_scale = caculate_bias_scale(rect.width, rect.height, rect.position_x, rect.position_y, texture_width)
            
            # 更新lightmap信息，增加Dir信息
            updated_lightmap_info[mesh_id] = {
                "mesh_id": mesh_id,
                "texture_index": texture.texture_index,
                "new_lq": f"packed_lightmap_{texture.texture_index}",
                "new_dir": f"packed_lightmap_{texture.texture_index}_dir",  # 新增Dir信息
                "new_bias_scale": new_bias_scale,
                "scale_factor": 1.0  # 默认缩放因子
            }
    
    # 创建lightmap和dir两个子文件夹
    lightmap_dir = os.path.join(output_dir, "lightmap")
    dir_dir = os.path.join(output_dir, "dir")
    os.makedirs(lightmap_dir, exist_ok=True)
    os.makedirs(dir_dir, exist_ok=True)
    
    # 只保存mip0的打包纹理，跳过中间的单独mip级别
    saved_paths = []
    for texture_idx, texture_mip_levels in enumerate(packed_textures_mip):
        texture_dir_mip_levels = packed_textures_dir_mip[texture_idx]
        
        # 只保存mip0级别
        texture_info = texture_mip_levels[0]
        texture_dir_info = texture_dir_mip_levels[0]
        
        # 保存LQ纹理 (mip0) 到lightmap文件夹
        output_path = os.path.join(lightmap_dir, f"packed_lightmap_{texture_info['texture_index']}.png")
        Image.fromarray(texture_info["array"]).save(output_path)
        saved_paths.append(output_path)
        print(f"已保存LQ打包纹理 mip0: {output_path}")
        
        # 保存Dir纹理 (mip0) 到dir文件夹
        output_path_dir = os.path.join(dir_dir, f"packed_lightmap_{texture_info['texture_index']}_dir.png")
        Image.fromarray(texture_dir_info["array"]).save(output_path_dir)
        saved_paths.append(output_path_dir)
        print(f"已保存Dir打包纹理 mip0: {output_path_dir}")
        
        # 中间的单独mip级别(mip1, mip2等)不再保存，只使用合并后的mip纹理
    
    return updated_lightmap_info

def process_terrain_lightmap(args, scene_data, json_data, source_json_path):
    """处理地形的灯光贴图
    
    Args:
        args: 命令行参数
        scene_data: 场景配置数据
        json_data: 要更新的JSON数据
        source_json_path: 用于处理的JSON文件路径
        
    Returns:
        (bool, dict): 处理结果(成功/失败)和更新后的JSON数据
    """
    print("\n=== 开始处理地形 ===")
    terrain_start_time = time.time()
    
    # 获取灯光贴图文件夹路径
    lightmap_base_dir = scene_data.get("source_lightmap_texture_path")
    
    print(f"使用JSON路径: {source_json_path}")
    print(f"使用灯光贴图文件夹: {lightmap_base_dir}")
    
    # 调用ReCode_Terrain_LQ中的地形处理函数，传入正确的JSON路径和灯光贴图文件夹路径
    terrain_result = ReCode_Terrain_LQ.process_terrain_lightmap(
        args.scene, 
        override_json_path=source_json_path,
        override_lightmap_folder=lightmap_base_dir
    )
    
    terrain_end_time = time.time()
    if terrain_result:
        print(f"地形处理完成，耗时: {terrain_end_time - terrain_start_time:.2f}秒")
        
        # 更新JSON中的地形数据
        try:
            print("更新JSON中的地形数据...")
            
            # 检查JSON中是否有Landscape部分
            if 'Landscape' in json_data:
                landscape_data = json_data['Landscape']
                if 'Landscape' in landscape_data:
                    landscape_data = landscape_data['Landscape']
                    
                    # 获取合并后的光照图名称和系数
                    combine_name = terrain_result["combine_name"]
                    lightmap_coef_scale = terrain_result["lightmap_coef_scale"]
                    lightmap_coef_add = terrain_result["lightmap_coef_add"]
                    direction_name = terrain_result["direction_name"]
                    direction_coef_scale = terrain_result["direction_coef_scale"]
                    direction_coef_add = terrain_result["direction_coef_add"]
                    
                    # 创建新的lightmapGroup，只保留一个项（0）
                    new_lightmap_group = {
                        'combine': combine_name,
                        '0': {
                            'LQ': combine_name,
                            'Dir': direction_name,  # 添加方向图引用
                            'BiasScale': [0, 0, 1, 1],  # 使用整个纹理
                            'CoefScale': [1, 1, 1, 1, 1, 1, 1, 1] + lightmap_coef_scale + direction_coef_scale,
                            'CoefAdd': [0, 0, 0, 0, 0, 0, 0, 0] + lightmap_coef_add + direction_coef_add
                        }
                    }
                        
                    # 更新JSON中的lightmapGroup
                    landscape_data['lightmapGroup'] = new_lightmap_group
                    print("已更新地形lightmapGroup，合并为单个项")
                    print(f"使用光照图: {combine_name}")
                    print(f"使用方向图: {direction_name}")
                else:
                    print("警告: 在JSON中未找到嵌套的Landscape项")
            else:
                print("警告: 在JSON中未找到Landscape项")
            
        except Exception as e:
            print(f"更新JSON中的地形数据时出错: {e}")
            print(traceback.format_exc())
            return False, json_data
    else:
        print(f"地形处理失败，耗时: {terrain_end_time - terrain_start_time:.2f}秒")
        return False, json_data
    
    print("=== 地形处理结束 ===\n")
    
    return True, json_data


def process_staticmesh_lightmap(args, scene_data, json_data, output_dir):
    """处理静态网格物体的灯光贴图
    
    Args:
        args: 命令行参数
        scene_data: 场景配置数据 
        json_data: 要更新的JSON数据
        output_dir: 输出目录
        
    Returns:
        (bool, dict): 处理结果(成功/失败)和更新后的JSON数据
    """
    try:
        lightmap_base_dir = scene_data.get("source_lightmap_texture_path")
        texture_size = scene_data.get("lightmap_texture_size", 2048)
        min_texture_size = scene_data.get("lightmap_texture_min_size", 16)
        level_left_pos = scene_data.get("level_left_pos", [-1024, -1024])
        level_right_pos = scene_data.get("level_right_pos", [1024, 1024])
        lod_distance = scene_data.get("lod_distance", [100, 200, 400, 800])
        max_mip_level = scene_data.get("max_mip_level", 0)
        
        total_start_time = time.time()
        
        # 步骤1: 使用传入的JSON数据
        step1_start_time = time.time()
        step1_time = time.time() - step1_start_time
        print(f"步骤1: 准备JSON数据完成，耗时: {step1_time:.2f}秒")
        
        # 步骤2: 按空间位置分组数据
        step2_start_time = time.time()
        
        # 计算格子大小
        grid_size = generate_world_single_area_size(lod_distance)
        print(f"根据lod_distance计算的格子大小: {grid_size}")
        
        global groups  # 使其成为全局变量，以便在其他函数中访问
        groups = group_by_spatial_location(json_data, level_left_pos, level_right_pos, grid_size)
        step2_time = time.time() - step2_start_time
        print(f"步骤2: 按空间位置分组完成，找到 {len(groups)} 个格子，耗时: {step2_time:.2f}秒")
        
        if len(groups) == 0:
            print("警告: 未找到有效的分组数据，请检查JSON格式")
            return False, json_data
        
        # 步骤2.5: 计算每个物体实际需要的lightmap大小
        # 遍历每个格子，计算实际的lightmap大小
        group_rectangles = {}
        
        for grid_key, items in groups.items():
            print(f"处理格子 '{grid_key}' 中的 {len(items)} 个物体...")
            group_rectangles[grid_key] = []
            
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
                    pixel_width = max(pixel_width, min_texture_size)
                    pixel_height = max(pixel_height, min_texture_size)
                    info = {
                        "mesh_id": mesh_id,
                        "name": item.get("name", mesh_id),
                        "lightmap_lq": lightmap_lq,
                        "original_bias_scale": bias_scale,  # 使用一致的字段名
                        "width": pixel_width,
                        "height": pixel_height,
                        "rectangle_id": 0, # generate_sequential_id(mesh_id, grid_key),
                    }
                    info["rectangle_id"] = generate_sequential_id(mesh_id, info)
                    # 添加到格子的矩形列表，增加rectangle_id字段
                    group_rectangles[grid_key].append(info)
                    
                except Exception as e:
                    print(f"警告: 处理 {mesh_id} 的灯光贴图时出错: {e}")
                    raise e
        
        print(f"已计算 {sum(len(rects) for rects in group_rectangles.values())} 个物体的lightmap大小")

        # 步骤3: 为每个格子创建独立的LightmapPacker并执行打包
        step3_start_time = time.time()
        
        # 创建BigMap目录在源灯光贴图文件夹内
        bigmap_dir = os.path.join(os.path.dirname(lightmap_base_dir), "BigMap")
        os.makedirs(bigmap_dir, exist_ok=True)
        print(f"创建大图保存目录: {bigmap_dir}")
        
        all_results = []
        updated_lightmap_info = {}
        
        for grid_key, rectangles in group_rectangles.items():
            if not rectangles:
                continue
                
            print(f"处理格子 '{grid_key}' 中的 {len(rectangles)} 个物体...")
            
            # 为每个格子创建独立的LightmapPacker实例
            try:
                packer = LightmapPackerPython(None)  # 使用默认DLL路径
                packer.set_log_callback(default_log_callback)
                packer.set_texture_size(texture_size)
                
                # 为每个物体创建一个单独的组
                for rectangle in rectangles:
                    mesh_id = rectangle["mesh_id"]
                    width = rectangle["width"]
                    height = rectangle["height"]
                    rectangle_id = rectangle["rectangle_id"]
                    
                    # 每个物体作为一个独立的组
                    cpp_input_group_data = InputGroupData(width, height, [rectangle_id])
                    if not packer.add_group(cpp_input_group_data):
                        print(f"警告: 添加物体 '{mesh_id}' 到C++失败")
                        continue
                
                # 使用pack_single_lightmap将格子内的所有物体打包到一张图中
                if not packer.pack_single_lightmap():
                    print(f"格子 '{grid_key}' 贴图打包失败")
                    continue
                
                results = packer.get_all_texture_results()
                if not results:
                    print(f"格子 '{grid_key}' 未获取到打包结果")
                    continue
                
                # 应该只有一个结果纹理
                texture_result = results[0]
                texture_index = len(all_results)  # 全局纹理索引
                texture_result.texture_index = texture_index
                all_results.append(texture_result)
                
                print(f"格子 '{grid_key}' 打包完成，生成纹理 {texture_index}，包含 {texture_result.rectangle_count} 个矩形")
                
                # 处理并保存该格子的打包纹理
                grid_updated_info = process_and_save_single_packed_texture(
                    texture_result,
                    rectangles,
                    texture_index,
                    grid_key,
                    bigmap_dir,
                    lightmap_base_dir,
                    max_mip_level
                )
                
                # 合并更新信息
                updated_lightmap_info.update(grid_updated_info)
                
            except Exception as e:
                print(f"处理格子 '{grid_key}' 时出错: {e}")
                print(traceback.format_exc())
                continue
        
        step3_time = time.time() - step3_start_time
        print(f"步骤3: 执行贴图打包完成，耗时: {step3_time:.2f}秒")
        
        # 步骤3.5: 创建按位置合并的mipmap（如果max_mip_level > 0）
        step3_5_start_time = time.time()
        if max_mip_level > 0:
            print(f"\n开始创建按位置合并的mipmap...")
            
            # 组织grid为不同的mip级别
            mip_organizations = organize_grids_by_mip_levels(groups, max_mip_level)
            
            # 创建并保存合并的mip纹理
            merged_paths = create_and_save_merged_mip_textures(
                mip_organizations, 
                groups, 
                all_results, 
                bigmap_dir, 
                texture_size, 
                max_mip_level
            )
            
            print(f"已创建 {len(merged_paths)} 个合并的mip纹理文件")
        else:
            print("跳过mipmap合并（max_mip_level = 0）")
        
        step3_5_time = time.time() - step3_5_start_time
        print(f"步骤3.5: 创建合并mipmap完成，耗时: {step3_5_time:.2f}秒")
        
        # 保存打包结果到JSON
        debug_output_path = os.path.join(output_dir, "packing_debug.json")
        save_packing_results_to_json(all_results, groups, debug_output_path)
         
        # 步骤4: 更新JSON数据
        step4_start_time = time.time()
        
        # 更新JSON数据 - 直接在传入的json_data上更新
        updated_json_data = update_json_data(json_data, updated_lightmap_info)
        
        step4_time = time.time() - step4_start_time
        print(f"步骤4: 更新JSON数据完成，耗时: {step4_time:.2f}秒")
        
        # 总结
        total_time = time.time() - total_start_time
        print("\n=== 处理静态网格物体完成 ===")
        print(f"总共处理了 {len(all_results)} 个格子纹理")
        print(f"总耗时: {total_time:.2f}秒")
        
        # 显示每个步骤占用的时间百分比
        print("\n时间分布:")
        print(f"- 准备JSON数据: {step1_time/total_time*100:.1f}%\t({step1_time:.2f}秒)")
        print(f"- 按空间分组: {step2_time/total_time*100:.1f}%\t({step2_time:.2f}秒)")
        print(f"- 执行贴图打包: {step3_time/total_time*100:.1f}%\t({step3_time:.2f}秒)")
        print(f"- 创建合并mipmap: {step3_5_time/total_time*100:.1f}%\t({step3_5_time:.2f}秒)")
        print(f"- 更新JSON数据: {step4_time/total_time*100:.1f}%\t({step4_time:.2f}秒)")
        
        print(f"新的光照图文件保存在: {bigmap_dir}")
        print(f"  - LQ纹理保存在: {os.path.join(bigmap_dir, 'lightmap')}")
        print(f"  - Dir纹理保存在: {os.path.join(bigmap_dir, 'dir')}")
        
        return True, updated_json_data
        
    except Exception as e:
        print(f"处理静态网格物体时出错: {e}")
        print(traceback.format_exc())
        return False, json_data


def create_backup_file(json_path, backup_dir, backup_filename=None):
    """创建备份文件的通用函数
    
    Args:
        json_path: 原始JSON文件路径
        backup_dir: 备份目录
        backup_filename: 自定义备份文件名，如果为None则使用原始文件名
        
    Returns:
        备份文件路径，如果失败则返回None
    """
    try:
        if not os.path.exists(json_path):
            print(f"错误: 原始JSON文件不存在: {json_path}")
            return None
        
        # 确定备份文件名
        if backup_filename:
            # 如果指定了自定义文件名，使用该文件名
            backup_json_path = os.path.join(backup_dir, backup_filename)
            print(f"使用自定义备份文件名: {backup_filename}")
        else:
            # 使用原始文件名
            json_filename = os.path.basename(json_path)
            backup_json_path = os.path.join(backup_dir, json_filename)
            print(f"使用默认备份文件名: {json_filename}")
        
        print(f"创建备份文件: {backup_json_path}")
        import shutil
        shutil.copy2(json_path, backup_json_path)
        print("✓ 备份创建成功")
        return backup_json_path
    except Exception as e:
        print(f"创建备份时出错: {e}")
        return None

def go_main(parser):
    args = parser.parse_args()
    
    # 检查参数冲突
    if args.use_backup and args.create_backup:
        print("错误: --use-backup 和 --create-backup 参数不能同时使用")
        print("  --use-backup: 从备份文件读取JSON（可指定备份文件名）")
        print("  --create-backup: 创建原始JSON文件的备份（可指定备份文件名）")
        print("请选择其中一个参数使用")
        return
    

    
    # 从GlobalParameter获取场景相关参数
    scene_data = GlobalParameter.ALL_LIGHT_MAP_DATA.get(args.scene, {})
    if not scene_data:
        print(f"错误: 找不到场景 '{args.scene}' 的配置数据")
        return
    
    # 获取各项参数
    json_path = scene_data.get("source_lightmap_json_path")
    lightmap_base_dir = scene_data.get("source_lightmap_texture_path")
    texture_size = scene_data.get("lightmap_texture_size")
    min_texture_size = scene_data.get("lightmap_texture_min_size")

    # 创建JSON备份文件夹
    json_dir = os.path.dirname(json_path)
    backup_dir = os.path.join(json_dir, "backup")
    os.makedirs(backup_dir, exist_ok=True)

    # 备份或从备份读取JSON
    json_filename = os.path.basename(json_path)
    backup_json_path = os.path.join(backup_dir, json_filename)

    # 如果需要创建备份，先创建备份
    if args.create_backup:
        # 确定备份文件名
        if args.create_backup is True:
            backup_filename = None  # 使用默认文件名
            print(f"创建默认备份文件")
        else:
            backup_filename = args.create_backup  # 使用指定文件名
            print(f"创建指定备份文件: {backup_filename}")
        
        backup_result = create_backup_file(json_path, backup_dir, backup_filename)
        if backup_result is None:
            return
        # 如果指定了自定义文件名，更新backup_json_path
        if backup_filename:
            backup_json_path = backup_result
        print(f"场景 '{args.scene}' 的备份已完成")
        print("提示: 后续处理可以使用 --use-backup 参数从备份恢复")

    # 确定实际使用的JSON路径
    if args.use_backup:
        # 确定备份文件路径
        if args.use_backup is True:
            # 如果只有 --use-backup 没有参数，使用默认备份文件名
            actual_backup_path = backup_json_path
            print(f"使用默认备份文件: {os.path.basename(actual_backup_path)}")
        else:
            # 如果指定了备份文件名，使用指定的文件名
            actual_backup_path = os.path.join(backup_dir, args.use_backup)
            print(f"使用指定备份文件: {args.use_backup}")
        
        # 检查备份文件是否存在
        if os.path.exists(actual_backup_path):
            print(f"从备份读取JSON: {actual_backup_path}")
            source_json_path = actual_backup_path
        else:
            print(f"错误: 指定的备份文件不存在: {actual_backup_path}")
            print(f"请检查备份文件是否正确，或使用 --create-backup 创建备份")
            return
    else:
        # 使用原始路径
        source_json_path = json_path

    # 检查是否指定了处理选项
    if not args.process_terrain and not args.process_staticmesh:
        # 如果没有处理选项，但有create-backup，说明只是要创建备份
        if args.create_backup:
            print("仅创建备份完成，未进行资产处理")
            return
        else:
            print("\n错误: 未指定任何处理选项")
            print("请使用以下选项之一：")
            print("  --process-terrain     处理地形的灯光贴图")
            print("  --process-staticmesh  处理静态网格物体的灯光贴图")
            print("  --create-backup       只创建JSON备份文件（可指定备份文件名）")
            print("  --use-backup          从备份文件读取JSON（可指定备份文件名）")
            return

    # 如果需要进行处理操作，检查备份文件是否存在，如果不存在则自动创建
    if (args.process_terrain or args.process_staticmesh) and not args.use_backup:
        # 检查备份文件是否存在
        if not os.path.exists(backup_json_path):
            print(f"⚠️  检测到没有备份文件，正在自动创建备份...")
            backup_result = create_backup_file(json_path, backup_dir)
            if backup_result is None:
                print("❌ 无法创建备份文件，为了安全起见，停止处理")
                return
            print("✓ 自动备份创建成功")
            print("提示: 后续处理可以使用 --use-backup 参数从备份恢复")
        else:
            print(f"✓ 发现已存在备份文件: {backup_json_path}")

    print(f"场景: {args.scene}")
    print(f"JSON路径: {source_json_path}")
    print(f"灯光贴图路径: {lightmap_base_dir}")
    print(f"纹理大小: {texture_size}")
    print(f"最小纹理大小: {min_texture_size}")
    
    # 获取max_mip_level并显示mip级别信息
    max_mip_level = scene_data.get("max_mip_level", 0)
    print(f"Mip级别: {max_mip_level + 1} 级 (mip0 到 mip{max_mip_level})")
    if max_mip_level > 0:
        print("  源文件命名规则:")
        print("    mip0: 原始文件名.png (如: lightmap_123.png)")
        for level in range(1, max_mip_level + 1):
            print(f"    mip{level}: 原始文件名_Mip_{level}.png (如: lightmap_123_Mip_{level}.png)")
        print("  输出文件命名:")
        print("  文件夹结构:")
        print("    lightmap/ - 存放所有LQ纹理")
        print("    dir/ - 存放所有Dir纹理")
        print("  文件命名:")
        print(f"    mip0: lightmap/packed_lightmap_X.png, dir/packed_lightmap_X_dir.png (原始分辨率，每个格子独立)")
        for level in range(1, max_mip_level + 1):
            merge_size = 2 ** level
            print(f"    mip{level}: lightmap/packed_lightmap_mip{level}_Y.png, dir/packed_lightmap_mip{level}_Y_dir.png (合并{merge_size}x{merge_size}格子)")
        print("  注：中间的单独mip级别不再输出，只输出mip0和合并后的mip纹理")
    else:
        print("  仅生成单个分辨率的大图 (mip0)")

    # 设置输出路径
    output_dir = os.path.join("./output/lightmaps", args.scene)
    os.makedirs(output_dir, exist_ok=True)

    # 加载初始JSON数据
    json_data = load_json_data(source_json_path)
    modified = False

    # 处理地形lightmap（如果启用）
    if args.process_terrain:
        terrain_success, json_data = process_terrain_lightmap(args, scene_data, json_data, source_json_path)
        modified = modified or terrain_success

    # 处理静态网格物体（如果启用）
    if args.process_staticmesh:
        staticmesh_success, json_data = process_staticmesh_lightmap(args, scene_data, json_data, output_dir)
        modified = modified or staticmesh_success

    # 如果有任何更改，保存JSON
    if modified:
        print(f"\n保存最终的JSON文件到: {json_path}")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4)

def main():
    parser = argparse.ArgumentParser(description="混合架构灯光贴图打包工具")
    parser.add_argument("--scene", type=str, default=GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME,
                        help="场景名称，默认为basic_level")
    parser.add_argument("--process-terrain", action="store_true",
                        help="处理地形的灯光贴图")
    parser.add_argument("--process-staticmesh", action="store_true",
                        help="处理场景中静态网格物体的灯光贴图")
    parser.add_argument("--use-backup", nargs='?', const=True, default=False,
                        help="从备份文件夹读取JSON，而不是从原始位置读取。可指定备份文件名，如果不指定则使用默认备份")
    parser.add_argument("--create-backup", nargs='?', const=True, default=False,
                        help="创建原始JSON文件的备份（可以与处理选项组合使用）。可指定备份文件名，如果不指定则使用原始文件名")

    go_main(parser) 

if __name__ == "__main__":
    main() 
    
    