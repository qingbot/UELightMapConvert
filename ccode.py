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
SHRINK_PIXELS = 4  # 每边收缩的像素数

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
    
    # 保存处理后的数据
    with open(json_path, 'w') as f:
        json.dump(processed_data, f, indent='\t')
    
    return processed_data['Landscape']['Landscape']

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

def read_bmp(image_path):
    """使用PIL读取BMP文件"""
    try:
        with Image.open(image_path) as img:
            return pil_to_cv2(img)
    except Exception as e:
        raise Exception(f"无法读取BMP文件: {image_path}, 错误: {str(e)}")

def save_bmp(image_path, cv2_image):
    """保存为BMP文件"""
    try:
        pil_image = cv2_to_pil(cv2_image)
        pil_image.save(image_path, format='BMP')
    except Exception as e:
        raise Exception(f"无法保存BMP文件: {image_path}, 错误: {str(e)}")

def get_max_dimensions(lightmap_data, lightmap_folder):
    """获取贴图的宽度和高度,考虑bias和scale"""
    # 获取单个地块的数据
    tile_data = lightmap_data['lightmapGroup']['0']
    lq_name = tile_data['LQ']
    bias_scale = tile_data['BiasScale']
    image_path = os.path.join(lightmap_folder, f"{lq_name}.bmp")  # 改为.bmp
    
    # 获取bias和scale值
    u_offset, v_offset = bias_scale[0], bias_scale[1] 
    u_scale, v_scale = bias_scale[2], bias_scale[3]
    
    # 使用PIL读取BMP图像
    img = read_bmp(image_path)
    height, width = img.shape[:2]
    
    # 计算实际需要的宽高
    actual_width = int(width * u_scale)
    actual_height = int(height * v_scale * 0.5)  # 高度要乘0.5
    
    return actual_width, actual_height

def decode_light_lq(pixel, coef_scale, coef_add):
    """解码光照数据，使用更高精度的计算"""
    # 使用float64提高精度
    pixel = pixel.astype(np.uint8)
    r, g, b, a = pixel / 255.0
    
    # 使用高精度系数
    r = (r * coef_scale[0] + coef_add[0])
    g = (g * coef_scale[1] + coef_add[1])
    b = (b * coef_scale[2] + coef_add[2])
    
    # 保持高精度计算
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    luminance = np.maximum(luminance, 0.000001)
    

    log_black_point = 0.00390625
    L = np.exp2(luminance * 16 - 8) - log_black_point
    luma = L * 0.6
    scale = luma / luminance
    
    # 最后再转回float32
    r = (r * scale) 
    g = (g * scale) 
    b = (b * scale) 
    a = (a)
    
    return np.array([r, g, b, a])

def gaussian_kernel(x, y, sigma=1.0):
    """计算高斯核权重"""
    return np.exp(-(x*x + y*y)/(2*sigma*sigma))

def direct_sample(source_array, x1, y1, x2, y2, target_width, target_height, coef_scale, coef_add):
    target_array = np.zeros((target_height, target_width, 4), dtype=np.uint8)
    
    # 使用float64计算采样步长
    x_scale = np.float64(x2 - x1) / np.float64(target_width - 1)
    y_scale = np.float64(y2 - y1) / np.float64(target_height - 1)
    
    for y in range(target_height):
        # 保持高精度计算采样位置
        src_y_f = np.float64(y1) + np.float64(y) * y_scale
        src_y = int((src_y_f))  # 使用round而不是截断
        
        for x in range(target_width):
            src_x_f = np.float64(x1) + np.float64(x) * x_scale
            src_x = int((src_x_f))
            
            src_x = np.clip(src_x, x1, x2-1)
            src_y = np.clip(src_y, y1, y2-1)
            
            pixel = decode_light_lq(source_array[src_y, src_x], coef_scale, coef_add)
            
            # # 使用高精度计算亮度
            # log_black_point = np.float64(0.00390625)
            # L = np.float64(pixel[0] * 0.299 + pixel[1] * 0.587 + pixel[2] * 0.114)
            # logL = np.float64(np.log2(L + log_black_point)) / np.float64(16.0) + np.float64(0.5)
            
            # pixel = pixel * logL
            # pixel = np.clip(pixel, 0, 1)
            target_array[y, x] = (pixel * 255.0).astype(np.uint8)
            
    return target_array

def process_lightmaps(landscape_data, lightmap_folder, json_path):
    total_start_time = time.time()
    
    # 创建8x8的网格
    grid_size = 8
    total_tiles = grid_size * grid_size
    
    # 获取所有贴图中的最大尺寸（已经减去收缩的像素）
    tile_width, tile_height = get_max_dimensions(landscape_data, lightmap_folder)
    
    # 创建最终的大图（尺寸已经考虑收缩）
    final_width = tile_width * grid_size
    final_height = tile_height * grid_size
    final_image = np.zeros((final_height, final_width, 4), dtype=np.uint8)
    
    print("开始处理图像...")
    
    # 直接遍历所有图块
    lightmap_data = landscape_data['lightmapGroup']
    for i in range(total_tiles):
        tile_data = lightmap_data[str(i)]
        lq_name = tile_data['LQ']
        bias_scale = tile_data['BiasScale']
        
        # 提取CoefScale和CoefAdd的相关值
        coef_scale = tile_data['CoefScale'][8:12]
        coef_add = tile_data['CoefAdd'][8:12]
        
        # 读取源贴图
        source_path = os.path.join(lightmap_folder, f"{lq_name}.bmp")  # 改为.bmp
        source_array = read_bmp(source_path)
        source_height, source_width = source_array.shape[:2]
        
        # 计算UV偏移和缩放
        u_offset, v_offset = bias_scale[0], bias_scale[1]
        u_scale, v_scale = bias_scale[2], bias_scale[3]
        
        try:
            # 计算源图像中的裁剪区域（向内收缩指定像素）
            x1 = int((0 * u_scale + u_offset) * source_width) + SHRINK_PIXELS
            y1 = int((0 * v_scale + v_offset) * 0.5 * source_height) + SHRINK_PIXELS
            x2 = int((1 * u_scale + u_offset) * source_width) - SHRINK_PIXELS
            y2 = int((1 * v_scale + v_offset) * 0.5 * source_height) - SHRINK_PIXELS

            # 直接采样到目标尺寸（已经减去收缩的像素）
            sampled_array = direct_sample(source_array, x1, y1, x2, y2, 
                                        tile_width, tile_height,
                                        coef_scale, coef_add)
            
            # 计算在最终图像中的位置
            grid_x = i % grid_size
            grid_y = i // grid_size
            paste_x = grid_x * tile_width
            paste_y = grid_y * tile_height
            
            # 复制到最终图像
            final_image[paste_y:paste_y+tile_height, 
                       paste_x:paste_x+tile_width] = sampled_array
            
            # 显示进度
            print(f"处理进度: {i+1}/{total_tiles} ({(i+1)/total_tiles*100:.1f}%)")
            
        except Exception as e:
            print(f"处理贴图 {lq_name} 时出错: {str(e)}")
    
    # 保存最终图像为BMP格式
    output_name = f"{landscape_data['Name']}_combine_lightmap"
    output_path = os.path.join(lightmap_folder, f"{output_name}.bmp")  # 改为.bmp
    save_bmp(output_path, final_image)
    
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
    
    # 先处理texture json引用
    landscape_data = process_texture_json(json_path)
    process_lightmaps(landscape_data, lightmap_folder, json_path)
    
    end_time = time.time()  # 记录程序结束时间
    print(f"\n总运行时间统计:")
    print(f"程序总运行时间: {end_time - start_time:.2f}秒")

if __name__ == "__main__":
    main()
