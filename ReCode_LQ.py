import os
import sys
import json
import time
import numpy as np
import traceback
import itertools
from pathlib import Path
from PIL import Image
import math
import shutil
from datetime import datetime
import copy
from collections import defaultdict
import argparse
import cv2
import random

TextureSize = 2048

RootPath = Path("C:/chaos_integrated_tools/data_analysis/scene")
LightmapPath = Path.joinpath(RootPath, "light/light_map")
BigLightmapPath = Path.joinpath(LightmapPath, "BigLightmap")
JsonPath = Path.joinpath(RootPath, "current_scene_data_source.json")
MinTextureSize = 16

# 新增:获取新JSON文件的路径
def get_new_json_path():
    # 使用时间戳创建新的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_name = f"current_scene_data_{timestamp}.json"
    return Path.joinpath(RootPath, json_name)

class LightmapPacker:
    def __init__(self, texture_size, min_texture_size):
        self.texture_size = texture_size
        self.min_texture_size = min_texture_size
        self.current_textures = []  # 存储当前的纹理图像数据
        self.current_positions = []  # 存储每个纹理的位置信息
        self.add_new_texture()
    
    def add_new_texture(self):
        # 使用NumPy创建空白纹理数组
        new_texture = np.zeros((self.texture_size, self.texture_size, 4), dtype=np.uint8)
        self.current_textures.append(new_texture)
        self.current_positions.append([])
        return len(self.current_textures) - 1
    
    def reset(self):
        """重置打包器状态"""
        self.current_textures = []
        self.current_positions = []
        self.add_new_texture()
    
    def get_current_state(self):
        """获取当前状态的副本"""
        return {
            'textures': [t.copy() for t in self.current_textures],
            'positions': [p.copy() for p in self.current_positions]
        }
    
    def restore_state(self, state):
        """恢复到指定状态"""
        self.current_textures = [t.copy() for t in state['textures']]
        self.current_positions = [p.copy() for p in state['positions']]

    def can_fit(self, size, texture_index, positions):
        """检查是否可以放入指定纹理中
        positions: 当前纹理的已占用位置列表
        """
        if not positions:
            return True, (0, 0)
        
        # 实现简单的装箱算法
        for y in range(0, self.texture_size - size[1] + 1, size[1]):
            for x in range(0, self.texture_size - size[0] + 1, size[0]):
                can_place = True
                for pos, s in positions:
                    if (x < pos[0] + s[0] and x + size[0] > pos[0] and
                        y < pos[1] + s[1] and y + size[1] > pos[1]):
                        can_place = False
                        break
                if can_place:
                    return True, (x, y)
        return False, None

    def add_texture(self, texture_array, size):
        # 尝试在现有纹理中找到位置
        for i in range(len(self.current_textures)):
            can_fit, position = self.can_fit(size, i, self.current_positions[i])
            if can_fit:
                # 直接复制像素数据
                x, y = position
                self.current_textures[i][y:y+size[1], x:x+size[0]] = texture_array
                self.current_positions[i].append((position, size))
                return i, position
        
        # 如果没有找到位置,创建新的纹理
        new_index = self.add_new_texture()
        self.current_textures[new_index][0:size[1], 0:size[0]] = texture_array
        self.current_positions[new_index].append(((0, 0), size))
        return new_index, (0, 0)

    def try_pack_with_scale(self, texture_arrays, original_sizes, scale_factor):
        """尝试使用指定缩放因子打包所有纹理"""
        scaled_arrays = []
        scaled_sizes = []
        
        # 缩放所有纹理
        for texture, size in zip(texture_arrays, original_sizes):
            new_size = (int(size[0] * scale_factor), int(size[1] * scale_factor))
            if new_size[0] < self.min_texture_size or new_size[1] < self.min_texture_size:
                return False, None
            
            # 使用最近邻插值进行缩放以保持像素值
            scaled = Image.fromarray(texture).resize(new_size, Image.NEAREST)
            scaled_arrays.append(np.array(scaled))
            scaled_sizes.append(new_size)
        
        # 尝试打包
        success = True
        positions = []
        
        # 创建临时状态用于尝试
        temp_textures = [t.copy() for t in self.current_textures]
        temp_positions = [p.copy() for p in self.current_positions]
        
        try:
            # 确保至少有一个纹理
            if not temp_textures:
                temp_textures.append(np.zeros((self.texture_size, self.texture_size, 4), dtype=np.uint8))
                temp_positions.append([])
            
            # 尝试将所有纹理放入同一个纹理中
            current_texture_index = len(temp_textures) - 1
            
            for texture, size in zip(scaled_arrays, scaled_sizes):
                found_position = False
                
                # 先尝试在当前纹理中找位置
                can_fit, position = self.can_fit(size, current_texture_index, temp_positions[current_texture_index])
                if can_fit:
                    x, y = position
                    temp_textures[current_texture_index][y:y+size[1], x:x+size[0]] = texture
                    temp_positions[current_texture_index].append((position, size))
                    positions.append((current_texture_index, position))
                    found_position = True
                
                if not found_position:
                    # 如果当前纹理放不下,创建新的纹理
                    new_texture = np.zeros((self.texture_size, self.texture_size, 4), dtype=np.uint8)
                    new_texture[0:size[1], 0:size[0]] = texture
                    temp_textures.append(new_texture)
                    temp_positions.append([((0, 0), size)])
                    current_texture_index = len(temp_textures) - 1
                    positions.append((current_texture_index, (0, 0)))
            
            # 如果所有纹理都成功放置,更新实际状态
            self.current_textures = temp_textures
            self.current_positions = temp_positions
            success = True
            
        except Exception as e:
            print(f"打包过程中出错:{str(e)}")
            success = False
        
        if success:
            return True, (positions, scale_factor)
        return False, None

    def try_place_single_item(self, size, texture_idx, texture_data=None):
        """尝试放置单个物体,确保不会与已有物体重叠"""
        w, h = size
        
        # 高级策略:优先尝试已有区域的边缘位置
        for pos, s in self.current_positions[texture_idx]:
            # 检查右侧
            x_right = pos[0] + s[0]
            if x_right + w <= self.texture_size:
                can_place = True
                for p2, s2 in self.current_positions[texture_idx]:
                    if p2 == pos:
                        continue
                    if (x_right < p2[0] + s2[0] and x_right + w > p2[0] and
                        pos[1] < p2[1] + s2[1] and pos[1] + h > p2[1]):
                        can_place = False
                        break
                if can_place:
                    return (x_right, pos[1])
            
            # 检查底部
            y_bottom = pos[1] + s[1]
            if y_bottom + h <= self.texture_size:
                can_place = True
                for p2, s2 in self.current_positions[texture_idx]:
                    if p2 == pos:
                        continue
                    if (pos[0] < p2[0] + s2[0] and pos[0] + w > p2[0] and
                        y_bottom < p2[1] + s2[1] and y_bottom + h > p2[1]):
                        can_place = False
                        break
                if can_place:
                    return (pos[0], y_bottom)
        
        # 常规网格搜索 - 小步长(更精确但更慢）
        step = max(1, min(w, h) // 10)  # 使用小步长,但不小于1
        for y in range(0, self.texture_size - h + 1, step):
            for x in range(0, self.texture_size - w + 1, step):
                # 检查每个实际位置,而不仅仅是步长的位置
                if x + w > self.texture_size or y + h > self.texture_size:
                    continue
                    
                can_place = True
                for pos, s in self.current_positions[texture_idx]:
                    if (x < pos[0] + s[0] and x + w > pos[0] and
                        y < pos[1] + s[1] and y + h > pos[1]):
                        can_place = False
                        break
                
                if can_place:
                    # 额外验证:仔细检查像素级冲突
                    mask = np.sum(self.current_textures[texture_idx][y:y+h, x:x+w, 3])
                    if mask > 0:  # 如果有任何非零alpha值(表示已有内容）
                        can_place = False
                    
                    if can_place:
                        return (x, y)
        
        return None

    def can_fit_group(self, group, scale=1.0, existing_only=False, specific_texture=None):
        """
        尝试将一组纹理放入纹理中,同时考虑是否只检查现有纹理或特定纹理
        
        参数:
            group: 需要放置的组
            scale: 缩放比例,默认为1.0(不缩放）
            existing_only: 是否只检查现有纹理,不创建新纹理
            specific_texture: 指定尝试放入的特定纹理索引
            
        返回:
            (texture_idx, positions, scale, None): 成功时返回纹理索引、位置列表和缩放比例
            如果无法放入,则返回(None, None, scale, None)
        """
        # 获取组中的尺寸
        sizes = []
        for info in group['infos']:
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            
            # 尝试打开图像获取尺寸
            try:
                with Image.open(lightmap_path) as img:
                    source_width, source_height = img.size
                
                # 计算原始区域的像素尺寸
                original_width = int(info["BiasScale"][2] * source_width)
                original_height = int(info["BiasScale"][3] * source_height) * 0.5
                
                sizes.append((original_width, original_height))
            except Exception as e:
                print(f"无法获取图像尺寸: {lightmap_path}, 错误: {e}")
                # 给一个默认尺寸
                sizes.append((64, 64))
        
        # 创建缩放后的尺寸信息(但不执行实际的图片缩放)
        scaled_sizes = []
        for w, h in sizes:
            # 确保最小尺寸
            scaled_w = max(1, int(w * scale))
            scaled_h = max(1, int(h * scale))
            scaled_sizes.append((scaled_w, scaled_h))
        
        # 如果指定了特定纹理,只尝试那个纹理
        texture_indices = []
        if specific_texture is not None:
            texture_indices = [specific_texture]
        else:
            # 否则,按照剩余空间从大到小的顺序尝试所有现有纹理
            texture_indices = sorted(range(len(self.current_textures)), 
                                    key=lambda idx: self.current_space[idx], 
                                    reverse=True)
        
        # 尝试在现有纹理中放置
        for texture_idx in texture_indices:
            # 尝试在当前纹理中放置组
            positions = self.try_place_group_in_texture(texture_idx, scaled_sizes)
            if positions:
                # 返回布局信息，但不返回缩放后的纹理(推迟实际的图片处理)
                return texture_idx, positions, scale, None
        
        # 如果要求只使用现有纹理或指定了特定纹理但失败,直接返回
        if existing_only or specific_texture is not None:
            return None, None, scale, None
        
        # 否则,创建新的纹理并尝试放置
        new_texture_idx = self.add_new_texture()
        positions = self.try_place_group_in_texture(new_texture_idx, scaled_sizes)
        if positions:
            # 返回布局信息，但不返回缩放后的纹理
            return new_texture_idx, positions, scale, None
        
        # 如果还是不行,返回失败
        return None, None, scale, None

    def get_scaled_textures(self, group, scale):
        """获取缩放后的纹理列表"""
        scaled_textures = []
        for i, texture in enumerate(group['textures']):
            w, h = group['sizes'][i]
            scaled_w = max(1, int(w * scale))
            scaled_h = max(1, int(h * scale))
            
            if scale != 1.0:
                img = Image.fromarray(texture)
                scaled_img = img.resize((scaled_w, scaled_h), Image.NEAREST)
                scaled_textures.append(np.array(scaled_img))
            else:
                scaled_textures.append(texture)
        
        return scaled_textures

    def try_place_group_in_texture(self, texture_idx, sizes):
        """尝试在指定纹理中放置一组物体,返回位置列表或None"""
        # 创建占用图,标记已使用区域
        occupation_map = np.zeros((self.texture_size, self.texture_size), dtype=bool)
        
        # 标记当前纹理的已用区域
        for pos, size in self.current_positions[texture_idx]:
            x, y = pos
            w, h = size
            occupation_map[y:y+h, x:x+w] = True
        
        # 按面积从大到小排序物体
        sizes_with_index = [(i, size) for i, size in enumerate(sizes)]
        sizes_with_index.sort(key=lambda x: x[1][0] * x[1][1], reverse=True)
        
        positions = [None] * len(sizes)
        
        # 创建空白区域的四叉树索引
        empty_regions = self._build_empty_regions_index(occupation_map)
        
        # 尝试放置每个物体
        for idx, (i, size) in enumerate(sizes_with_index):
            w, h = size
            pos = None
            
            # 尝试放置在左上角
            if idx == 0 and not np.any(occupation_map[0:h, 0:w]):
                pos = (0, 0)
            else:
                # 尝试紧贴已放置物体
                for prev_idx in range(idx):
                    prev_i = sizes_with_index[prev_idx][0]
                    if positions[prev_i] is None:
                        continue
                    
                    prev_x, prev_y = positions[prev_i]
                    prev_w, prev_h = sizes[prev_i]
                    
                    # 尝试右侧放置
                    x_right = prev_x + prev_w
                    if x_right + w <= self.texture_size and not np.any(occupation_map[prev_y:prev_y+h, x_right:x_right+w]):
                        pos = (x_right, prev_y)
                        break
                    
                    # 尝试下方放置
                    y_bottom = prev_y + prev_h
                    if y_bottom + h <= self.texture_size and not np.any(occupation_map[y_bottom:y_bottom+h, prev_x:prev_x+w]):
                        pos = (prev_x, y_bottom)
                        break
                
                # 如果紧贴放置失败,使用四叉树索引快速定位可能的放置位置
                if pos is None:
                    pos = self._find_placement_with_regions(empty_regions, w, h, occupation_map)
            
            if pos:
                positions[i] = pos
                x, y = pos
                # 标记占用区域
                occupation_map[y:y+h, x:x+w] = True
                # 更新四叉树索引
                self._update_empty_regions(empty_regions, x, y, w, h)
            else:
                # 一个物体放不下,整个放置失败
                return None
        
        # 验证所有位置都有效
        if None in positions:
            return None
        
        return positions

    def _build_empty_regions_index(self, occupation_map):
        """构建空白区域索引，用于快速查找放置位置"""
        empty_regions = []
        visited = np.zeros_like(occupation_map, dtype=bool)
        
        # 使用步长来减少检查的点数量
        step = min(32, max(self.texture_size, self.texture_size) // 64)  # 动态步长
        
        for y in range(0, self.texture_size, step):
            for x in range(0, self.texture_size, step):
                if visited[y, x] or occupation_map[y, x]:
                    continue
                    
                # 探测最大可用矩形
                max_w = 0
                max_h = 0
                
                # 探测宽度
                for w in range(step, self.texture_size - x + 1, step):
                    if x + w > self.texture_size or np.any(occupation_map[y:y+step, x:x+w]):
                        max_w = w - step
                        break
                    max_w = w
                    
                # 探测高度
                for h in range(step, self.texture_size - y + 1, step):
                    if y + h > self.texture_size or np.any(occupation_map[y:y+h, x:x+max_w]):
                        max_h = h - step
                        break
                    max_h = h
                
                if max_w > 0 and max_h > 0:
                    empty_regions.append((x, y, max_w, max_h))
                    # 标记已访问
                    visited[y:y+max_h, x:x+max_w] = True
        
        # 按面积从大到小排序
        empty_regions.sort(key=lambda r: r[2] * r[3], reverse=True)
        return empty_regions

    def _find_placement_with_regions(self, empty_regions, width, height, occupation_map):
        """使用空白区域索引快速查找放置位置"""
        # 首先检查所有大于等于目标尺寸的区域
        for x, y, w, h in empty_regions:
            if w >= width and h >= height:
                # 验证该区域确实可用（因为索引可能部分过时）
                if not np.any(occupation_map[y:y+height, x:x+width]):
                    return (x, y)
        
        # 如果没有找到合适的区域，回退到传统网格搜索，但使用更大的步长
        step = max(1, min(width, height) // 4)
        for y in range(0, self.texture_size - height + 1, step):
            for x in range(0, self.texture_size - width + 1, step):
                # 快速检查是否有可能放置
                if occupation_map[y, x] or occupation_map[y+height-1, x] or occupation_map[y, x+width-1] or occupation_map[y+height-1, x+width-1]:
                    continue
                    
                # 详细检查整个区域
                if not np.any(occupation_map[y:y+height, x:x+width]):
                    # 如果需要精确匹配，进行细粒度搜索
                    found = True
                    for fine_y in range(y, y+step):
                        if fine_y + height > self.texture_size:
                            continue
                        for fine_x in range(x, x+step):
                            if fine_x + width > self.texture_size:
                                continue
                            if not np.any(occupation_map[fine_y:fine_y+height, fine_x:fine_x+width]):
                                return (fine_x, fine_y)
        
        return None

    def _update_empty_regions(self, empty_regions, x, y, width, height):
        """更新空白区域索引"""
        # 移除或分割被占用的区域
        i = 0
        while i < len(empty_regions):
            rx, ry, rw, rh = empty_regions[i]
            
            # 检查是否有重叠
            if (x < rx + rw and x + width > rx and
                y < ry + rh and y + height > ry):
                
                # 移除当前区域
                empty_regions.pop(i)
                
                # 创建剩余区域（分割成最多4个区域）
                # 左侧区域
                if x > rx:
                    empty_regions.append((rx, ry, x - rx, rh))
                
                # 右侧区域
                if x + width < rx + rw:
                    empty_regions.append((x + width, ry, rx + rw - (x + width), rh))
                
                # 上方区域
                if y > ry:
                    empty_regions.append((rx, ry, rw, y - ry))
                
                # 下方区域
                if y + height < ry + rh:
                    empty_regions.append((rx, y + height, rw, ry + rh - (y + height)))
            else:
                i += 1

    def place_group(self, group, texture_idx, positions, scale, scaled_textures=None):
        """将一组纹理放置在指定的纹理中
        
        参数:
            group: 要放置的组,包含纹理和信息
            texture_idx: 目标纹理索引
            positions: 放置位置列表
            scale: 缩放系数
            scaled_textures: 预先缩放的纹理，始终为None，因为我们在此处才执行实际缩放
        """
        # 在这里执行实际的图片加载和缩放操作
        scaled_textures = []
        
        for info in group['infos']:
            # 加载并处理灯光贴图
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            
            # 加载原始图像
            img = Image.open(lightmap_path)
            source_width, source_height = img.size
            
            # 计算原始区域的像素尺寸
            original_width = int(info["BiasScale"][2] * source_width)
            original_height = int(info["BiasScale"][3] * source_height) * 0.5
            
            # 将提取区域转换为整个图片
            texture = extract_lightmap(lightmap_path, info["BiasScale"])
            
            # 缩放图片
            if scale != 1.0:
                scaled_w = max(1, int(original_width * scale))
                scaled_h = max(1, int(original_height * scale))
                scaled_img = Image.fromarray(texture).resize((scaled_w, scaled_h), Image.NEAREST)
                scaled_textures.append(np.array(scaled_img))
            else:
                scaled_textures.append(texture)
        
        group_results = []
        
        for i, (position, info) in enumerate(zip(positions, group['infos'])):
            if position is None:  # 跳过没有成功放置的物体
                continue
                    
            # 获取原始图像信息
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            
            with Image.open(lightmap_path) as img:
                source_width, source_height = img.size
            
            # 计算原始区域的像素尺寸
            original_width = int(info["BiasScale"][2] * source_width)
            original_height = int(info["BiasScale"][3] * source_height) * 0.5
            
            # 计算缩放后的尺寸
            scaled_width = int(original_width * scale)
            scaled_height = int(original_height * scale)
            
            # 获取缩放后的纹理
            scaled_texture = scaled_textures[i]
            
            # 确保纹理尺寸与计算尺寸匹配
            actual_h, actual_w = scaled_texture.shape[:2]
            if actual_w != scaled_width or actual_h != scaled_height:
                print(f"警告:实际纹理尺寸({actual_w}x{actual_h})与计算尺寸({scaled_width}x{scaled_height})不匹配")
                # 使用实际的尺寸
                scaled_width = actual_w
                scaled_height = actual_h
            
            # 将纹理放入目标位置
            x, y = position
            
            # 双重检查:确保目标区域是空的
            target_region = self.current_textures[texture_idx][y:y+scaled_height, x:x+scaled_width]
            if np.any(target_region[:,:,3] > 0):
                print(f"警告:位置 ({x},{y}) 已经有内容,可能会导致覆盖!")
            
            try:
                self.current_textures[texture_idx][y:y+scaled_height, x:x+scaled_width] = scaled_texture
            except ValueError as e:
                print(f"错误:无法将形状为 {scaled_texture.shape} 的纹理复制到形状为 [{y}:{y+scaled_height}, {x}:{x+scaled_width}] 的区域")
                print(f"详细错误: {str(e)}")
                continue
            
            # 记录已使用的位置
            self.current_positions[texture_idx].append(((x, y), (scaled_width, scaled_height)))
            # 更新剩余空间
            self.current_space[texture_idx] -= scaled_width * scaled_height
            
            # 计算新的bias_scale值
            # 原始bias_scale: [u_min, v_min, width, height]
            original_bias_scale = info["BiasScale"]
            
            # 在打包纹理中的新坐标
            new_u_min = x / self.texture_size
            new_v_min = y / self.texture_size
            new_width = scaled_width / self.texture_size
            new_height = scaled_height / self.texture_size
            
            # 新的bias_scale
            new_bias_scale = [new_u_min, new_v_min, new_width, new_height]
            
            # 添加到结果
            result = {
                "mesh_id": info["mesh_id"],
                "Name": info["Name"],
                "texture_index": texture_idx,
                "new_lq": f"packed_lightmap_{texture_idx}",
                "new_bias_scale": new_bias_scale,
                "scale_factor": scale,
                "position": (x, y),
                "size": (scaled_width, scaled_height)
            }
            group_results.append(result)
        
        return group_results

class GlobalRectPacker:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.textures = []
        self.used_positions = []  # 每个纹理的已用位置列表
        self.texture_remaining_space = []  # 每个纹理的剩余空间
        # 添加第一个纹理
        self.add_texture()
    
    def add_texture(self):
        """添加新纹理"""
        self.textures.append(np.zeros((self.height, self.width, 4), dtype=np.uint8))
        self.used_positions.append([])
        self.texture_remaining_space.append(self.width * self.height)
        return len(self.textures) - 1
        
    def can_fit_group(self, group, scale=1.0, existing_only=False, specific_texture=None):
        """
        尝试将一组纹理放入纹理中,同时考虑是否只检查现有纹理或特定纹理
        
        参数:
            group: 需要放置的组
            scale: 缩放比例,默认为1.0(不缩放）
            existing_only: 是否只检查现有纹理,不创建新纹理
            specific_texture: 指定尝试放入的特定纹理索引
            
        返回:
            (texture_idx, positions, scale, None): 成功时返回纹理索引、位置列表和缩放比例
            如果无法放入,则返回(None, None, scale, None)
        """
        # 获取组中的尺寸
        sizes = []
        for info in group['infos']:
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            
            # 尝试打开图像获取尺寸
            try:
                with Image.open(lightmap_path) as img:
                    source_width, source_height = img.size
                
                # 计算原始区域的像素尺寸
                original_width = int(info["BiasScale"][2] * source_width)
                # 乘以0.5是因为在lightmap中，图片的上半部分才是我需要的内容
                original_height = int(info["BiasScale"][3] * source_height) * 0.5
                
                sizes.append((original_width, original_height))
            except Exception as e:
                print(f"无法获取图像尺寸: {lightmap_path}, 错误: {e}")
                # 给一个默认尺寸
                sizes.append((64, 64))
        
        # 创建缩放后的尺寸信息(但不执行实际的图片缩放)
        scaled_sizes = []
        for w, h in sizes:
            # 确保最小尺寸
            scaled_w = max(1, int(w * scale))
            scaled_h = max(1, int(h * scale))
            scaled_sizes.append((scaled_w, scaled_h))
        
        # 如果指定了特定纹理,只尝试那个纹理
        texture_indices = []
        if specific_texture is not None:
            texture_indices = [specific_texture]
        else:
            # 否则,按照剩余空间从大到小的顺序尝试所有现有纹理
            texture_indices = sorted(range(len(self.textures)), 
                                    key=lambda idx: self.texture_remaining_space[idx], 
                                    reverse=True)
        
        # 尝试在现有纹理中放置
        for texture_idx in texture_indices:
            # 尝试在当前纹理中放置组
            positions = self.try_place_group_in_texture(texture_idx, scaled_sizes)
            if positions:
                # 返回布局信息，但不返回缩放后的纹理(推迟实际的图片处理)
                return texture_idx, positions, scale, None
        
        # 如果要求只使用现有纹理或指定了特定纹理但失败,直接返回
        if existing_only or specific_texture is not None:
            return None, None, scale, None
        
        # 否则,创建新的纹理并尝试放置
        new_texture_idx = self.add_texture()
        positions = self.try_place_group_in_texture(new_texture_idx, scaled_sizes)
        if positions:
            # 返回布局信息，但不返回缩放后的纹理
            return new_texture_idx, positions, scale, None
        
        # 如果还是不行,返回失败
        return None, None, scale, None
    
    def try_place_group_in_texture(self, texture_idx, sizes):
        """尝试在指定纹理中放置一组物体,返回位置列表或None"""
        # 创建占用图,标记已使用区域
        occupation_map = np.zeros((self.height, self.width), dtype=bool)
        
        # 标记当前纹理的已用区域
        for pos, size in self.used_positions[texture_idx]:
            x, y = pos
            w, h = size
            occupation_map[y:y+h, x:x+w] = True
        
        # 按面积从大到小排序物体
        sizes_with_index = [(i, size) for i, size in enumerate(sizes)]
        sizes_with_index.sort(key=lambda x: x[1][0] * x[1][1], reverse=True)
        
        positions = [None] * len(sizes)
        
        # 创建空白区域的四叉树索引
        empty_regions = self._build_empty_regions_index(occupation_map)
        
        # 尝试放置每个物体
        for idx, (i, size) in enumerate(sizes_with_index):
            w, h = size
            pos = None
            
            # 尝试放置在左上角
            if idx == 0 and not np.any(occupation_map[0:h, 0:w]):
                pos = (0, 0)
            else:
                # 尝试紧贴已放置物体
                for prev_idx in range(idx):
                    prev_i = sizes_with_index[prev_idx][0]
                    if positions[prev_i] is None:
                        continue
                    
                    prev_x, prev_y = positions[prev_i]
                    prev_w, prev_h = sizes[prev_i]
                    
                    # 尝试右侧放置
                    x_right = prev_x + prev_w
                    if x_right + w <= self.width and not np.any(occupation_map[prev_y:prev_y+h, x_right:x_right+w]):
                        pos = (x_right, prev_y)
                        break
                    
                    # 尝试下方放置
                    y_bottom = prev_y + prev_h
                    if y_bottom + h <= self.height and not np.any(occupation_map[y_bottom:y_bottom+h, prev_x:prev_x+w]):
                        pos = (prev_x, y_bottom)
                        break
                
                # 如果紧贴放置失败,使用四叉树索引快速定位可能的放置位置
                if pos is None:
                    pos = self._find_placement_with_regions(empty_regions, w, h, occupation_map)
            
            if pos:
                positions[i] = pos
                x, y = pos
                # 标记占用区域
                occupation_map[y:y+h, x:x+w] = True
                # 更新四叉树索引
                self._update_empty_regions(empty_regions, x, y, w, h)
            else:
                # 一个物体放不下,整个放置失败
                return None
        
        # 验证所有位置都有效
        if None in positions:
            return None
        
        return positions

    def _build_empty_regions_index(self, occupation_map):
        """构建空白区域索引，用于快速查找放置位置"""
        empty_regions = []
        visited = np.zeros_like(occupation_map, dtype=bool)
        
        # 使用步长来减少检查的点数量
        step = min(32, max(self.width, self.height) // 64)  # 动态步长
        
        for y in range(0, self.height, step):
            for x in range(0, self.width, step):
                if visited[y, x] or occupation_map[y, x]:
                    continue
                    
                # 探测最大可用矩形
                max_w = 0
                max_h = 0
                
                # 探测宽度
                for w in range(step, self.width - x + 1, step):
                    if x + w > self.width or np.any(occupation_map[y:y+step, x:x+w]):
                        max_w = w - step
                        break
                    max_w = w
                    
                # 探测高度
                for h in range(step, self.height - y + 1, step):
                    if y + h > self.height or np.any(occupation_map[y:y+h, x:x+max_w]):
                        max_h = h - step
                        break
                    max_h = h
                
                if max_w > 0 and max_h > 0:
                    empty_regions.append((x, y, max_w, max_h))
                    # 标记已访问
                    visited[y:y+max_h, x:x+max_w] = True
        
        # 按面积从大到小排序
        empty_regions.sort(key=lambda r: r[2] * r[3], reverse=True)
        return empty_regions

    def _find_placement_with_regions(self, empty_regions, width, height, occupation_map):
        """使用空白区域索引快速查找放置位置"""
        # 首先检查所有大于等于目标尺寸的区域
        for x, y, w, h in empty_regions:
            if w >= width and h >= height:
                # 验证该区域确实可用（因为索引可能部分过时）
                if not np.any(occupation_map[y:y+height, x:x+width]):
                    return (x, y)
        
        # 如果没有找到合适的区域，回退到传统网格搜索，但使用更大的步长
        step = max(1, min(width, height) // 4)
        for y in range(0, self.height - height + 1, step):
            for x in range(0, self.width - width + 1, step):
                # 快速检查是否有可能放置
                if occupation_map[y, x] or occupation_map[y+height-1, x] or occupation_map[y, x+width-1] or occupation_map[y+height-1, x+width-1]:
                    continue
                    
                # 详细检查整个区域
                if not np.any(occupation_map[y:y+height, x:x+width]):
                    # 如果需要精确匹配，进行细粒度搜索
                    found = True
                    for fine_y in range(y, y+step):
                        if fine_y + height > self.height:
                            continue
                        for fine_x in range(x, x+step):
                            if fine_x + width > self.width:
                                continue
                            if not np.any(occupation_map[fine_y:fine_y+height, fine_x:fine_x+width]):
                                return (fine_x, fine_y)
        
        return None

    def _update_empty_regions(self, empty_regions, x, y, width, height):
        """更新空白区域索引"""
        # 移除或分割被占用的区域
        i = 0
        while i < len(empty_regions):
            rx, ry, rw, rh = empty_regions[i]
            
            # 检查是否有重叠
            if (x < rx + rw and x + width > rx and
                y < ry + rh and y + height > ry):
                
                # 移除当前区域
                empty_regions.pop(i)
                
                # 创建剩余区域（分割成最多4个区域）
                # 左侧区域
                if x > rx:
                    empty_regions.append((rx, ry, x - rx, rh))
                
                # 右侧区域
                if x + width < rx + rw:
                    empty_regions.append((x + width, ry, rx + rw - (x + width), rh))
                
                # 上方区域
                if y > ry:
                    empty_regions.append((rx, ry, rw, y - ry))
                
                # 下方区域
                if y + height < ry + rh:
                    empty_regions.append((rx, y + height, rw, ry + rh - (y + height)))
            else:
                i += 1

    def place_group(self, group, texture_idx, positions, scale=1.0, scaled_textures=None):
        """
        将组放入指定纹理中的指定位置
        
        参数:
            group: 要放置的组
            texture_idx: 目标纹理索引
            positions: 放置位置列表
            scale: 缩放比例
            scaled_textures: 预先缩放的纹理，始终为None，因为我们在此处才执行实际缩放
        """
        # 在这里才执行实际的图片缩放操作
        scaled_textures = []
        for i, texture in enumerate(group['textures']):
            w, h = group['sizes'][i]
            scaled_w = max(1, int(w * scale))
            scaled_h = max(1, int(h * scale))
            
            # 确保纹理是numpy数组
            if not isinstance(texture, np.ndarray):
                texture = np.array(texture)
            
            # 使用PIL进行缩放
            if scale != 1.0:
                img = Image.fromarray(texture)
                scaled_img = img.resize((scaled_w, scaled_h), Image.NEAREST)
                scaled_textures.append(np.array(scaled_img))
            else:
                scaled_textures.append(texture)
        
        # 遍历每个物体进行放置
        for i, info in enumerate(group['infos']):
            if positions[i] is None:
                # 跳过无法放置的物体
                continue
            
            # 获取原始图像信息
            texture = scaled_textures[i]
            x, y = positions[i]
            original_w, original_h = group['sizes'][i]
            scaled_w = max(1, int(original_w * scale))
            scaled_h = max(1, int(original_h * scale))
            
            # 检查目标尺寸是否匹配纹理尺寸
            if texture.shape[0] != scaled_h or texture.shape[1] != scaled_w:
                print(f"警告:纹理大小不匹配:预期 ({scaled_w}, {scaled_h}),"
                      f"实际 ({texture.shape[1]}, {texture.shape[0]})")
                # 调整纹理大小以匹配
                img = Image.fromarray(texture)
                img = img.resize((scaled_w, scaled_h), Image.NEAREST)
                texture = np.array(img)
            
            # 验证目标区域是否为空或可以覆盖
            target_region = self.textures[texture_idx][y:y+scaled_h, x:x+scaled_w]
            if np.any(target_region[:, :, 3] > 0):
                print(f"警告:目标区域 ({x}, {y}, {scaled_w}, {scaled_h}) 在纹理 {texture_idx} 中不为空")
            
            try:
                # 复制纹理数据到目标区域
                self.textures[texture_idx][y:y+scaled_h, x:x+scaled_w] = texture
            except ValueError as e:
                print(f"复制纹理时出错:{e}")
                print(f"目标形状: {target_region.shape}, 源形状: {texture.shape}")
                continue
            
            # 更新已使用的位置和剩余空间
            self.used_positions[texture_idx].append((positions[i], (scaled_w, scaled_h)))
            self.texture_remaining_space[texture_idx] -= scaled_w * scaled_h
        
        return True

def load_json_data():
    with open(JsonPath, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_lightmap(lightmap_path, bias_scale):
    """
    从原始灯光贴图中提取指定区域的纹理
    
    参数:
        lightmap_path: 灯光贴图路径
        bias_scale: 偏移和缩放参数 [u_min, v_min, width, height]
        
    返回:
        提取的区域纹理数组
    """
    # 使用PIL打开图片
    original = Image.open(lightmap_path)
    
    # 转换为NumPy数组
    img_array = np.array(original)
    
    # 计算提取区域
    x = int(bias_scale[0] * original.width)
    y = int(bias_scale[1] * original.height * 0.5)  # 注意这里乘以0.5
    width = int(bias_scale[2] * original.width)
    height = int(bias_scale[3] * original.height * 0.5)  # 注意这里乘以0.5
    
    # 防止越界
    x = max(0, min(x, original.width - 1))
    y = max(0, min(y, original.height - 1))
    width = max(1, min(width, original.width - x))
    height = max(1, min(height, original.height - y))
    
    # 直接提取像素数据
    region_array = img_array[y:y+height, x:x+width].copy()
    return region_array

def group_by_parameters(json_data):
    """根据Parameters对物体进行分组"""
    groups = {}
    
    for mesh_id, mesh in json_data["Static Mesh"].items():
        if "Parameters" not in mesh or "LightMap" not in mesh:
            continue
            
        params = mesh["Parameters"]
        if "MeshJsonURL" not in params or "MeshDataURL" not in params:
            continue
            
        key = (params["MeshJsonURL"], params["MeshDataURL"])
        if key not in groups:
            groups[key] = []
        groups[key].append({
            "mesh_id": mesh_id,
            "Name": mesh["Name"],
            "LQ": mesh["LightMap"]["LQ"],
            "BiasScale": mesh["LightMap"]["BiasScale"]
        })
    
    return groups

def global_packing_optimization(groups):
    """全局打包优化算法,考虑所有可能的组合以最大化空间利用率
    
    Args:
        groups: 按组整理的数据字典
        
    Returns:
        优化后的打包结果信息(仅包含布局数据)
    """
    # 首先获取所有组的信息
    sorted_groups = []
    for key, group_infos in groups.items():
        total_area = 0
        textures = []
        sizes = []
        for info in group_infos:
            # 处理灯光贴图
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            
            # 提取区域并添加到纹理列表
            texture = extract_lightmap(lightmap_path, info["BiasScale"])
            textures.append(texture)
            
            # 记录尺寸
            source_width, source_height = Image.open(lightmap_path).size
            width = int(info["BiasScale"][2] * source_width)
            height = int(info["BiasScale"][3] * source_height) * 0.5
            sizes.append((width, height))
            
            # 累加面积
            total_area += width * height
        
        # 将组信息存储起来
        group = {
            'key': key,
            'infos': group_infos,
            'textures': textures,
            'sizes': sizes,
            'area': total_area
        }
        
        # 计算其他组特征
        if group['sizes']:
            max_dim = max(max(w, h) for w, h in group['sizes'])
            min_dim = min(min(w, h) for w, h in group['sizes'])
            group['aspect_ratio'] = max_dim / min_dim if min_dim > 0 else 1.0
            group['max_dim'] = max_dim
            
            # 计算填充率(面积/边界矩形面积)
            total_rect_area = sum(w * h for w, h in group['sizes'])
            group['fill_rate'] = total_area / total_rect_area if total_rect_area > 0 else 1.0
        else:
            group['aspect_ratio'] = 1.0
            group['fill_rate'] = 1.0
            group['max_dim'] = 0
        
        # 计算组内物体数量和平均大小
        group['item_count'] = len(group['sizes'])
        group['avg_size'] = group['area'] / group['item_count'] if group['item_count'] > 0 else 0
        
        print(f"组 {group['key']} 分析:")
        print(f"  - 面积: {group['area']}")
        print(f"  - 宽高比: {group['aspect_ratio']:.2f}")
        print(f"  - 填充率: {group['fill_rate']:.2f}")
        print(f"  - 物体数量: {group['item_count']}")
        print(f"  - 平均大小: {group['avg_size']:.2f}")
        
        sorted_groups.append(group)
    
    # 全局优化步骤2:优化组的处理顺序
    print(f"\n开始优化组的处理顺序...")
    
    # 1. 按最大尺寸降序排序
    sorted_by_max_dim = sorted(sorted_groups, key=lambda x: x['max_dim'], reverse=True)
    
    # 2. 使用间插策略优化处理顺序
    optimized_order = []
    while sorted_by_max_dim:
        # 添加最大的
        if sorted_by_max_dim:
            optimized_order.append(sorted_by_max_dim.pop(0))
        # 添加最小的
        if sorted_by_max_dim:
            optimized_order.append(sorted_by_max_dim.pop(-1))
    
    print(f"优化后的处理顺序:")
    for i, group in enumerate(optimized_order):
        print(f"  组 {i+1}: {group['key']}, 面积: {group['area']}")
    
    # 创建全局打包器
    packer = GlobalRectPacker(TextureSize, TextureSize)
    final_assignments = {}  # 记录每个组的布局信息
    
    # 处理所有组，但只进行布局规划，不实际放置图片
    for group_idx, group in enumerate(optimized_order):
        print(f"\n处理组 {group_idx+1}/{len(optimized_order)}: {group['key']}")
        
        # 步骤1:首先尝试以原始尺寸（不缩放）放入现有纹理
        texture_idx, positions, scale, _ = None, None, None, None
        try:
            texture_idx, positions, scale, _ = packer.can_fit_group(group, 1.0, existing_only=True)
            if positions:
                print(f"  成功规划到现有纹理 {texture_idx},不缩放")
            else:
                # 步骤2:如果现有纹理放不下,创建新纹理并尝试原始尺寸
                new_texture_idx = packer.add_texture()
                texture_idx, positions, scale, _ = packer.can_fit_group(group, 1.0, existing_only=False, 
                                                                                specific_texture=new_texture_idx)
                if positions:
                    print(f"  成功规划到新纹理 {new_texture_idx},不缩放")
                else:
                    # 步骤3:只有当新纹理也放不下时,才尝试缩放
                    # 修改缩放因子序列,每次使用0.5的幂次方（即每次缩小一半）
                    scale_factors = [0.5, 0.25, 0.125, 0.0625, 0.03125, 0.03125 * 0.5]
                    for scale_factor in scale_factors:
                        try:
                            texture_idx, positions, scale, _ = packer.can_fit_group(
                                group, scale_factor, existing_only=False)
                            if positions:
                                print(f"  成功规划到纹理 {texture_idx},缩放比例: {scale_factor}")
                                break
                        except Exception as e:
                            print(f"  尝试缩放比例 {scale_factor} 时出错:{e}")
                            print(traceback.format_exc())
        except Exception as e:
            print(f"  尝试规划组时出错:{e}")
            print(traceback.format_exc())
            
        # 仅记录布局信息，不实际放置图片
        if texture_idx is not None and positions:
            # 记录组分配到哪个纹理及其布局信息
            final_assignments[group['key']] = {
                'texture_idx': texture_idx,
                'scale': scale,
                'positions': positions,
                'group': group  # 保存组信息以便后续处理
            }
            print(f"  成功规划组 {group['key']} 到纹理 {texture_idx}")
            
            # 更新打包器的使用信息（但不真正放置图像）
            for i, pos in enumerate(positions):
                if pos is None:
                    continue
                w, h = group['sizes'][i]
                scaled_w = max(1, int(w * scale))
                scaled_h = max(1, int(h * scale))
                packer.used_positions[texture_idx].append((pos, (scaled_w, scaled_h)))
                packer.texture_remaining_space[texture_idx] -= scaled_w * scaled_h
        else:
            print(f"警告:无法为组 {group['key']} 规划位置,尝试分割组或减小至更小的尺寸...")
    
    # 打印最终分配情况
    print("\n最终规划情况汇总:")
    print("========================================")
    texture_groups = defaultdict(list)
    for group_key, assignment_data in final_assignments.items():
        texture_idx = assignment_data['texture_idx']
        texture_groups[texture_idx].append(group_key)
    
    for texture_idx, group_keys in texture_groups.items():
        print(f"纹理 {texture_idx} 包含 {len(group_keys)} 个组:")
        for key in group_keys:
            print(f"  - {key}")
    
    # 统计纹理利用率
    total_pixels = len(packer.textures) * TextureSize * TextureSize
    used_pixels = 0
    for texture_idx, positions in enumerate(packer.used_positions):
        # 创建一个布尔掩码,标记每个像素是否被使用
        usage_mask = np.zeros((TextureSize, TextureSize), dtype=bool)
        
        # 标记所有使用的像素
        for pos, size in positions:
            x, y = pos
            w, h = size
            usage_mask[y:y+h, x:x+w] = True
        
        # 计算真实使用的像素数量（避免重叠计算）
        texture_used = np.sum(usage_mask)
        efficiency = texture_used / (TextureSize * TextureSize) * 100
        print(f"纹理 {texture_idx} 利用率: {efficiency:.2f}%")
        used_pixels += texture_used
    
    overall_efficiency = used_pixels / total_pixels * 100
    print(f"整体空间利用率: {overall_efficiency:.2f}%")
    print("========================================")
    
    # 准备返回的结果数据
    results = []
    for group_key, assignment in final_assignments.items():
        group_info = assignment['group']
        texture_idx = assignment['texture_idx']
        scale = assignment['scale']
        positions = assignment['positions']
        
        # 为组中的每个物体创建结果项
        for i, info in enumerate(group_info['infos']):
            if i >= len(positions) or positions[i] is None:
                continue
                
            results.append({
                "mesh_id": info["mesh_id"],
                "Name": info["Name"],
                "texture_index": texture_idx,
                "new_lq": f"packed_lightmap_{texture_idx}",
                "new_bias_scale": [
                    (positions[i][0] + 1) / TextureSize,                           # bias_u (+1边界处理)
                    (positions[i][1] + 1) / TextureSize,                           # bias_v (+1边界处理)
                    (group_info['sizes'][i][0] * scale - 2) / TextureSize,         # scale_u (-2边界处理)
                    (group_info['sizes'][i][1] * scale - 2) / TextureSize          # scale_v (-2边界处理)
                ],
                "scale_factor": scale,
                "position": positions[i],
                "size": (int(group_info['sizes'][i][0] * scale), 
                         int(group_info['sizes'][i][1] * scale)),
                "group_info": group_info,  # 保存组信息以便后续处理
                "texture_info": info       # 保存纹理信息以便后续处理
            })
    
    # 创建空纹理数组
    empty_textures = []
    for _ in range(len(packer.textures)):
        empty_texture = np.zeros((TextureSize, TextureSize, 4), dtype=np.uint8)
        empty_textures.append(empty_texture)
    
    return results, empty_textures, final_assignments

def find_global_optimal_solution(groups):
    """
    寻找全局最优解，使用模拟退火算法代替全排列
    
    Args:
        groups: 按组整理的数据字典
        
    Returns:
        最优布局方案和空纹理列表
    """
    print("开始寻找全局最优解(使用模拟退火算法)...")
    
    # 步骤1：为每个组计算最佳分辨率
    group_list = []
    for key, group_infos in groups.items():
        textures = []
        sizes = []
        for info in group_infos:
            # 处理灯光贴图尺寸信息
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            
            try:
                # 获取尺寸
                with Image.open(lightmap_path) as img:
                    source_width, source_height = img.size
                
                # 计算原始区域的像素尺寸
                width = int(info["BiasScale"][2] * source_width)
                height = int(info["BiasScale"][3] * source_height) * 0.5
                sizes.append((width, height))
            except Exception as e:
                print(f"处理图片 {lightmap_name} 时出错: {e}")
                # 给一个默认尺寸
                sizes.append((64, 64))
        
        total_area = sum(w * h for w, h in sizes)
        
        # 将组信息存储起来
        group = {
            'key': key,
            'infos': group_infos,
            'sizes': sizes,
            'area': total_area,
            'item_count': len(sizes)
        }
        
        # 计算该组的最佳分辨率（在单独纹理中的最大缩放）
        optimal_scale = calculate_optimal_scale(group, TextureSize)
        group['optimal_scale'] = optimal_scale
        
        print(f"组 {key} 的最佳缩放比例: {optimal_scale}")
        group_list.append(group)
    
    # 按面积从大到小排序以提高初始解质量
    group_list.sort(key=lambda g: g['area'], reverse=True)
    
    # 步骤2：使用模拟退火算法寻找最优组合
    best_assignment, best_utilization, best_packer = simulated_annealing_optimization(group_list)
    
    print(f"\n最优方案: 空间利用率 {best_utilization:.2%}, 使用 {len(best_packer.textures)} 个纹理")
    
    # 准备结果
    results = []
    for group_key, assignment in best_assignment.items():
        group_info = assignment['group']
        texture_idx = assignment['texture_idx']
        scale = assignment['scale']
        positions = assignment['positions']
        
        for i, info in enumerate(group_info['infos']):
            if i >= len(positions) or positions[i] is None:
                continue
                
            results.append({
                "mesh_id": info["mesh_id"],
                "Name": info["Name"],
                "texture_index": texture_idx,
                "new_lq": f"packed_lightmap_{texture_idx}",
                "new_bias_scale": [
                    (positions[i][0] + 1) / TextureSize,                           # bias_u (+1边界处理)
                    (positions[i][1] + 1) / TextureSize,                           # bias_v (+1边界处理)
                    (group_info['sizes'][i][0] * scale - 2) / TextureSize,         # scale_u (-2边界处理)
                    (group_info['sizes'][i][1] * scale - 2) / TextureSize          # scale_v (-2边界处理)
                ],
                "scale_factor": scale,
                "position": positions[i],
                "size": (int(group_info['sizes'][i][0] * scale), 
                        int(group_info['sizes'][i][1] * scale)),
                "group_info": group_info,
                "texture_info": info
            })
    
    # 创建空纹理
    empty_textures = []
    for _ in range(len(best_packer.textures)):
        empty_texture = np.zeros((TextureSize, TextureSize, 4), dtype=np.uint8)
        empty_textures.append(empty_texture)
    
    # 在这里添加实际的纹理填充代码
    print("\n开始填充实际纹理数据...")
    # 遍历每个组分配
    for group_key, assignment in best_assignment.items():
        group_info = assignment['group']
        texture_idx = assignment['texture_idx']
        scale = assignment['scale']
        positions = assignment['positions']
        
        # 加载原始纹理
        textures = []
        for info in group_info['infos']:
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            texture = extract_lightmap(lightmap_path, info["BiasScale"])
            textures.append(texture)
        
        print(f"处理组 {group_key}，放置 {len(positions)} 个图像，缩放: {scale}")
        
        # 遍历组内每个图像
        for i, (info, texture) in enumerate(zip(group_info['infos'], textures)):
            if i >= len(positions) or positions[i] is None:
                continue
            
            # 获取位置和尺寸信息
            x, y = positions[i]
            original_w, original_h = group_info['sizes'][i]
            scaled_w = max(1, int(original_w * scale))
            scaled_h = max(1, int(original_h * scale))
            
            # 调整图像大小
            if scaled_w != texture.shape[1] or scaled_h != texture.shape[0]:
                resized_texture = cv2.resize(texture, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
            else:
                resized_texture = texture
            
            # 填充到目标纹理中
            try:
                empty_textures[texture_idx][y:y+scaled_h, x:x+scaled_w] = resized_texture
            except ValueError as e:
                print(f"错误: 无法填充图像到纹理中，位置:({x}, {y})，大小:({scaled_w}, {scaled_h})，纹理形状:{empty_textures[texture_idx].shape}")
                print(f"原始纹理形状:{texture.shape}, 缩放后形状:{resized_texture.shape}")
                print(f"错误信息: {e}")
    
    return results, empty_textures

def simulated_annealing_optimization(group_list, initial_temp=100.0, min_temp=0.1, cooling_rate=0.95, iterations_per_temp=50):
    """
    使用模拟退火算法寻找最优打包顺序
    
    Args:
        group_list: 组列表
        initial_temp: 初始温度
        min_temp: 最小温度（终止条件）
        cooling_rate: 冷却速率
        iterations_per_temp: 每个温度的迭代次数
        
    Returns:
        最优分配，利用率和打包器
    """
    print(f"开始模拟退火优化，共{len(group_list)}个组")
    
    # 创建初始解（按面积排序）
    current_solution = group_list.copy()
    
    # 评估初始解
    current_packer = GlobalRectPacker(TextureSize, TextureSize)
    current_assignment = {}
    current_utilization = evaluate_packing_solution(current_solution, current_packer, current_assignment)
    
    # 保存最佳解
    best_solution = current_solution.copy()
    best_packer = copy.deepcopy(current_packer)
    best_assignment = copy.deepcopy(current_assignment)
    best_utilization = current_utilization
    
    # 模拟退火主循环
    temperature = initial_temp
    iteration = 0
    no_improvement_count = 0
    max_no_improvement = 500  # 如果500次迭代没有改进，提前终止
    
    print(f"初始利用率: {best_utilization:.2%}")
    
    while temperature > min_temp and no_improvement_count < max_no_improvement:
        for _ in range(iterations_per_temp):
            iteration += 1
            
            # 生成新解（通过交换或移动操作）
            new_solution = current_solution.copy()
            
            # 随机选择扰动类型
            if random.random() < 0.5:
                # 交换两个组的位置
                if len(new_solution) >= 2:  # 确保至少有两个组可交换
                    i, j = random.sample(range(len(new_solution)), 2)
                    new_solution[i], new_solution[j] = new_solution[j], new_solution[i]
            else:
                # 移动一个组到新位置
                if len(new_solution) >= 2:  # 确保至少有两个位置可移动
                    old_idx = random.randrange(len(new_solution))
                    new_idx = random.randrange(len(new_solution))
                    item = new_solution.pop(old_idx)
                    new_solution.insert(new_idx, item)
            
            # 评估新解
            new_packer = GlobalRectPacker(TextureSize, TextureSize)
            new_assignment = {}
            new_utilization = evaluate_packing_solution(new_solution, new_packer, new_assignment)
            
            # 计算能量差
            delta_e = new_utilization - current_utilization
            
            # Metropolis准则：接受或拒绝新解
            if delta_e > 0 or random.random() < math.exp(delta_e / temperature):
                current_solution = new_solution
                current_packer = new_packer
                current_assignment = new_assignment
                current_utilization = new_utilization
                
                # 更新最佳解
                if current_utilization > best_utilization:
                    best_solution = current_solution.copy()
                    best_packer = copy.deepcopy(current_packer)
                    best_assignment = copy.deepcopy(current_assignment)
                    best_utilization = current_utilization
                    no_improvement_count = 0
                    print(f"[迭代 {iteration}] 找到更优方案: 利用率 {best_utilization:.2%}, 温度: {temperature:.2f}")
                else:
                    no_improvement_count += 1
            else:
                no_improvement_count += 1
            
            # 如果已达到很高的利用率，提前终止
            if best_utilization > 0.95:
                print(f"达到足够高的利用率({best_utilization:.2%})，提前终止搜索")
                break
        
        # 冷却
        temperature *= cooling_rate
        print(f"温度降至 {temperature:.2f}, 当前最优利用率: {best_utilization:.2%}")
        
        # 如果已达到很高的利用率，提前终止
        if best_utilization > 0.95:
            break
    
    print(f"模拟退火完成，共{iteration}次迭代，最终利用率: {best_utilization:.2%}，使用{len(best_packer.textures)}个纹理")
    return best_assignment, best_utilization, best_packer

def evaluate_packing_solution(group_order, packer, assignments):
    """
    评估打包方案的质量
    
    Args:
        group_order: 组的顺序
        packer: 打包器实例
        assignments: 存储分配结果的字典（会被修改）
        
    Returns:
        空间利用率
    """
    # 每个组尝试放入打包器
    for group in group_order:
        scale = group['optimal_scale']
        placed = False
        
        # 先尝试放入现有纹理
        for texture_idx in range(len(packer.textures)):
            texture_idx, positions, _, _ = packer.can_fit_group(group, scale, existing_only=True)
            if positions:
                # 成功放置，记录分配
                assignments[group['key']] = {
                    'texture_idx': texture_idx,
                    'scale': scale,
                    'positions': positions,
                    'group': group
                }
                
                # 更新使用信息
                for i, pos in enumerate(positions):
                    if pos is None:
                        continue
                    w, h = group['sizes'][i]
                    scaled_w = max(1, int(w * scale))
                    scaled_h = max(1, int(h * scale))
                    packer.used_positions[texture_idx].append((pos, (scaled_w, scaled_h)))
                    packer.texture_remaining_space[texture_idx] -= scaled_w * scaled_h
                
                placed = True
                break
        
        # 如果现有纹理放不下，创建新纹理
        if not placed:
            new_texture_idx = packer.add_texture()
            texture_idx, positions, _, _ = packer.can_fit_group(group, scale, specific_texture=new_texture_idx)
            
            if positions:
                # 成功放置，记录分配
                assignments[group['key']] = {
                    'texture_idx': texture_idx,
                    'scale': scale,
                    'positions': positions,
                    'group': group
                }
                
                # 更新使用信息
                for i, pos in enumerate(positions):
                    if pos is None:
                        continue
                    w, h = group['sizes'][i]
                    scaled_w = max(1, int(w * scale))
                    scaled_h = max(1, int(h * scale))
                    packer.used_positions[texture_idx].append((pos, (scaled_w, scaled_h)))
                    packer.texture_remaining_space[texture_idx] -= scaled_w * scaled_h
            
            else:
                # 无法放入新纹理，这不应该发生，因为新纹理是空的
                print(f"警告: 组 {group['key']} 即使使用其最佳缩放比例 {scale} 也无法放入新纹理")
    
    # 计算空间利用率
    total_pixels = len(packer.textures) * TextureSize * TextureSize
    used_pixels = 0
    for texture_idx, positions in enumerate(packer.used_positions):
        usage_mask = np.zeros((TextureSize, TextureSize), dtype=bool)
        for pos, size in positions:
            x, y = pos
            w, h = size
            usage_mask[y:y+h, x:x+w] = True
        texture_used = np.sum(usage_mask)
        used_pixels += texture_used
    
    utilization = used_pixels / total_pixels
    return utilization

def calculate_optimal_scale(group, texture_size):
    """
    计算一个组在单独放入空纹理时的最优缩放比例
    
    Args:
        group: 组信息
        texture_size: 纹理尺寸
        
    Returns:
        最优缩放比例
    """
    # 从1.0开始尝试，直到找到能放入的最大缩放比例
    scales = [1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625, 0.0078125, 0.00390625, 0.001953125, 0.0009765625]
    
    # 创建一个临时打包器
    packer = GlobalRectPacker(texture_size, texture_size)
    
    for scale in scales:
        # 缩放尺寸
        scaled_sizes = []
        for w, h in group['sizes']:
            scaled_w = max(1, int(w * scale))
            scaled_h = max(1, int(h * scale))
            scaled_sizes.append((scaled_w, scaled_h))
        
        # 尝试放置
        positions = packer.try_place_group_in_texture(0, scaled_sizes)
        if positions:
            # 找到可行的缩放比例
            return scale
    
    # 如果所有尝试都失败，返回最小缩放比例
    return scales[-1]

def pack_lightmaps(json_data, use_global_optimal=True):
    """
    打包灯光贴图
    
    Args:
        json_data: JSON数据
        use_global_optimal: 是否使用全局最优解算法，默认为True
    
    Returns:
        打包结果
    """
    # 确保BigLightmap文件夹存在
    os.makedirs(BigLightmapPath, exist_ok=True)
    
    # 先清空目标文件夹中的现有文件,防止干扰
    for old_file in BigLightmapPath.glob("packed_lightmap_*.png"):
        os.remove(old_file)
        print(f"删除旧文件: {old_file}")
    
    # 按Parameters分组
    groups = group_by_parameters(json_data)
    
    try:
        # 根据选择，使用不同的算法进行打包
        if use_global_optimal:
            print("使用模拟退火算法进行打包...")
            results, textures = find_global_optimal_solution(groups)
        else:
            print("使用传统算法进行打包...")
            results, textures = global_packing_optimization(groups)
        
        print(f"\n总共生成了 {len(textures)} 个纹理")
        
        # 保存所有生成的纹理
        for i, texture_array in enumerate(textures):
            # 保存完整的纹理
            save_path = Path.joinpath(BigLightmapPath, f"packed_lightmap_{i}.png")
            Image.fromarray(texture_array).save(save_path)
            
            # 提取alpha通道并单独保存
            alpha_channel = texture_array[:, :, 3]  # 获取alpha通道
            alpha_image = Image.fromarray(alpha_channel, mode='L')  # 创建单通道图像
            alpha_save_path = Path.joinpath(BigLightmapPath, f"packed_lightmap_{i}_skyao.png")
            alpha_image.save(alpha_save_path)
            
            print(f"保存纹理 {i} 成功，同时已保存其alpha通道到 {alpha_save_path.name}")
        
        return results
        
    except Exception as e:
        print(f"处理过程中出错:{str(e)}")
        raise

def update_json_data(json_data, new_lightmap_info):
    # 创建纹理索引计数
    texture_counts = {}
    
    for info in new_lightmap_info:
        mesh = json_data["Static Mesh"][info["mesh_id"]]
        texture_index = info["texture_index"]
        
        # 更新光照图名称
        new_lq = f"packed_lightmap_{texture_index}"
        mesh["LightMap"]["LQ"] = new_lq
        
        # 更新BiasScale
        mesh["LightMap"]["BiasScale"] = info["new_bias_scale"]
        
        # 记录使用情况
        if texture_index not in texture_counts:
            texture_counts[texture_index] = 0
        texture_counts[texture_index] += 1
        
        print(f"更新Mesh {info['Name']}:")
        print(f"- 纹理索引: {texture_index}")
        print(f"- 新光照图: {new_lq}")
        print(f"- 新BiasScale: {info['new_bias_scale']}")
    
    # 打印纹理使用统计
    print("\n更新后的纹理使用情况:")
    for tex_idx, count in texture_counts.items():
        print(f"纹理 {tex_idx}: 被 {count} 个物体使用")

def save_packing_results_to_json(results, groups_data, output_path=None):
    """将打包结果保存为JSON文件,按组记录每个物体的最终分配情况
    
    Args:
        results: 打包后的结果列表
        groups_data: 按组整理的数据字典
        output_path: 输出JSON文件路径,如果为None则使用默认路径
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path.joinpath(RootPath, f"lightmap_packing_results_{timestamp}.json")
    
    # 按组整理结果
    results_by_group = {}
    
    # 创建组键到对象的映射
    group_objects_map = {}
    for key, group_infos in groups_data.items():
        group_objects_map[key] = {info["mesh_id"]: info for info in group_infos}
    
    # 按组整理结果
    for result in results:
        mesh_id = result["mesh_id"]
        
        # 查找该对象所属的组
        for group_key, objects in group_objects_map.items():
            if mesh_id in objects:
                if str(group_key) not in results_by_group:
                    results_by_group[str(group_key)] = {"objects": []}
                
                # 添加对象信息
                results_by_group[str(group_key)]["objects"].append({
                    "mesh_id": mesh_id,
                    "name": result["Name"],
                    "final_lightmap": result["new_lq"],
                    "bias_scale": result["new_bias_scale"],
                    "scale_factor": result["scale_factor"],
                    "texture_index": result["texture_index"]
                })
                break
    
    # 创建最终JSON结构
    output_data = {
        "packing_results": results_by_group,
        "summary": {
            "total_groups": len(results_by_group),
            "total_objects": len(results),
            "timestamp": datetime.now().isoformat()
        }
    }
    
    # 写入JSON文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n打包结果已保存到: {output_path}")
    return output_path

def main():
    import argparse
    
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='灯光贴图打包工具')
    parser.add_argument('--algorithm', type=str, default='global', choices=['global', 'traditional'],
                        help='打包算法: global为模拟退火优化算法, traditional为传统算法')
    args = parser.parse_args()
    
    print("=== 灯光贴图打包工具 ===")
    print(f"使用算法: {args.algorithm}")
    use_global_optimal = args.algorithm == 'global'
    
    # 步骤1: 加载JSON数据
    print("\n[1/5] 加载JSON数据...")
    start_time = time.time()
    json_data = load_json_data()
    new_json_path = get_new_json_path()
    
    # 先保存一份JSON副本
    with open(new_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=4)
    
    step1_time = time.time() - start_time
    print(f"加载完成，并创建备份：{new_json_path}，耗时: {step1_time:.2f}秒")
    
    try:
        # 步骤2: 按组整理数据
        print("\n[2/5] 按组整理数据...")
        start_time = time.time()
        grouped_data = group_by_parameters(json_data)
        step2_time = time.time() - start_time
        print(f"整理了 {len(grouped_data)} 个组，耗时: {step2_time:.2f}秒")
        
        # 步骤3: 执行贴图打包
        print("\n[3/5] 执行贴图打包...")
        start_time = time.time()
        
        if use_global_optimal:
            print("使用全局最优解算法")
            packed_results, packed_textures, _ = find_global_optimal_solution(grouped_data)
        else:
            print("使用传统打包算法")
            packer = LightmapPacker(TextureSize, MIN_TEXTURE_SIZE)
            packed_results = traditional_lightmap_packing(packer, grouped_data)
            packed_textures = packer.current_textures
            
        step3_time = time.time() - start_time
        print(f"打包完成，得到 {len(packed_results)} 个对象的打包结果，耗时: {step3_time:.2f}秒")
        
        # 步骤4: 生成新的贴图
        print("\n[4/5] 生成新的贴图...")
        start_time = time.time()
        total_textures = len(packed_textures)
        for texture_idx, texture in enumerate(packed_textures):
            print(f"处理贴图 {texture_idx+1}/{total_textures}...")
            
            # 从RGBA数组转换为图像并保存
            img = Image.fromarray(texture)
            output_name = f"packed_lightmap_{texture_idx}.png"
            output_path = Path.joinpath(BigLightmapPath, output_name)
            img.save(output_path)
            print(f"已保存贴图: {output_path}")
        
        step4_time = time.time() - start_time
        print(f"生成了 {len(packed_textures)} 个新贴图，耗时: {step4_time:.2f}秒")
        
        # 步骤5: 更新JSON数据并保存
        print("\n[5/5] 更新JSON数据并保存...")
        start_time = time.time()
        
        # 保存打包结果到独立的JSON文件
        save_packing_results_to_json(packed_results, grouped_data)
        
        # 更新主JSON数据
        update_json_data(json_data, packed_results)
        
        # 保存更新后的JSON到新文件
        with open(new_json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4)
            
        step5_time = time.time() - start_time
        print(f"更新了JSON数据并保存至 {new_json_path}，耗时: {step5_time:.2f}秒")
        
        # 总结
        total_time = step1_time + step2_time + step3_time + step4_time + step5_time
        print("\n=== 处理完成 ===")
        print(f"总共处理了 {len(packed_results)} 个对象")
        print(f"生成了 {len(packed_textures)} 个打包贴图")
        print(f"总耗时: {total_time:.2f}秒")
    
        # 显示每个步骤占用的时间百分比
        print("\n时间分布:")
        print(f"- 加载JSON数据: {step1_time/total_time*100:.1f}%")
        print(f"- 按组整理数据: {step2_time/total_time*100:.1f}%")
        print(f"- 执行贴图打包: {step3_time/total_time*100:.1f}%")
        print(f"- 生成新贴图: {step4_time/total_time*100:.1f}%")
        print(f"- 更新JSON数据: {step5_time/total_time*100:.1f}%")
        
        print(f"\n新的JSON文件已保存为: {new_json_path}")
        print(f"新的光照图文件保存在当前目录")
        
    except Exception as e:
        print(f"处理过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 先添加一个简单的测试
    try:
        main()
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        traceback.print_exc()
