import json
import os
import numpy as np
import cv2
from PIL import Image  # 添加PIL导入
from concurrent.futures import ProcessPoolExecutor
from threading import Lock
import multiprocessing
import time

global_path = "C:/chaos_integrated_tools/data_analysis/scene"

def process_texture_json(json_path):
    """处理JSON文件, 将TextureJsonURL替换为其对应json文件的内容"""
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    def process_dict(d):
        """递归处理字典, 替换TextureJsonURL"""
        if not isinstance(d, dict):
            return d
        
        result = {}
        for key, value in d.items():
            if key == "TextureJsonURL":
                # 读取引用的json文件内容
                try:
                    with open(value, 'r') as f:
                        texture_data = json.load(f)
                    # 删除TextureJsonURL, 将texture json的所有数据添加到当前层级
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
    
    # 处理整个数据
    processed_data = process_dict(data)
    
    # 保存处理后的数据并打印结构
    with open(json_path, 'w') as f:
        json.dump(processed_data, f, indent='\t')
    
    print("JSON数据结构:")
    print(json.dumps(processed_data, indent=2))
    
    # 检查数据结构
    if 'Landscape' not in processed_data:
        print(f"警告: 在JSON中未找到'Landscape'键")
        print(f"可用的键: {list(processed_data.keys())}")
        # 尝试直接在根级别查找lightmapGroup
        if 'lightmapGroup' in processed_data:
            return processed_data
        raise Exception("无法找到必要的数据结构")
    
    landscape_data = processed_data['Landscape']
    if 'Landscape' not in landscape_data:
        print(f"警告: 在Landscape中未找到嵌套的'Landscape'键")
        print(f"可用的键: {list(landscape_data.keys())}")
        # 尝试直接使用第一层landscape数据
        if 'lightmapGroup' in landscape_data:
            return landscape_data
        raise Exception("无法找到必要的数据结构")
    
    return landscape_data['Landscape']

def load_lightmap_data(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)
    return data['Landscape']['Landscape']

def save_lightmap_data(json_path, lightmap_data, combine_name):
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # 添加combine字段
    data['Landscape']['Landscape']['lightmapGroup']['combine'] = combine_name
    
    with open(json_path, 'w') as f:
        json.dump(data, f, indent='\t')

def pil_to_cv2(pil_image):
    """将PIL图像转换为OpenCV格式"""
    # 转换为RGBA模式
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

def get_max_dimensions(lightmap_data, lightmap_folder):
    """获取贴图的宽度和高度,考虑bias和scale"""
    tile_data = lightmap_data['lightmapGroup']['0']
    lq_name = tile_data['LQ']
    bias_scale = tile_data['BiasScale']
    image_path = os.path.join(lightmap_folder, f"{lq_name}.tga")  # 改为.tga
    
    # 获取bias和scale值
    u_offset, v_offset = bias_scale[0], bias_scale[1] 
    u_scale, v_scale = bias_scale[2], bias_scale[3]
    
    # 使用PIL读取TGA图像
    img = read_tga(image_path)
    height, width = img.shape[:2]
    
    # 计算实际需要的宽高
    actual_width = int(width * u_scale)
    actual_height = int(height * v_scale * 0.5)  # 高度要乘0.5
    
    return actual_width, actual_height

def decode_light_lq(pixel, coef_scale, coef_add):
    """解码光照数据"""
    # 将uint8转换为float32并归一化到0-1范围
    r, g, b, a = pixel.astype(np.uint8) / 255.0
    
    # 对r,g,b进行pow(0.45)操作
    # r = pow(r, 2.2) * 255
    # g = pow(g, 2.2) * 255
    # b = pow(b, 2.2) * 255
    r *= 255
    g *= 255
    b *= 255
    
    
    # # 应用系数
    # r = r * coef_scale[1] + coef_add[1]
    # g = g * coef_scale[2] + coef_add[2]
    # b = b * coef_scale[3] + coef_add[3]
    
    # # 计算亮度
    # luminance = 0.299 * r + 0.587 * g + 0.114 * b
    # luminance = np.maximum(luminance, 0.000001)  # 避免除零
    
    # # 调整亮度范围
    # log_black_point = 0.00390625
    
    # # 计算新的亮度值
    # L = (pow(2, luminance * 16 - 8) - log_black_point)
    
    # # 应用亮度调整
    # scale = L / luminance
    
    # # 调整RGB值
    # r = np.clip(r * scale, 0, 1)
    # g = np.clip(g * scale, 0, 1)
    # b = np.clip(b * scale, 0, 1)
    
    # 返回浮点数值，范围0-1
    return np.array([r, g, b, a])
def gaussian_kernel(x, y, sigma=1.0):
    """计算高斯核权重"""
    return np.exp(-(x*x + y*y)/(2*sigma*sigma))

def direct_sample(source_array, x1, y1, x2, y2, target_width, target_height, coef_scale, coef_add):
    """直接点采样
    Args:
        source_array: 源图像数组
        x1, y1, x2, y2: 原始裁剪区域坐标（已经收缩过）
        target_width, target_height: 目标尺寸
        coef_scale, coef_add: 光照系数
    """
    # 创建目标数组
    target_array = np.zeros((target_height, target_width, 4), dtype=np.uint8)
    
    # 计算采样步长（使用浮点数保持精确度）
    x_scale = (x2 - x1) / (target_width - 1)
    y_scale = (y2 - y1) / (target_height - 1)
    
    # 直接点采样
    for y in range(target_height):
        # 使用浮点数计算源坐标
        src_y_f = y1 + y * y_scale
        # 四舍五入而不是直接截断
        src_y = int((src_y_f))
        
        for x in range(target_width):
            # 使用浮点数计算源坐标
            src_x_f = x1 + x * x_scale
            # 四舍五入而不是直接截断
            src_x = int((src_x_f))
            
            # 确保采样点在有效范围内
            src_x = np.clip(src_x, x1, x2-1)
            src_y = np.clip(src_y, y1, y2-1)
            
            # 获取源像素并解码
            pixel = decode_light_lq(source_array[src_y, src_x], coef_scale, coef_add)
            
            # # 计算亮度并应用log编码
            # log_black_point = 0.00390625
            # L = pixel[0] * 0.299 + pixel[1] * 0.587 + pixel[2] * 0.114
            # logL = np.log2(L + log_black_point) / 16.0 + 0.5
            # pixel[0] = pixel[0] * logL
            # pixel[1] = pixel[1] * logL
            # pixel[2] = pixel[2] * logL
            
            # # 对pixel超过1的值进行截断,然后转换为uint8
            # pixel = np.clip(pixel, 0, 1)
            # target_array[y, x] = (pixel).astype(np.uint8)
            target_array[y, x] = pixel
    return target_array

def save_landscape_json(lightmap_folder, landscape_data):
    """保存Landscape.json文件，包含所有的coef_scale和coef_add"""
    coef_data = []
    
    # 获取所有物体的键
    lightmap_group = landscape_data['lightmapGroup']
    object_keys = [key for key in lightmap_group.keys() if key != 'combine']
    
    # 遍历所有物体，收集coef数据
    for object_key in object_keys:
        tile_data = lightmap_group[object_key]
        coef_scale = tile_data['CoefScale'][8:12]  # 只取需要的部分
        coef_add = tile_data['CoefAdd'][8:12]
        
        # 添加到数组
        coef_data.append({
            'coef_scale': coef_scale,
            'coef_add': coef_add,
            'grid_index': int(object_key)  # 保存网格索引
        })
    
    # 按网格索引排序
    coef_data.sort(key=lambda x: x['grid_index'])
    
    # 保存到json文件
    landscape_json_path = os.path.join(lightmap_folder, 'Landscape.json')
    with open(landscape_json_path, 'w') as f:
        json.dump(coef_data, f, indent='\t')
    
    print(f"已保存系数数据到: {landscape_json_path}")
    print(f"共保存了 {len(coef_data)} 个物体的系数数据")

def process_lightmaps(landscape_data, lightmap_folder, json_path):
    total_start_time = time.time()
    
    # 保存系数数据到Landscape.json
    save_landscape_json(lightmap_folder, landscape_data)
    
    # 获取所有物体的键
    lightmap_group = landscape_data['lightmapGroup']
    object_keys = [key for key in lightmap_group.keys() if key != 'combine']
    total_objects = len(object_keys)
    
    print(f"找到 {total_objects} 个物体需要处理")
    
    # 先计算每个物体的尺寸，找到最大尺寸
    max_width = 0
    max_height = 0
    
    for object_key in object_keys:
        tile_data = lightmap_group[object_key]
        bias_scale = tile_data['BiasScale']
        u_scale, v_scale = bias_scale[2], bias_scale[3]
        
        # 读取源贴图获取尺寸
        source_path = os.path.join(lightmap_folder, f"{tile_data['LQ']}.tga")
        source_array = read_tga(source_path)
        source_height, source_width = source_array.shape[:2]
        
        # 计算实际尺寸
        actual_width = int(source_width * u_scale)
        actual_height = int(source_height * v_scale * 0.5)
        
        max_width = max(max_width, actual_width)
        max_height = max(max_height, actual_height)
    
    # 创建最终的大图
    grid_size = int(np.ceil(np.sqrt(total_objects)))  # 计算网格大小
    final_width = max_width * grid_size
    final_height = max_height * grid_size
    final_image = np.zeros((final_height, final_width, 4), dtype=np.uint8)
    
    print(f"创建 {grid_size}x{grid_size} 的网格图像，大小为 {final_width}x{final_height}")
    
    # 处理每个物体并复制到大图中
    for i, object_key in enumerate(object_keys):
        tile_data = lightmap_group[object_key]
        lq_name = tile_data['LQ']
        bias_scale = tile_data['BiasScale']
        
        # 提取CoefScale和CoefAdd的相关值
        coef_scale = tile_data['CoefScale'][8:12]
        coef_add = tile_data['CoefAdd'][8:12]
        
        try:
            # 读取源贴图
            source_path = os.path.join(lightmap_folder, f"{lq_name}.tga")
            source_array = read_tga(source_path)
            source_height, source_width = source_array.shape[:2]
            
            # 计算UV偏移和缩放
            u_offset, v_offset = bias_scale[0], bias_scale[1]
            u_scale, v_scale = bias_scale[2], bias_scale[3]
            
            # 计算源图像中的裁剪区域
            x1 = int((0 * u_scale + u_offset) * source_width)
            y1 = int((0 * v_scale + v_offset) * 0.5 * source_height)
            x2 = int((1 * u_scale + u_offset) * source_width)
            y2 = int((1 * v_scale + v_offset) * 0.5 * source_height)
            
            # 直接采样到目标尺寸
            processed_image = direct_sample(source_array, x1, y1, x2, y2, 
                                         max_width, max_height,
                                         coef_scale, coef_add)
            
            # 计算在最终图像中的位置
            grid_x = i % grid_size
            grid_y = i // grid_size
            paste_x = grid_x * max_width
            paste_y = grid_y * max_height
            
            # 复制到最终图像
            final_image[paste_y:paste_y+max_height, 
                       paste_x:paste_x+max_width] = processed_image
            
            print(f"处理进度: {i+1}/{total_objects} ({(i+1)/total_objects*100:.1f}%) - {lq_name}")
            
        except Exception as e:
            print(f"处理贴图 {lq_name} 时出错: {str(e)}")
    
    # 保存最终图像
    output_name = f"{landscape_data['Name']}_combine_lightmap"
    output_path = os.path.join(lightmap_folder, f"{output_name}.tga")
    save_tga(output_path, final_image)
    
    # 更新JSON文件
    save_lightmap_data(json_path, landscape_data, output_name)
    
    print(f"已生成合并后的光照图: {output_path}")
    total_end_time = time.time()
    print(f"程序总运行时间: {total_end_time - total_start_time:.2f}秒")

def main():
    start_time = time.time()  # 记录程序开始时间
    
    # 构建相关路径
    json_path = os.path.join(global_path, "current_scene_data.json")
    lightmap_folder = os.path.join(global_path, "light", "light_map")
    
    # 确保light_map文件夹存在
    if not os.path.exists(lightmap_folder):
        os.makedirs(lightmap_folder)
    
    try:
        # 先处理texture json引用
        landscape_data = process_texture_json(json_path)
        print("数据结构:", landscape_data.keys())
        process_lightmaps(landscape_data, lightmap_folder, json_path)
    except Exception as e:
        print(f"处理失败: {str(e)}")
        print("请检查JSON文件结构是否正确")
    
    end_time = time.time()  # 记录程序结束时间
    print(f"\n总运行时间统计:")
    print(f"程序总运行时间: {end_time - start_time:.2f}秒")

if __name__ == "__main__":
    main()
