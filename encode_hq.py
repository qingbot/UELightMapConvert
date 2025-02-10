import json
import os
import cv2
from PIL import Image
import numpy as np
import time

global_path = "C:/chaos_integrated_tools/data_analysis/scene"
SHRINK_PIXELS = 4

def process_texture_json(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    def process_dict(d):
        if not isinstance(d, dict):
            return d
        
        result = {}
        for key, value in d.items():
            if key == "TextureJsonURL":
                try:
                    with open(value, 'r') as f:
                        texture_data = json.load(f)
                    for texture_key, texture_value in texture_data.items():
                        result[texture_key] = texture_value
                except Exception as e:
                    print(f"处理texture json文件出错: {value}")
                    print(f"错误信息: {str(e)}")
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = process_dict(value)
            elif isinstance(value, list):
                result[key] = [process_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result
    
    processed_data = process_dict(data)
    
    with open(json_path, 'w') as f:
        json.dump(processed_data, f, indent='\t')
    
    if 'Landscape' not in processed_data:
        if 'lightmapGroup' in processed_data:
            return processed_data
        raise Exception("无法找到必要的数据结构")
    
    landscape_data = processed_data['Landscape']
    if 'Landscape' not in landscape_data:
        if 'lightmapGroup' in landscape_data:
            return landscape_data
        raise Exception("无法找到必要的数据结构")
    
    return landscape_data['Landscape']

def pil_to_cv2(pil_image):
    """将PIL图像转换为OpenCV格式"""
    # 先转换为RGBA
    if pil_image.mode != 'RGBA':
        pil_image = pil_image.convert('RGBA')
    # 转换为numpy数组
    numpy_image = np.array(pil_image)
    # 转换颜色通道顺序从RGBA到BGRA
    cv2_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGBA2BGRA)
    return cv2_image

def cv2_to_pil(cv2_image):
    """将OpenCV图像转换为PIL格式"""
    # 转换颜色通道顺序从BGRA到RGBA
    rgba_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGRA2RGBA)
    # 转换为PIL图像
    pil_image = Image.fromarray(rgba_image)
    return pil_image

def read_tga(image_path):
    """使用PIL读取TGA文件"""
    try:
        with Image.open(image_path) as img:
            return pil_to_cv2(img)
    except Exception as e:
        raise Exception(f"无法读取TGA文件: {image_path}, 错误: {str(e)}")

def save_tga(image_path, cv2_image):
    """保存为TGA文件"""
    try:
        pil_image = cv2_to_pil(cv2_image)
        pil_image.save(image_path, format='TGA')
    except Exception as e:
        raise Exception(f"无法保存TGA文件: {image_path}, 错误: {str(e)}")

def decode_light_hq(pixel, dir_pixel, source_coef_scale, source_coef_add):
    pixel = pixel.astype(np.uint8) / 255.0
    return (pixel * 255).astype(np.uint8)
    dir_pixel = dir_pixel.astype(np.uint8) / 255.0

    log_l = pixel[3]
    log_l += dir_pixel[3] * (1.0 / 255.0) - (0.5 / 255.0)
    log_l = log_l * source_coef_scale[3] + source_coef_add[3]

    uvw = pixel[0:4]
    uvw[0:3] = uvw[0:3] * uvw[0:3] * source_coef_scale[0:3] + source_coef_add[0:3]

    log_black_point = 0.01858136
    L = np.exp2(log_l) - log_black_point

    direction = 0.6
    luma = L * direction
    color = luma * uvw
    color = np.clip(color, 0, 1)
    color = color * 255.0
    return color

def direct_sample(source_array, x1, y1, x2, y2, target_width, target_height, dir_sample_offset_x, dir_sample_offset_y, source_coef_scale, source_coef_add):
    target_array = np.zeros((target_height, target_width, 4), dtype=source_array.dtype)
    
    x_scale = (x2 - x1) / (target_width - 1)
    y_scale = (y2 - y1) / (target_height - 1)
    
    for y in range(target_height):
        src_y_f = y1 + y * y_scale
        src_y = int(src_y_f)
        
        for x in range(target_width):
            src_x_f = x1 + x * x_scale
            src_x = int(src_x_f)
            
            src_x = np.clip(src_x, x1, x2-1)
            src_y = np.clip(src_y, y1, y2-1)

            direction_sample_x = int(src_x + dir_sample_offset_x)
            direction_sample_y = int(src_y + dir_sample_offset_y)
            
            target_array[y, x] = decode_light_hq(source_array[src_y, src_x], source_array[direction_sample_y, direction_sample_x], source_coef_scale, source_coef_add)
    
    return target_array

def process_lightmaps(landscape_data, lightmap_folder, json_path):
    total_start_time = time.time()
   
    lightmap_group = landscape_data['lightmapGroup']
    object_keys = [key for key in lightmap_group.keys() if key != 'combine']
    total_objects = len(object_keys)
    
    print(f"找到 {total_objects} 个物体需要处理")
    
    max_width = 0
    max_height = 0
    
    for object_key in object_keys:
        tile_data = lightmap_group[object_key]
        bias_scale = tile_data['BiasScale']
        u_scale, v_scale = bias_scale[2], bias_scale[3]
        
        source_path = os.path.join(lightmap_folder, f"{tile_data['HQ']}.tga")
        source_array = read_tga(source_path)
        source_height, source_width = source_array.shape[:2]
        
        actual_width = int(source_width * u_scale)
        actual_height = int(source_height * v_scale * 0.5)
        
        max_width = max(max_width, actual_width)
        max_height = max(max_height, actual_height)
    
    grid_size = int(np.ceil(np.sqrt(total_objects)))
    final_width = max_width * grid_size
    final_height = max_height * grid_size
    final_image = np.zeros((final_height, final_width, 4), dtype=np.uint8)
    
    print(f"创建 {grid_size}x{grid_size} 的网格图像，大小为 {final_width}x{final_height}")
    
    for i, object_key in enumerate(object_keys):
        tile_data = lightmap_group[object_key]
        hq_name = tile_data['HQ']
        bias_scale = tile_data['BiasScale']
        
        coef_scale = tile_data['CoefScale'][0:4]
        coef_add = tile_data['CoefAdd'][0:4]
        
        try:
            source_path = os.path.join(lightmap_folder, f"{hq_name}.tga")
            source_array = read_tga(source_path)
            source_height, source_width = source_array.shape[:2]
            
            u_offset, v_offset = bias_scale[0], bias_scale[1]
            u_scale, v_scale = bias_scale[2], bias_scale[3]
            
            x1 = int((0 * u_scale + u_offset) * source_width) + SHRINK_PIXELS
            y1 = int((0 * v_scale + v_offset) * 0.5 * source_height) + SHRINK_PIXELS
            x2 = int((1 * u_scale + u_offset) * source_width) - SHRINK_PIXELS
            y2 = int((1 * v_scale + v_offset) * 0.5 * source_height) - SHRINK_PIXELS

            dir_sample_offset_x = 0
            dir_sample_offset_y = 0.5 * (source_height)
            
            processed_image = direct_sample(source_array, x1, y1, x2, y2, 
                                         max_width, max_height,
                                         dir_sample_offset_x, dir_sample_offset_y,
                                         coef_scale, coef_add)
            
            grid_x = i % grid_size
            grid_y = i // grid_size
            paste_x = grid_x * max_width
            paste_y = grid_y * max_height
            
            final_image[paste_y:paste_y+max_height, 
                       paste_x:paste_x+max_width] = processed_image
            
            print(f"处理进度: {i+1}/{total_objects} ({(i+1)/total_objects*100:.1f}%) - {hq_name}")
            
        except Exception as e:
            print(f"处理贴图 {hq_name} 时出错: {str(e)}")
    
    output_name = f"{landscape_data['Name']}_combine_lightmap_hq"
    output_path = os.path.join(lightmap_folder, f"{output_name}.tga")
    save_tga(output_path, final_image)
    
    print(f"已生成合并后的光照图: {output_path}")
    total_end_time = time.time()
    print(f"程序总运行时间: {total_end_time - total_start_time:.2f}秒")

def main():
    start_time = time.time()
    
    json_path = os.path.join(global_path, "current_scene_data.json")
    lightmap_folder = os.path.join(global_path, "light", "light_map")
    
    if not os.path.exists(lightmap_folder):
        os.makedirs(lightmap_folder)
    
    try:
        landscape_data = process_texture_json(json_path)
        print("数据结构:", landscape_data.keys())
        process_lightmaps(landscape_data, lightmap_folder, json_path)
    except Exception as e:
        print(f"处理失败: {str(e)}")
        print("请检查JSON文件结构是否正确")
    
    end_time = time.time()
    print(f"\n总运行时间统计:")
    print(f"程序总运行时间: {end_time - start_time:.2f}秒")

if __name__ == "__main__":
    main()
