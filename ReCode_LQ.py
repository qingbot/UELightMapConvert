import os
from pathlib import Path
import json
import numpy as np
from PIL import Image
import math
import shutil
from datetime import datetime

TextureSize = 2048

RootPath = Path("C:/chaos_integrated_tools/data_analysis/scene")
LightmapPath = Path.joinpath(RootPath, "light/light_map")
BigLightmapPath = Path.joinpath(LightmapPath, "BigLightmap")
JsonPath = Path.joinpath(RootPath, "current_scene_data_source.json")
MinTextureSize = 16

# 新增：获取新JSON文件的路径
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
        
        # 如果没有找到位置，创建新的纹理
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
                    # 如果当前纹理放不下，创建新的纹理
                    new_texture = np.zeros((self.texture_size, self.texture_size, 4), dtype=np.uint8)
                    new_texture[0:size[1], 0:size[0]] = texture
                    temp_textures.append(new_texture)
                    temp_positions.append([((0, 0), size)])
                    current_texture_index = len(temp_textures) - 1
                    positions.append((current_texture_index, (0, 0)))
            
            # 如果所有纹理都成功放置，更新实际状态
            self.current_textures = temp_textures
            self.current_positions = temp_positions
            success = True
            
        except Exception as e:
            print(f"打包过程中出错：{str(e)}")
            success = False
        
        if success:
            return True, (positions, scale_factor)
        return False, None

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

def pack_all_groups(groups):
    """尝试将所有组打包到尽可能少的纹理中，确保每个组的所有物体都在同一个纹理中"""
    # 按照总面积对组进行排序（面积大的先处理）
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
    sorted_groups.sort(key=lambda x: x['area'], reverse=True)

    # 结果列表
    results = []
    
    # 用于存储每个纹理的信息
    textures = []  # 存储纹理图像数据
    used_positions = []  # 存储每个纹理已使用的位置
    
    # 记录组分配情况
    group_assignments = {}  # 记录每个组被分配到的纹理
    
    # 按组处理物体
    for group in sorted_groups:
        print(f"\n开始处理组 {group['key']}...")
        print(f"组内物体数量: {len(group['infos'])}")
        
        best_scale = 1.0
        best_texture_index = None
        best_positions = None
        
        # 新增：调试输出每个物体的尺寸
        print("组内物体尺寸:")
        for i, size in enumerate(group['sizes']):
            print(f"  物体 {group['infos'][i]['Name']}: {size[0]}x{size[1]}")
        
        # 1. 尝试将整组放入已有的纹理中（不缩放）
        for texture_index in range(len(textures)):
            # 复制当前纹理的已用位置列表，用于临时测试
            temp_used_positions = [pos for pos in used_positions[texture_index]]
            positions = []
            can_fit_all = True
            
            # 检查组内所有物体是否都能放入这个纹理
            for i, (texture_array, size) in enumerate(zip(group['textures'], group['sizes'])):
                can_fit, position = can_fit_in_texture(textures[texture_index], 
                                                     temp_used_positions, 
                                                     size)
                if can_fit:
                    positions.append(position)
                    # 立即更新临时已用位置列表，确保后续物体不会与此位置重叠
                    temp_used_positions.append(((position[0], position[1]), size))
                    print(f"  物体 {group['infos'][i]['Name']} 可以放入纹理 {texture_index} 位置 {position}")
                else:
                    can_fit_all = False
                    print(f"  物体 {group['infos'][i]['Name']} 无法放入纹理 {texture_index}")
                    break
            
            if can_fit_all:
                best_texture_index = texture_index
                best_positions = positions
                best_scale = 1.0
                print(f"组 {group['key']} 完整放入现有纹理 {texture_index}")
                break
        
        # 2. 如果无法放入现有纹理，创建新纹理
        if best_texture_index is None:
            # 创建新纹理
            new_texture = np.zeros((TextureSize, TextureSize, 4), dtype=np.uint8)
            textures.append(new_texture)
            used_positions.append([])
            texture_index = len(textures) - 1
            print(f"为组 {group['key']} 创建新纹理 {texture_index}")
            
            # 复制新纹理的已用位置列表，用于临时测试
            temp_used_positions = []
            positions = []
            can_fit_all = True
            
            # 检查是否能放入新纹理（不缩放）
            for i, (texture_array, size) in enumerate(zip(group['textures'], group['sizes'])):
                # 使用简单排列策略
                if not temp_used_positions:  # 第一个物体放左上角
                    position = (0, 0)
                else:
                    # 尝试沿着x轴排列
                    last_pos, last_size = temp_used_positions[-1]
                    next_x = last_pos[0] + last_size[0]
                    if next_x + size[0] <= TextureSize:  # 当前行能放下
                        position = (next_x, last_pos[1])
                    else:  # 需要换行
                        # 找当前行的最大高度
                        max_height = 0
                        for pos, sz in temp_used_positions:
                            if pos[1] == last_pos[1]:  # 同一行
                                max_height = max(max_height, sz[1])
                        position = (0, last_pos[1] + max_height)
                        # 检查是否超出高度限制
                        if position[1] + size[1] > TextureSize:
                            can_fit_all = False
                            print(f"  物体 {group['infos'][i]['Name']} 放不下，超出纹理高度")
                            break
                
                # 检查位置是否有效
                if position[0] + size[0] > TextureSize or position[1] + size[1] > TextureSize:
                    can_fit_all = False
                    print(f"  物体 {group['infos'][i]['Name']} 放不下，超出纹理边界")
                    break
                
                # 检查是否与已分配位置冲突
                has_conflict = False
                for pos, sz in temp_used_positions:
                    if (position[0] < pos[0] + sz[0] and position[0] + size[0] > pos[0] and
                        position[1] < pos[1] + sz[1] and position[1] + size[1] > pos[1]):
                        has_conflict = True
                        print(f"  物体 {group['infos'][i]['Name']} 与已分配位置冲突")
                        break
                
                if has_conflict:
                    can_fit_all = False
                    break
                
                positions.append(position)
                temp_used_positions.append((position, size))
                print(f"  物体 {group['infos'][i]['Name']} 放置在位置 {position}")
            
            if can_fit_all:
                best_texture_index = texture_index
                best_positions = positions
                best_scale = 1.0
                print(f"组 {group['key']} 以原始尺寸放入新纹理 {texture_index}")
            else:
                # 3. 如果新纹理也放不下，尝试缩放整个组
                # 尝试几种常用的缩放比例: 0.5, 0.25, 0.125...
                for scale_factor in [0.5, 0.25, 0.125, 0.0625]:
                    print(f"尝试以 {scale_factor} 比例缩放组 {group['key']}")
                    
                    # 计算缩放后的尺寸
                    scaled_sizes = [(int(w * scale_factor), int(h * scale_factor)) 
                                   for w, h in group['sizes']]
                    
                    # 验证最小尺寸
                    if any(w < MinTextureSize or h < MinTextureSize for w, h in scaled_sizes):
                        print(f"  比例 {scale_factor} 太小，会导致某些物体小于最小纹理尺寸 {MinTextureSize}")
                        continue
                    
                    # 复位临时变量
                    temp_used_positions = []
                    positions = []
                    can_fit_all = True
                    
                    # 使用同样的位置分配策略
                    for i, scaled_size in enumerate(scaled_sizes):
                        if not temp_used_positions:  # 第一个物体放左上角
                            position = (0, 0)
                        else:
                            # 尝试沿着x轴排列
                            last_pos, last_size = temp_used_positions[-1]
                            next_x = last_pos[0] + last_size[0]
                            if next_x + scaled_size[0] <= TextureSize:  # 当前行能放下
                                position = (next_x, last_pos[1])
                            else:  # 需要换行
                                # 找当前行的最大高度
                                max_height = 0
                                for pos, sz in temp_used_positions:
                                    if pos[1] == last_pos[1]:  # 同一行
                                        max_height = max(max_height, sz[1])
                                position = (0, last_pos[1] + max_height)
                                # 检查是否超出高度限制
                                if position[1] + scaled_size[1] > TextureSize:
                                    can_fit_all = False
                                    break
                        
                        # 检查位置是否有效
                        if position[0] + scaled_size[0] > TextureSize or position[1] + scaled_size[1] > TextureSize:
                            can_fit_all = False
                            break
                        
                        positions.append(position)
                        temp_used_positions.append((position, scaled_size))
                        print(f"  物体 {group['infos'][i]['Name']} 缩放后放置在位置 {position}")
                    
                    if can_fit_all:
                        best_texture_index = texture_index
                        best_positions = positions
                        best_scale = scale_factor
                        print(f"组 {group['key']} 以 {scale_factor} 比例放入新纹理 {texture_index}")
                        break
        
        # 如果找不到合适的位置，抛出异常
        if best_texture_index is None:
            raise Exception(f"无法处理组 {group['key']}, 即使在最小缩放比例下也无法容纳")
        
        # 更新纹理和已用位置信息
        current_texture = textures[best_texture_index]
        
        # 将组放入选定的纹理
        for i, (position, texture_array, size) in enumerate(zip(best_positions, group['textures'], group['sizes'])):
            # 获取原始图像信息
            info = group['infos'][i]
            lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
            lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
            
            with Image.open(lightmap_path) as img:
                source_width, source_height = img.size
            
            # 计算原始区域的像素尺寸
            original_width = int(info["BiasScale"][2] * source_width)
            original_height = int(info["BiasScale"][3] * source_height) * 0.5
            
            # 计算缩放后的尺寸
            scaled_width = int(original_width * best_scale)
            scaled_height = int(original_height * best_scale)
            
            # 如果需要缩放，重新调整纹理
            if best_scale < 1.0:
                # 将原始纹理缩放到新尺寸
                scaled_img = Image.fromarray(texture_array).resize((scaled_width, scaled_height), Image.NEAREST)
                scaled_texture = np.array(scaled_img)
            else:
                scaled_texture = texture_array
            
            # 将纹理放入目标位置
            x, y = position
            # 确保不会超出边界
            if y + scaled_height > TextureSize or x + scaled_width > TextureSize:
                print(f"警告：物体 {info['Name']} 位置 ({x}, {y}) 加上尺寸 {scaled_width}x{scaled_height} 将超出纹理边界")
                continue
                
            # 检查是否与已放置区域重叠
            overlap = False
            for (pos, sz) in used_positions[best_texture_index]:
                if (x < pos[0] + sz[0] and x + scaled_width > pos[0] and
                    y < pos[1] + sz[1] and y + scaled_height > pos[1]):
                    overlap = True
                    print(f"警告：物体 {info['Name']} 位置 ({x}, {y}) 与已放置区域重叠")
                    break
            
            if overlap:
                continue
                
            current_texture[y:y+scaled_height, x:x+scaled_width] = scaled_texture
            # 记录已使用的位置
            used_positions[best_texture_index].append(((x, y), (scaled_width, scaled_height)))
            
            # 计算新的BiasScale
            new_bias_scale = [
                x / TextureSize,              # x起始位置比例
                y / TextureSize,              # y起始位置比例
                scaled_width / TextureSize,   # 宽度占比
                scaled_height / TextureSize   # 高度占比
            ]
            
            # 添加到结果
            results.append({
                "mesh_id": info["mesh_id"],
                "Name": info["Name"],
                "texture_index": best_texture_index,
                "new_lq": f"packed_lightmap_{best_texture_index}",
                "new_bias_scale": new_bias_scale,
                "scale_factor": best_scale,
                "position": (x, y),
                "size": (scaled_width, scaled_height)
            })
            
            # 打印详细信息
            print(f"物体 {info['Name']} 成功放置:")
            print(f"  原始图像尺寸: {source_width}x{source_height}")
            print(f"  缩放比例: {best_scale}")
            print(f"  缩放后尺寸: {scaled_width}x{scaled_height}")
            print(f"  在纹理 {best_texture_index} 中的位置: ({x}, {y})")
            print(f"  新的BiasScale: {new_bias_scale}")
        
        # 记录该组被分配到的纹理
        group_assignments[group['key']] = best_texture_index
    
    # 打印汇总信息
    print("\n\n最终分配情况汇总:")
    print("========================================")
    texture_groups = {}
    for group_key, texture_idx in group_assignments.items():
        if texture_idx not in texture_groups:
            texture_groups[texture_idx] = []
        texture_groups[texture_idx].append(group_key)
        print(f"组 {group_key} -> 纹理 packed_lightmap_{texture_idx}")
    
    print("\n每个纹理包含的组:")
    for texture_idx, group_keys in texture_groups.items():
        print(f"纹理 {texture_idx} 包含 {len(group_keys)} 个组:")
        for key in group_keys:
            print(f"  - {key}")
    print("========================================")
    
    return results, textures

# 辅助函数：检查纹理是否能放入指定位置
def can_fit_in_texture(texture_data, used_positions, size):
    texture_size = texture_data.shape[0]
    
    # 按行优先策略尝试放置
    for y in range(0, texture_size - size[1] + 1, size[1]):
        for x in range(0, texture_size - size[0] + 1, size[0]):
            # 检查是否与已使用的区域重叠
            can_place = True
            for (pos, sz) in used_positions:
                # 矩形重叠检测
                if (x < pos[0] + sz[0] and x + size[0] > pos[0] and
                    y < pos[1] + sz[1] and y + size[1] > pos[1]):
                    can_place = False
                    break
            
            if can_place:
                return True, (x, y)
    
    return False, None

def pack_lightmaps(json_data):
    # 确保BigLightmap文件夹存在
    os.makedirs(BigLightmapPath, exist_ok=True)
    
    # 先清空目标文件夹中的现有文件，防止干扰
    for old_file in BigLightmapPath.glob("packed_lightmap_*.png"):
        os.remove(old_file)
        print(f"删除旧文件: {old_file}")
    
    # 按Parameters分组
    groups = group_by_parameters(json_data)
    
    try:
        # 尝试打包所有组
        results, textures = pack_all_groups(groups)
        
        print(f"\n总共生成了 {len(textures)} 个纹理")
        
        # 保存所有生成的纹理，添加更多的验证信息
        for i, texture_array in enumerate(textures):
            save_path = Path.joinpath(BigLightmapPath, f"packed_lightmap_{i}.png")
            
            # 检查纹理数组是否有效
            if texture_array.shape[0] != TextureSize or texture_array.shape[1] != TextureSize:
                print(f"警告：纹理 {i} 尺寸异常: {texture_array.shape}")
            
            # 检查纹理是否为空（全黑）
            if np.sum(texture_array) == 0:
                print(f"警告：纹理 {i} 可能是空的（全黑）")
            
            # 保存并验证
            Image.fromarray(texture_array).save(save_path)
            if os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                print(f"保存纹理 {i} 成功，文件大小: {file_size/1024:.1f}KB")
            else:
                print(f"错误：纹理 {i} 保存失败！")
        
        # 验证所有文件是否都已创建
        expected_files = [f"packed_lightmap_{i}.png" for i in range(len(textures))]
        actual_files = [f.name for f in BigLightmapPath.glob("packed_lightmap_*.png")]
        
        print("\n文件验证:")
        print(f"期望创建的文件数量: {len(expected_files)}")
        print(f"实际创建的文件数量: {len(actual_files)}")
        
        missing_files = set(expected_files) - set(actual_files)
        if missing_files:
            print(f"警告：以下文件未成功创建: {missing_files}")
        
        # 打印结果详情以进行调试
        texture_counts = {}
        for result in results:
            tex_idx = result["texture_index"]
            if tex_idx not in texture_counts:
                texture_counts[tex_idx] = 0
            texture_counts[tex_idx] += 1
            print(f"物体 {result['Name']} -> 纹理 {result['new_lq']} (索引: {tex_idx})")
        
        print("\n每个纹理的物体数量:")
        for tex_idx, count in texture_counts.items():
            print(f"纹理 {tex_idx}: {count} 个物体")
        
        return results
        
    except Exception as e:
        print(f"处理过程中出错：{str(e)}")
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
    """将打包结果保存为JSON文件，按组记录每个物体的最终分配情况
    
    Args:
        results: 打包后的结果列表
        groups_data: 按组整理的数据字典
        output_path: 输出JSON文件路径，如果为None则使用默认路径
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
    
    print(f"已创建JSON备份文件：{new_json_path}")
    
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
        
        print(f"处理完成！新的JSON文件已保存为：{new_json_path}")
        print(f"新的光照图文件保存在：{BigLightmapPath}")
        
    except Exception as e:
        print(f"处理过程中出错：{str(e)}")
        raise

if __name__ == "__main__":
    main()
