import os
from pathlib import Path
import json
import numpy as np
from PIL import Image
import math
import shutil
from datetime import datetime
import copy
import itertools
from collections import defaultdict
import traceback

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
        
        # 常规网格搜索 - 小步长（更精确但更慢）
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
                    if mask > 0:  # 如果有任何非零alpha值（表示已有内容）
                        can_place = False
                    
                    if can_place:
                        return (x, y)
        
        return None

    def can_fit_group(self, group, scale=1.0, existing_only=False, specific_texture=None):
        """尝试将一组纹理放入纹理中,优先保持原始分辨率
        
        参数:
            group: 需要放置的组
            scale: 初始缩放比例
            existing_only: 是否只检查现有纹理
            specific_texture: 指定尝试放入的特定纹理索引
        """
        # 获取组信息
        textures = group['textures']
        sizes = group['sizes']
        
        # 缩放因子序列（从大到小）
        scale_factors = [1.0, 0.5, 0.25, 0.125, 0.0625]
        
        # 如果指定了特定纹理,只尝试那个纹理
        if specific_texture is not None:
            existing_textures = [specific_texture]
        else:
            # 尝试所有现有纹理
            existing_textures = list(range(len(self.current_textures)))
        
        # 第一步：尝试以原始分辨率放入现有纹理
        current_scale = scale
        scaled_sizes = [(int(w * current_scale), int(h * current_scale)) for w, h in sizes]
        scaled_textures = self.get_scaled_textures(group, current_scale)
        
        for texture_idx in existing_textures:
            positions = self.try_place_group_in_texture(texture_idx, scaled_sizes)
            if positions:
                print(f"以原始分辨率放入现有纹理 {texture_idx}")
                return texture_idx, positions, current_scale, scaled_textures
        
        # 如果要求只使用现有纹理,在这里返回
        if existing_only:
            return None, None, scale, None
        
        # 第二步：如果无法放入现有纹理,尝试创建新纹理（仍然使用原始分辨率）
        if specific_texture is None:
            new_texture_idx = len(self.current_textures)
            self.add_new_texture()
            positions = self.try_place_group_in_texture(new_texture_idx, scaled_sizes)
            if positions:
                print(f"以原始分辨率放入新纹理 {new_texture_idx}")
                return new_texture_idx, positions, current_scale, scaled_textures
        
        # 第三步：如果新纹理也放不下,开始缩小分辨率
        for scale_factor in scale_factors[1:]:  # 跳过1.0,因为已经试过了
            current_scale = scale_factor
            scaled_sizes = [(int(w * current_scale), int(h * current_scale)) for w, h in sizes]
            scaled_textures = self.get_scaled_textures(group, current_scale)
            
            # 检查最小尺寸限制
            if any(w < 1 or h < 1 for w, h in scaled_sizes):
                print(f"缩放比例 {current_scale} 导致某些纹理小于1像素,跳过")
                continue
            
            print(f"尝试缩放比例 {current_scale}")
            
            # 先检查是否能放入现有纹理（回头检查）
            for texture_idx in existing_textures:
                positions = self.try_place_group_in_texture(texture_idx, scaled_sizes)
                if positions:
                    print(f"缩小到 {current_scale} 后成功放入现有纹理 {texture_idx}")
                    return texture_idx, positions, current_scale, scaled_textures
            
            # 如果现有纹理都放不下,尝试放入新纹理
            if specific_texture is None:
                # 注意：我们可能已经添加了一个新纹理,所以需要确认索引
                new_texture_idx = len(self.current_textures) - 1
                if new_texture_idx < 0:
                    new_texture_idx = self.add_new_texture()
                
                positions = self.try_place_group_in_texture(new_texture_idx, scaled_sizes)
                if positions:
                    print(f"缩小到 {current_scale} 后放入新纹理 {new_texture_idx}")
                    return new_texture_idx, positions, current_scale, scaled_textures
                
                # 如果第一张新纹理都放不下,可能需要再创建一张新纹理试试
                new_texture_idx = self.add_new_texture()
                positions = self.try_place_group_in_texture(new_texture_idx, scaled_sizes)
                if positions:
                    print(f"缩小到 {current_scale} 后放入另一张新纹理 {new_texture_idx}")
                    return new_texture_idx, positions, current_scale, scaled_textures
        
        # 如果所有尝试都失败,返回失败
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
        """尝试在指定纹理中放置一组物体,确保不会重叠"""
        # 创建一个占用图,标记已使用的区域
        occupation_map = np.zeros((self.texture_size, self.texture_size), dtype=bool)
        
        # 标记现有的所有使用区域
        for pos, size in self.current_positions[texture_idx]:
            x, y = pos
            w, h = size
            occupation_map[y:y+h, x:x+w] = True
        
        # 按面积从大到小排序物体
        sizes_with_index = [(i, size) for i, size in enumerate(sizes)]
        sizes_with_index.sort(key=lambda x: x[1][0] * x[1][1], reverse=True)
        
        positions = [None] * len(sizes)
        
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
                    if x_right + w <= self.texture_size:
                        if not np.any(occupation_map[prev_y:prev_y+h, x_right:x_right+w]):
                            pos = (x_right, prev_y)
                            break
                    
                    # 尝试下方放置
                    y_bottom = prev_y + prev_h
                    if y_bottom + h <= self.texture_size:
                        if not np.any(occupation_map[y_bottom:y_bottom+h, prev_x:prev_x+w]):
                            pos = (prev_x, y_bottom)
                            break
            
            # 如果没找到紧贴的位置,按网格搜索
            if pos is None:
                # 更高效的网格搜索,从(0,0)开始
                for y in range(0, self.texture_size - h + 1):
                    for x in range(0, self.texture_size - w + 1):
                        if not np.any(occupation_map[y:y+h, x:x+w]):
                            pos = (x, y)
                            break
                    if pos:
                        break
            
            if pos:
                positions[i] = pos
                x, y = pos
                # 标记占用区域
                occupation_map[y:y+h, x:x+w] = True
            else:
                # 如果任何一个物体放不下,整个放置失败
                return None
        
        # 最终验证:确保所有位置都有效且不重叠
        if None in positions:
            return None
            
        # 验证没有重叠
        for i, pos1 in enumerate(positions):
            x1, y1 = pos1
            w1, h1 = sizes[i]
            for j, pos2 in enumerate(positions):
                if i == j:
                    continue
                x2, y2 = pos2
                w2, h2 = sizes[j]
                if (x1 < x2 + w2 and x1 + w1 > x2 and
                    y1 < y2 + h2 and y1 + h1 > y2):
                    # 检测到重叠,返回失败
                    return None
        
        return positions

    def place_group(self, group, texture_idx, positions, scale, scaled_textures=None):
        """将组放置到指定纹理,返回结果"""
        group_results = []
        
        # 如果没有提供缩放后的纹理,需要先生成
        if scaled_textures is None:
            scaled_textures = []
            for texture, size in zip(group['textures'], group['sizes']):
                scaled_w = int(size[0] * scale)
                scaled_h = int(size[1] * scale)
                img = Image.fromarray(texture)
                scaled_img = img.resize((scaled_w, scaled_h), Image.NEAREST)
                scaled_textures.append(np.array(scaled_img))
        
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
            self.current_positions[texture_idx][0][1][0] -= scaled_width * scaled_height
            
            # 计算新的BiasScale
            new_bias_scale = [
                x / self.texture_size,              # x起始位置比例
                y / self.texture_size,             # y起始位置比例
                scaled_width / self.texture_size,   # 宽度占比
                scaled_height / self.texture_size  # 高度占比
            ]
            
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
            scale: 缩放比例,默认为1.0（不缩放）
            existing_only: 是否只检查现有纹理,不创建新纹理
            specific_texture: 指定尝试放入的特定纹理索引
            
        返回:
            (texture_idx, positions, scale, scaled_textures): 成功时返回纹理索引、位置列表、缩放比例和缩放后的纹理
            如果无法放入,则返回(None, None, scale, None)
        """
        # 获取组中的纹理和尺寸
        textures = group['textures']
        sizes = group['sizes']
        
        # 创建缩放后的尺寸和纹理
        scaled_sizes = []
        scaled_textures = []
        
        for i, (w, h) in enumerate(sizes):
            # 确保最小尺寸
            scaled_w = max(1, int(w * scale))
            scaled_h = max(1, int(h * scale))
            scaled_sizes.append((scaled_w, scaled_h))
            
            # 缩放纹理图像
            if scale != 1.0:
                texture = textures[i]
                # 确保纹理是numpy数组
                if not isinstance(texture, np.ndarray):
                    texture = np.array(texture)
                # 使用PIL进行缩放
                img = Image.fromarray(texture)
                scaled_img = img.resize((scaled_w, scaled_h), Image.NEAREST)
                scaled_texture = np.array(scaled_img)
                scaled_textures.append(scaled_texture)
            else:
                # 如果不缩放,直接使用原始纹理
                scaled_textures.append(textures[i])
        
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
                return texture_idx, positions, scale, scaled_textures
        
        # 如果要求只使用现有纹理或指定了特定纹理但失败,直接返回
        if existing_only or specific_texture is not None:
            return None, None, scale, None
        
        # 否则,创建新的纹理并尝试放置
        new_texture_idx = self.add_texture()
        positions = self.try_place_group_in_texture(new_texture_idx, scaled_sizes)
        if positions:
            return new_texture_idx, positions, scale, scaled_textures
        
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
                
                # 如果紧贴放置失败,尝试网格搜索
                if pos is None:
                    for y in range(0, self.height - h + 1):
                        for x in range(0, self.width - w + 1):
                            if not np.any(occupation_map[y:y+h, x:x+w]):
                                pos = (x, y)
                                break
                        if pos:
                            break
            
            if pos:
                positions[i] = pos
                x, y = pos
                # 标记占用区域
                occupation_map[y:y+h, x:x+w] = True
            else:
                # 一个物体放不下,整个放置失败
                return None
        
        # 验证所有位置都有效
        if None in positions:
            return None
        
        return positions
        
    def place_group(self, group, texture_idx, positions, scale=1.0, scaled_textures=None):
        """
        将组放入指定纹理中的指定位置
        
        参数:
            group: 要放置的组
            texture_idx: 目标纹理索引
            positions: 放置位置列表
            scale: 缩放比例
            scaled_textures: 预先缩放的纹理,如果为None则需要即时计算
        """
        if scaled_textures is None:
            # 如果没有提供缩放纹理,需要计算
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
    # 使用PIL打开图片
    original = Image.open(lightmap_path)
    
    # 转换为NumPy数组
    img_array = np.array(original)
    
    # 计算提取区域
    x = int(bias_scale[0] * original.width)
    y = int(bias_scale[1] * original.height * 0.5)
    width = int(bias_scale[2] * original.width)
    height = int(bias_scale[3] * original.height * 0.5)
    
    # 直接提取像素数据
    region_array = img_array[y:y+height, x:x+width].copy()
    return region_array, (width, height)

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
        优化后的打包结果和纹理列表
    """
    # 首先获取所有组的信息
    sorted_groups = []
    for key, group_infos in groups.items():
        total_area = 0
        textures = []
        sizes = []
        for info in group_infos:
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            texture_array, size = extract_lightmap(lightmap_path, info["BiasScale"])
            total_area += size[0] * size[1]
            textures.append(texture_array)
            sizes.append(size)
        sorted_groups.append({
            'key': key,
            'infos': group_infos,
            'area': total_area,
            'textures': textures,
            'sizes': sizes
        })

    print(f"总共有 {len(sorted_groups)} 个组需要打包")

    # 全局优化步骤1:评估每个组的特征
    for group in sorted_groups:
        # 计算组的宽高比和填充率
        total_width = sum(size[0] for size in group['sizes'])
        max_height = max(size[1] for size in group['sizes']) if group['sizes'] else 0
        theoretical_area = total_width * max_height
        group['aspect_ratio'] = total_width / max_height if max_height > 0 else 1
        group['fill_rate'] = group['area'] / theoretical_area if theoretical_area > 0 else 1
        # 计算最大尺寸
        if group['sizes']:
            max_dimensions = [max(size[0], size[1]) for size in group['sizes']]
            group['max_dim'] = max(max_dimensions)
        else:
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
    final_textures = []
    final_assignments = {}  # 记录每个组分配到哪个纹理
    results = []
    
    # 处理所有组
    for group_idx, group in enumerate(optimized_order):
        print(f"\n处理组 {group_idx+1}/{len(optimized_order)}: {group['key']}")
        
        # 步骤1:首先尝试以原始尺寸（不缩放）放入现有纹理
        texture_idx, positions, scale, scaled_textures = None, None, None, None
        try:
            try:
                texture_idx, positions, scale, scaled_textures = packer.can_fit_group(group, 1.0, existing_only=True)
                if positions:
                    print(f"  成功放置到现有纹理 {texture_idx},不缩放")
                else:
                    # 步骤2:如果现有纹理放不下,创建新纹理并尝试原始尺寸
                    new_texture_idx = packer.add_texture()
                    texture_idx, positions, scale, scaled_textures = packer.can_fit_group(group, 1.0, existing_only=False, 
                                                                                    specific_texture=new_texture_idx)
                    if positions:
                        print(f"  成功放置到新纹理 {new_texture_idx},不缩放")
                    else:
                        # 步骤3:只有当新纹理也放不下时,才尝试缩放
                        # 修改缩放因子序列,每次使用0.5的幂次方（即每次缩小一半）
                        scale_factors = [0.5, 0.25, 0.125, 0.0625, 0.03125, 0.03125 * 0.5]
                        for scale_factor in scale_factors:
                            try:
                                texture_idx, positions, scale, scaled_textures = packer.can_fit_group(
                                    group, scale_factor, existing_only=False)
                                if positions:
                                    print(f"  成功放置到纹理 {texture_idx},缩放比例: {scale_factor}")
                                    break
                            except Exception as e:
                                print(f"  尝试缩放比例 {scale_factor} 时出错:{e}")
                                # 打印详细的异常信息
                                print(traceback.format_exc())
            except Exception as e:
                print(f"  尝试放置组时出错:{e}")
                # 打印详细的异常信息
                print(traceback.format_exc())
                
            # 实际放置组
            if texture_idx is not None and positions:
                try:
                    packer.place_group(group, texture_idx, positions, scale, scaled_textures)
                    # 记录组分配到哪个纹理
                    final_assignments[group['key']] = {
                        'texture_idx': texture_idx,
                        'scale': scale,
                        'positions': positions
                    }
                    print(f"  成功将组 {group['key']} 放置到纹理 {texture_idx}")
                except Exception as e:
                    print(f"  放置组时出错:{e}")
                    # 打印详细的异常信息
                    print(traceback.format_exc())
                    continue
            else:
                print(f"警告:无法放置组 {group['key']},尝试分割组或减小至更小的尺寸...")
        except Exception as e:
            print(f"  处理组时出错:{e}")
            # 打印详细的异常信息
            print(traceback.format_exc())
    
    # 打印最终分配情况
    print("\n最终分配情况汇总:")
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
    
    # 在函数结束前,将final_assignments转换为results格式
    results = []
    for group_key, assignment in final_assignments.items():
        # 找到对应的组信息
        group_info = None
        for group in sorted_groups:
            if group['key'] == group_key:
                group_info = group
                break
        
        if not group_info:
            continue
            
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
                    positions[i][0] / TextureSize,
                    positions[i][1] / TextureSize,
                    group_info['sizes'][i][0] * scale / TextureSize,
                    group_info['sizes'][i][1] * scale / TextureSize
                ],
                "scale_factor": scale,
                "position": positions[i],
                "size": (int(group_info['sizes'][i][0] * scale), 
                         int(group_info['sizes'][i][1] * scale))
        })
    
    return results, packer.textures

def pack_lightmaps(json_data):
    # 确保BigLightmap文件夹存在
    os.makedirs(BigLightmapPath, exist_ok=True)
    
    # 先清空目标文件夹中的现有文件,防止干扰
    for old_file in BigLightmapPath.glob("packed_lightmap_*.png"):
        os.remove(old_file)
        print(f"删除旧文件: {old_file}")
    
    # 按Parameters分组
    groups = group_by_parameters(json_data)
    
    try:
        # 使用全局优化算法打包
        results, textures = global_packing_optimization(groups)
        
        print(f"\n总共生成了 {len(textures)} 个纹理")
        
        # 保存所有生成的纹理
        for i, texture_array in enumerate(textures):
            save_path = Path.joinpath(BigLightmapPath, f"packed_lightmap_{i}.png")
            Image.fromarray(texture_array).save(save_path)
            print(f"保存纹理 {i} 成功")
        
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
    # 加载JSON数据并创建副本
    json_data = load_json_data()
    new_json_path = get_new_json_path()
    
    # 先保存一份JSON副本
    with open(new_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=4)
    
    print(f"已创建JSON备份文件:{new_json_path}")
    
    try:
        # 获取分组信息
        groups = group_by_parameters(json_data)
        
        # 处理所有光照图
        packed_results = pack_lightmaps(json_data)
        
        # 保存打包结果到JSON文件
        save_packing_results_to_json(packed_results, groups)
        
        # 更新JSON数据
        update_json_data(json_data, packed_results)
        
        # 保存更新后的JSON到新文件
        with open(new_json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4)
        
        print(f"处理完成!新的JSON文件已保存为:{new_json_path}")
        print(f"新的光照图文件保存在:{BigLightmapPath}")
        
    except Exception as e:
        print(f"处理过程中出错:{str(e)}")
        raise

if __name__ == "__main__":
    # 先添加一个简单的测试
    try:
        # 创建一个测试组
        test_group = {
            'key': 'test_group',
            'textures': [np.zeros((100, 100, 4), dtype=np.uint8)],
            'sizes': [(100, 100)],
            'infos': [{'id': 'test'}]
        }
        
        # 创建打包器并测试
        print("开始测试GlobalRectPacker类...")
        test_packer = GlobalRectPacker(512, 512)
        
        # 测试can_fit_group方法
        print("测试can_fit_group方法...")
        texture_idx, positions, scale, scaled_textures = test_packer.can_fit_group(test_group)
        print(f"返回值: texture_idx={texture_idx}, positions={positions}, scale={scale}")
        
        # 测试place_group方法
        if texture_idx is not None and positions:
            print("测试place_group方法...")
            test_packer.place_group(test_group, texture_idx, positions, scale, scaled_textures)
            print("place_group测试成功")
        
        print("GlobalRectPacker测试通过,继续执行主程序")
        # 现在执行原始的主程序代码
        main()
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        traceback.print_exc()
