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

def process_and_save_single_packed_texture(texture_result, rectangles, texture_index, grid_key, output_dir, lightmap_base_dir):
    """处理并保存单个格子的打包纹理"""
    updated_lightmap_info = {}
    
    # 创建空白纹理 - 分别为LQ和Dir创建纹理
    texture_width = texture_result.texture_width
    texture_height = texture_result.texture_height
    
    # 创建指定大小的RGBA纹理，初始为全透明（LQ - 上半部分）
    texture_array = np.zeros((texture_height, texture_width, 4), dtype=np.uint8)
    
    # 创建指定大小的RGBA纹理，初始为全透明（Dir - 下半部分）
    texture_array_dir = np.zeros((texture_height, texture_width, 4), dtype=np.uint8)
    
    print(f"处理格子 '{grid_key}' 的纹理 {texture_index}，包含 {texture_result.rectangle_count} 个矩形")
    
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
        
        # 获取原始灯光贴图路径
        lightmap_lq = original_info["lightmap_lq"]
        
        # 获取完整的灯光贴图路径
        if not os.path.isabs(lightmap_lq):
            # 检查是否需要添加.png后缀
            if not lightmap_lq.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_lightmap_path = os.path.join(lightmap_base_dir, lightmap_lq + ".png")
            else:
                full_lightmap_path = os.path.join(lightmap_base_dir, lightmap_lq)
        else:
            full_lightmap_path = lightmap_lq
        
        # 获取原始的bias_scale
        original_bias_scale = original_info["original_bias_scale"]
        
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
            # 假设图像是对称的，下半部分与上半部分相同
            y_min_dir = int(base_y + img_height / 2)  # 移动到下半部分
            y_max_dir = int(y_min_dir + padded_size_y)
            
            # 边界检查（下半部分）
            y_min_dir = max(0, min(y_min_dir, img_height - 1))
            y_max_dir = max(y_min_dir + 1, min(y_max_dir, img_height))
            
            # 提取下半部分区域（Dir）
            rect_region_dir = img_array[y_min_dir:y_max_dir, x_min:x_max]
            
            # 确保提取的区域与目标大小匹配（可能需要缩放）
            target_width = rect.width
            target_height = rect.height
            
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
            
            # 获取在打包纹理中的位置
            target_x = rect.position_x
            target_y = rect.position_y
            
            # 确保不会超出边界
            try:
                h, w = rect_region.shape[:2]
                h_dir, w_dir = rect_region_dir.shape[:2]
                
                if target_x + w <= texture_width and target_y + h <= texture_height:
                    # 将上半部分区域复制到LQ纹理
                    texture_array[target_y:target_y+h, target_x:target_x+w] = rect_region
                    
                    # 将下半部分区域复制到Dir纹理
                    texture_array_dir[target_y:target_y+h_dir, target_x:target_x+w_dir] = rect_region_dir
                    
                    # 计算新的BiasScale (基于打包纹理的UV坐标)
                    new_bias_scale = caculate_bias_scale(w, h, target_x, target_y, texture_width)
                    
                    # 生成新的贴图路径
                    new_lightmap_path = f"packed_lightmap_{texture_index}"
                    new_dir_lightmap_path = f"packed_lightmap_{texture_index}_dir"
                    
                    # 更新lightmap信息，增加Dir信息
                    updated_lightmap_info[mesh_id] = {
                        "mesh_id": mesh_id,
                        "texture_index": texture_index,
                        "new_lq": new_lightmap_path,
                        "new_dir": new_dir_lightmap_path,  # 新增Dir信息
                        "new_bias_scale": new_bias_scale,
                        "scale_factor": 1.0  # 默认缩放因子
                    }
                    
                else:
                    print(f"警告: 物体 {mesh_id} 的灯光贴图区域 ({w}x{h}) "
                          f"在位置 ({target_x},{target_y}) 超出纹理边界 "
                          f"{texture_width}x{texture_height}")
            except Exception as e:
                print(f"警告: 处理物体 {mesh_id} 时出错: {e}")
                print(traceback.format_exc())
        
        except Exception as e:
            print(f"警告: 处理 {mesh_id} 的灯光贴图时出错: {e}")
            print(traceback.format_exc())
    
    # 保存打包后的纹理
    output_path = os.path.join(output_dir, f"packed_lightmap_{texture_index}.png")
    Image.fromarray(texture_array).save(output_path)
    print(f"已保存LQ打包纹理: {output_path}")
    
    # 保存Dir纹理
    output_path_dir = os.path.join(output_dir, f"packed_lightmap_{texture_index}_dir.png")
    Image.fromarray(texture_array_dir).save(output_path_dir)
    print(f"已保存Dir打包纹理: {output_path_dir}")
    
    return updated_lightmap_info

def process_and_save_packed_textures(results, group_rectangles, texture_size=4096, output_dir=None, lightmap_base_dir=None):
    """根据C++返回的布局信息处理并保存打包后的纹理，更新BiasScale信息"""
    if output_dir is None:
        output_dir = "packed_lightmaps"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 确保lightmap_base_dir存在
    if not lightmap_base_dir:
        lightmap_base_dir = "."
    
    # 创建空白纹理 - 分别为LQ和Dir创建纹理
    packed_textures = []
    packed_textures_dir = []  # 为Dir创建单独的纹理
    for texture in results:
        # 创建指定大小的RGBA纹理，初始为全透明（LQ - 上半部分）
        texture_array = np.zeros((texture.texture_height, texture.texture_width, 4), dtype=np.uint8)
        packed_textures.append({
            "texture_index": texture.texture_index,
            "width": texture.texture_width,
            "height": texture.texture_height,
            "array": texture_array,
            "rectangles": []
        })
        
        # 创建指定大小的RGBA纹理，初始为全透明（Dir - 下半部分）
        texture_array_dir = np.zeros((texture.texture_height, texture.texture_width, 4), dtype=np.uint8)
        packed_textures_dir.append({
            "texture_index": texture.texture_index,
            "width": texture.texture_width,
            "height": texture.texture_height,
            "array": texture_array_dir,
            "rectangles": []
        })
    
    # 用于返回更新的lightmap信息
    updated_lightmap_info = {}
    
    # 处理每个纹理和其中的矩形
    for texture_idx, texture_info in enumerate(packed_textures):
        texture = results[texture_idx]
        texture_dir_info = packed_textures_dir[texture_idx]  # 获取对应的Dir纹理信息
        print(f"处理纹理 {texture.texture_index}，包含 {texture.rectangle_count} 个矩形")
        
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
            
            # 获取原始灯光贴图路径
            lightmap_lq = original_info["lightmap_lq"]
            
            # 获取完整的灯光贴图路径
            if not os.path.isabs(lightmap_lq):
                # 检查是否需要添加.png后缀
                if not lightmap_lq.lower().endswith(('.png', '.jpg', '.jpeg')):
                    full_lightmap_path = os.path.join(lightmap_base_dir, lightmap_lq + ".png")
                else:
                    full_lightmap_path = os.path.join(lightmap_base_dir, lightmap_lq)
            else:
                full_lightmap_path = lightmap_lq
            
            
            # 获取原始的bias_scale
            original_bias_scale = original_info["original_bias_scale"]
            
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
                # 假设图像是对称的，下半部分与上半部分相同
                y_min_dir = int(base_y + img_height / 2)  # 移动到下半部分
                y_max_dir = int(y_min_dir + padded_size_y)
                
                # 边界检查（下半部分）
                y_min_dir = max(0, min(y_min_dir, img_height - 1))
                y_max_dir = max(y_min_dir + 1, min(y_max_dir, img_height))
                
                # 提取下半部分区域（Dir）
                rect_region_dir = img_array[y_min_dir:y_max_dir, x_min:x_max]
                
                # 确保提取的区域与目标大小匹配（可能需要缩放）
                target_width = rect.width
                target_height = rect.height
                
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
                
                # 获取在打包纹理中的位置
                target_x = rect.position_x
                target_y = rect.position_y
                
                # 确保不会超出边界
                try:
                    h, w = rect_region.shape[:2]
                    h_dir, w_dir = rect_region_dir.shape[:2]
                    
                    if target_x + w <= texture_info["width"] and target_y + h <= texture_info["height"]:
                        # 将上半部分区域复制到LQ纹理
                        texture_info["array"][target_y:target_y+h, target_x:target_x+w] = rect_region
                        
                        # 将下半部分区域复制到Dir纹理
                        texture_dir_info["array"][target_y:target_y+h_dir, target_x:target_x+w_dir] = rect_region_dir
                        
                        # 计算新的BiasScale (基于打包纹理的UV坐标)
                        texture_width = texture_info["width"]
                        texture_height = texture_info["height"]
                        new_bias_scale = caculate_bias_scale(w, h, target_x, target_y, texture_width)
                        
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
                        
                        # 生成新的贴图路径 - 修复跨驱动器路径问题
                        try:
                            # 尝试生成相对路径
                            rel_output_dir = os.path.relpath(output_dir, os.path.dirname(lightmap_base_dir))
                            new_lightmap_path = os.path.join(rel_output_dir, f"packed_lightmap_{texture.texture_index}.png")
                            new_dir_lightmap_path = os.path.join(rel_output_dir, f"packed_lightmap_{texture.texture_index}_dir.png")
                        except ValueError as e:
                            # 如果发生错误(如跨驱动器)，则使用直接的文件名
                            print(f"注意: 跨驱动器路径问题，使用文件名作为路径: {e}")
                            new_lightmap_path = f"packed_lightmap_{texture.texture_index}.png"
                            new_dir_lightmap_path = f"packed_lightmap_{texture.texture_index}_dir.png"
                        
                        # 确保路径分隔符一致
                        new_lightmap_path = new_lightmap_path.replace("\\", "/")
                        new_dir_lightmap_path = new_dir_lightmap_path.replace("\\", "/")
                        
                        # 更新lightmap信息，增加Dir信息
                        updated_lightmap_info[mesh_id] = {
                            "mesh_id": mesh_id,
                            "texture_index": texture.texture_index,
                            "new_lq": f"packed_lightmap_{texture.texture_index}",
                            "new_dir": f"packed_lightmap_{texture.texture_index}_dir",  # 新增Dir信息
                            "new_bias_scale": new_bias_scale,
                            "scale_factor": 1.0  # 默认缩放因子
                        }
                        
                    else:
                        print(f"警告: 物体 {mesh_id} 的灯光贴图区域 ({w}x{h}) "
                              f"在位置 ({target_x},{target_y}) 超出纹理边界 "
                              f"{texture_info['width']}x{texture_info['height']}")
                except Exception as e:
                    print(f"警告: 处理物体 {mesh_id} 时出错: {e}")
                    print(traceback.format_exc())
            
            except Exception as e:
                print(f"警告: 处理 {mesh_id} 的灯光贴图时出错: {e}")
                print(traceback.format_exc())
    
    # 保存打包后的纹理
    saved_paths = []
    for texture_idx, texture_info in enumerate(packed_textures):
        # 保存LQ纹理
        texture_idx = texture_info["texture_index"]
        output_path = os.path.join(output_dir, f"packed_lightmap_{texture_idx}.png")
        Image.fromarray(texture_info["array"]).save(output_path)
        saved_paths.append(output_path)
        print(f"已保存LQ打包纹理: {output_path}")
        
        # 保存Dir纹理
        output_path_dir = os.path.join(output_dir, f"packed_lightmap_{texture_idx}_dir.png")
        Image.fromarray(packed_textures_dir[texture_idx]["array"]).save(output_path_dir)
        saved_paths.append(output_path_dir)
        print(f"已保存Dir打包纹理: {output_path_dir}")
    
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
                    lightmap_base_dir
                )
                
                # 合并更新信息
                updated_lightmap_info.update(grid_updated_info)
                
            except Exception as e:
                print(f"处理格子 '{grid_key}' 时出错: {e}")
                print(traceback.format_exc())
                continue
        
        step3_time = time.time() - step3_start_time
        print(f"步骤3: 执行贴图打包完成，耗时: {step3_time:.2f}秒")
        
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
        print(f"- 更新JSON数据: {step4_time/total_time*100:.1f}%\t({step4_time:.2f}秒)")
        
        print(f"新的光照图文件保存在: {bigmap_dir}")
        
        return True, updated_json_data
        
    except Exception as e:
        print(f"处理静态网格物体时出错: {e}")
        print(traceback.format_exc())
        return False, json_data


def go_main(parser):
    args = parser.parse_args()
    
    # 检查参数冲突
    if args.use_backup and args.create_backup:
        print("错误: --use-backup 和 --create-backup 参数不能同时使用")
        print("  --use-backup: 从备份文件读取JSON")
        print("  --create-backup: 创建原始JSON文件的备份")
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
        try:
            if os.path.exists(json_path):
                print(f"创建备份文件: {backup_json_path}")
                import shutil
                shutil.copy2(json_path, backup_json_path)
                print("✓ 备份创建成功")
                print("提示: 后续处理可以使用 --use-backup 参数从备份恢复")
            else:
                print(f"错误: 原始JSON文件不存在: {json_path}")
                return
        except Exception as e:
            print(f"创建备份时出错: {e}")
            return
        
        print(f"场景 '{args.scene}' 的备份已完成")

    # 确定实际使用的JSON路径
    if args.use_backup:
        # 如果使用备份，检查备份是否存在
        if os.path.exists(backup_json_path):
            print(f"从备份读取JSON: {backup_json_path}")
            source_json_path = backup_json_path
        else:
            print(f"警告: 备份文件不存在 {backup_json_path}，使用原始JSON")
            source_json_path = json_path
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
            print("  --create-backup       只创建JSON备份文件")
            print("  --use-backup          从备份文件读取JSON")
            return

    print(f"场景: {args.scene}")
    print(f"JSON路径: {source_json_path}")
    print(f"灯光贴图路径: {lightmap_base_dir}")
    print(f"纹理大小: {texture_size}")
    print(f"最小纹理大小: {min_texture_size}")

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
    parser.add_argument("--use-backup", action="store_true",
                        help="从备份文件夹读取JSON，而不是从原始位置读取")
    parser.add_argument("--create-backup", action="store_true",
                        help="创建原始JSON文件的备份（可以与处理选项组合使用）")

    go_main(parser) 

if __name__ == "__main__":
    main() 
    
    