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
JsonPath = Path.joinpath(RootPath, "current_scene_data.json")

# 新增：获取新JSON文件的路径
def get_new_json_path():
    # 使用时间戳创建新的文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_name = f"current_scene_data_{timestamp}.json"
    return Path.joinpath(RootPath, json_name)

class LightmapPacker:
    def __init__(self, texture_size):
        self.texture_size = texture_size
        self.current_textures = []  # 存储当前的纹理图像数据
        self.current_positions = []  # 存储每个纹理的位置信息
        self.add_new_texture()
    
    def add_new_texture(self):
        # 使用NumPy创建空白纹理数组
        new_texture = np.zeros((self.texture_size, self.texture_size, 4), dtype=np.uint8)
        self.current_textures.append(new_texture)
        self.current_positions.append([])
        return len(self.current_textures) - 1
    
    def can_fit(self, size, texture_index):
        if not self.current_positions[texture_index]:
            return True, (0, 0)
        
        # 实现简单的装箱算法
        positions = self.current_positions[texture_index]
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
            can_fit, position = self.can_fit(size, i)
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

def pack_lightmaps(lightmaps):
    # 确保BigLightmap文件夹存在
    os.makedirs(BigLightmapPath, exist_ok=True)
    
    packer = LightmapPacker(TextureSize)
    results = []
    
    for info in lightmaps:
        # 提取原始光照图，确保添加.png后缀
        lightmap_name = info["LQ"] if info["LQ"].endswith('.png') else f"{info['LQ']}.png"
        lightmap_path = Path.joinpath(LightmapPath, lightmap_name)
        texture_array, size = extract_lightmap(lightmap_path, info["BiasScale"])
        
        # 添加到打包器
        texture_index, position = packer.add_texture(texture_array, size)
        
        # 计算新的BiasScale
        new_bias_scale = [
            position[0] / TextureSize,
            position[1] / TextureSize,
            size[0] / TextureSize,
            size[1] / TextureSize
        ]
        
        # 只使用图片名字，不包含路径和后缀
        new_lq = f"packed_lightmap_{texture_index}"
        
        results.append({
            "Name": info["Name"],
            "texture_index": texture_index,
            "new_lq": new_lq,
            "new_bias_scale": new_bias_scale
        })
    
    # 保存打包后的纹理到BigLightmap文件夹，但文件名仍然需要后缀
    for i, texture_array in enumerate(packer.current_textures):
        save_path = Path.joinpath(LightmapPath, f"BigLightmap/packed_lightmap_{i}.png")
        # 将NumPy数组转换回图片并保存
        Image.fromarray(texture_array).save(save_path)
    
    return results

def update_json_data(json_data, new_lightmap_info):
    # 更新JSON中的光照图信息，只保存图片名字
    for info in new_lightmap_info:
        for mesh in json_data["Static Mesh"].values():
            if mesh["Name"] == info["Name"]:
                mesh["LightMap"]["LQ"] = info["new_lq"]  # 这里只保存名字，不包含路径和后缀
                mesh["LightMap"]["BiasScale"] = info["new_bias_scale"]
                break

def main():
    # 加载JSON数据并创建副本
    json_data = load_json_data()
    new_json_path = get_new_json_path()
    
    # 先保存一份JSON副本
    with open(new_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=4)
    
    print(f"已创建JSON备份文件：{new_json_path}")
    
    # 收集所有需要处理的光照图信息
    lightmap_infos = []
    for mesh in json_data["Static Mesh"].values():
        if "LightMap" in mesh and "LQ" in mesh["LightMap"]:
            lightmap_infos.append({
                "Name": mesh["Name"],
                "LQ": mesh["LightMap"]["LQ"],
                "BiasScale": mesh["LightMap"]["BiasScale"]
            })
    
    # 提取并重新打包光照图
    packed_results = pack_lightmaps(lightmap_infos)
    
    # 更新JSON数据
    update_json_data(json_data, packed_results)
    
    # 保存更新后的JSON到新文件
    with open(new_json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=4)
    
    print(f"处理完成！新的JSON文件已保存为：{new_json_path}")
    print(f"新的光照图文件保存在：{BigLightmapPath}")

if __name__ == "__main__":
    main()