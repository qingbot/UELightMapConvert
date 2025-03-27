import json
import os
from PIL import Image
import time
import numpy as np
import traceback
import argparse
import sys

# 移除全局路径，改为通过配置获取
# global_path = "C:/chaos_integrated_tools/data_analysis/scene"
SHRINK_PIXELS = 4   # 裁剪像素
FINAL_TEXTURE_MAX_SIZE = 2048  # 最终纹理最大尺寸

# 添加新的函数入口，用于被hybrid_lightmap_packer.py调用
def process_terrain_lightmap(scene_name, log_callback=None, override_json_path=None, override_lightmap_folder=None):
    """
    处理场景地形的光照图，作为hybrid_lightmap_packer.py的函数入口
    
    Args:
        scene_name: 场景名称，用于获取配置
        log_callback: 可选的日志回调函数，用于输出日志信息
        override_json_path: 可选，指定JSON文件路径，覆盖配置中的路径
        override_lightmap_folder: 可选，指定灯光贴图文件夹路径，覆盖配置中的路径
    
    Returns:
        dict: 包含处理结果的字典，如果成功则包含贴图名称和系数值，失败则为None
    """
    try:
        start_time = time.time()
        
        # 使用自定义日志函数或默认打印
        log = log_callback if log_callback else print
        
        log(f"开始处理场景地形: {scene_name}")
        
        # 获取场景配置
        scene_config = get_scene_config(scene_name)
        
        # 构建相关路径，优先使用指定的覆盖路径
        json_path = override_json_path if override_json_path else scene_config["source_lightmap_json_path"]
        lightmap_folder = override_lightmap_folder if override_lightmap_folder else scene_config["source_lightmap_texture_path"]
        
        log(f"使用JSON路径: {json_path}")
        log(f"使用灯光贴图文件夹: {lightmap_folder}")
        
        # 检查JSON文件是否存在
        if not os.path.exists(json_path):
            log(f"错误: JSON文件不存在: {json_path}")
            return None
        
        # 确保light_map文件夹存在
        if not os.path.exists(lightmap_folder):
            os.makedirs(lightmap_folder)
            log(f"创建文件夹: {lightmap_folder}")
        
        # 先处理texture json引用
        landscape_data = process_texture_json(json_path)
        log("成功处理texture json引用")
        
        # 处理lightmaps，现在返回贴图名称和系数
        result = process_lightmaps(landscape_data, lightmap_folder, json_path)
        
        end_time = time.time()
        log(f"地形处理完成，总耗时: {end_time - start_time:.2f}秒")
        
        return result
    except Exception as e:
        if log_callback:
            log_callback(f"处理地形时出错: {str(e)}")
            log_callback(traceback.format_exc())
        else:
            print(f"处理地形时出错: {str(e)}")
            traceback.print_exc()
        return None

# 添加获取场景配置的函数
def get_scene_config(scene_name):
    """根据场景名称获取配置"""
    # 导入全局配置
    try:
        import GlobalParameter
        if scene_name not in GlobalParameter.ALL_LIGHT_MAP_DATA:
            print(f"错误: 无法找到场景 '{scene_name}' 的配置")
            print(f"可用的场景: {list(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())}")
            sys.exit(1)
        
        return GlobalParameter.ALL_LIGHT_MAP_DATA[scene_name]
    except ImportError:
        print("错误: 无法导入GlobalParameter模块")
        sys.exit(1)

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
    
    # print("JSON数据结构:")
    # print(json.dumps(processed_data, indent=2))
    
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
    data['Landscape']['Landscape']['lightmapGroup']['combine'] = combine_name
    with open(json_path, 'w') as f:
        json.dump(data, f, indent='\t')

def read_png(image_path):
    """使用PIL读取PNG文件,确保输出RGBA格式"""
    try:
        img = Image.open(image_path)
        # 确保图像是RGBA格式
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        return img
    except Exception as e:
        raise Exception(f"无法读取PNG文件: {image_path}, 错误: {str(e)}")

def save_png(image_path, pil_image):
    """保存为PNG文件"""
    try:
        pil_image.save(image_path, format='PNG')
    except Exception as e:
        raise Exception(f"无法保存PNG文件: {image_path}, 错误: {str(e)}")

def get_max_dimensions(lightmap_data, lightmap_folder):
    """获取贴图的宽度和高度,考虑bias和scale"""
    tile_data = lightmap_data['lightmapGroup']['0']
    lq_name = tile_data['LQ']
    bias_scale = tile_data['BiasScale']
    image_path = os.path.join(lightmap_folder, f"{lq_name}.png")  # 改为.png
    
    # 获取bias和scale值
    u_offset, v_offset = bias_scale[0], bias_scale[1] 
    u_scale, v_scale = bias_scale[2], bias_scale[3]
    
    # 使用PIL读取PNG图像
    img = read_png(image_path)
    height, width = img.size
    
    # 计算实际需要的宽高
    actual_width = int(width * u_scale)
    actual_height = int(height * v_scale * 0.5)  # 高度要乘0.5
    
    return actual_width, actual_height

def decode_light_lq(pixel, coef_scale, coef_add):
    """解码光照数据"""
    # 确保我们有4个通道的数据
    if len(pixel) == 3:
        r, g, b = pixel
        a = 255  # 如果没有alpha通道,设置为255
    else:
        r, g, b, a = pixel
    
    # 归一化到0-1范围
    r, g, b = r/255.0, g/255.0, b/255.0
    
    # 应用系数
    r = r * coef_scale[0] + coef_add[0]
    g = g * coef_scale[1] + coef_add[1]
    b = b * coef_scale[2] + coef_add[2]
    
    return (r, g, b, a)

def ReQuantize(processed_images):
    # 初始化每个通道的最大最小值
    min_coef = [float('inf')] * 4
    max_coef = [float('-inf')] * 4 
    
    scale = [0, 0, 0, 0]
    add = [0, 0, 0, 0]
    # 统计每个通道coef_scale和coef_add的最大最小值
    for img_data in processed_images:
        coef_scale = img_data['coef_scale']
        coef_add = img_data['coef_add']

        # 更新每个通道coef_scale的最大最小值
        for i in range(4):
            s = coef_scale[i]
            a = coef_add[i]
            min_c = a
            max_c = a + s
            min_coef[i] = min(min_coef[i], min_c)
            max_coef[i] = max(max_coef[i], max_c)
    
    for i in range(4):
        scale[i] = max_coef[i] - min_coef[i]
        add[i] = min_coef[i]

    for img_data in processed_images:
        image_data = img_data['array']

        for i in range(len(image_data)):
            data = image_data[i]
            for p in range(len(data)):
                pixel = data[p]
                for j in range(3):
                    pixel[j] = (pixel[j] - add[j]) / scale[j]
                    pixel[j] = np.clip(pixel[j] * 255, 0, 255)
                data[p] = pixel
            image_data[i] = data
        img_data['array'] = image_data

    return (processed_images, scale, add)

def reLighting(processed_images, coef_scale, coef_add):
    for img_data in processed_images:
        image_data = img_data['array']
        for i in range(len(image_data)):
            data = image_data[i]
            for p in range(len(data)):
                pixel = data[p]
                
                r = pixel[0] / 255.0
                g = pixel[1] / 255.0
                b = pixel[2] / 255.0
                a = pixel[3] 
                
                r = r * coef_scale[0] + coef_add[0]
                g = g * coef_scale[1] + coef_add[1]
                b = b * coef_scale[2] + coef_add[2]
                
                log_l = 0.299 * r + 0.587 * g + 0.114 * b
                log_l = max(log_l, 0.000001)
                
                log_black_point = 0.00390625
                L = pow(2, log_l * 16 - 8) - log_black_point

                scale = L / log_l
                direction = 1
                luma = L * direction

                r = r * (luma / max(0.000001, log_l))
                g = g * (luma / max(0.000001, log_l))
                b = b * (luma / max(0.000001, log_l))
                
                r = np.clip(r * 255, 0, 255)
                g = np.clip(g * 255, 0, 255)
                b = np.clip(b * 255, 0, 255)
                
                data[p] = (r, g, b, a)
            image_data[i] = data
        img_data['array'] = image_data
                    

def direct_sample(source_image, x1, y1, x2, y2, target_width, target_height, coef_scale, coef_add):
    """使用PIL的线性采样方法处理图像,返回浮点数数组"""
    # 裁剪需要的区域
    crop_box = (x1, y1, x2, y2)
    cropped = source_image.crop(crop_box)
    
    # 使用BILINEAR进行线性采样调整大小
    resized = cropped.resize((target_width, target_height), Image.LANCZOS)
    
    # 创建浮点数数组
    processed_array = np.zeros((target_height, target_width, 4), dtype=np.float32)
    resized_pixels = resized.load()
    
    # 对每个像素应用光照解码
    for y in range(target_height):
        for x in range(target_width):
            pixel = resized_pixels[x, y]
            decoded_pixel = decode_light_lq(pixel, coef_scale, coef_add)
            processed_array[y, x] = decoded_pixel
    
    return processed_array

def ensure_bigmap_dir(lightmap_folder):
    """确保BigMap目录存在，返回完整路径"""
    # 使用与hybrid_lightmap_packer.py相同的路径结构：在lightmap_folder的父目录下创建BigMap
    bigmap_dir = os.path.join(os.path.dirname(lightmap_folder), "BigMap")
    os.makedirs(bigmap_dir, exist_ok=True)
    print(f"确保BigMap目录存在: {bigmap_dir}")
    return bigmap_dir

def save_landscape_json(lightmap_folder, landscape_data):
    """保存Landscape.json文件,包含所有的coef_scale和coef_add"""
    coef_data = []
    
    # 获取所有物体的键
    lightmap_group = landscape_data['lightmapGroup']
    object_keys = [key for key in lightmap_group.keys() if key != 'combine']
    
    # 遍历所有物体,收集coef数据
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
    
    # 确保BigMap目录存在
    bigmap_dir = ensure_bigmap_dir(lightmap_folder)
    # 保存到json文件
    landscape_json_path = os.path.join(bigmap_dir, 'Landscape.json')
    with open(landscape_json_path, 'w') as f:
        json.dump(coef_data, f, indent='\t')
    
    print(f"已保存系数数据到: {landscape_json_path}")
    print(f"共保存了 {len(coef_data)} 个物体的系数数据")

def process_lightmaps(landscape_data, lightmap_folder, json_path):
    total_start_time = time.time()
    
    save_landscape_json(lightmap_folder, landscape_data)
    
    lightmap_group = landscape_data['lightmapGroup']
    object_keys = [key for key in lightmap_group.keys() if key != 'combine']
    total_objects = len(object_keys)
    
    print(f"找到 {total_objects} 个物体需要处理")
    
    # 计算最大尺寸
    max_width = 0
    max_height = 0
    
    for object_key in object_keys:
        tile_data = lightmap_group[object_key]
        bias_scale = tile_data['BiasScale']
        u_scale, v_scale = bias_scale[2], bias_scale[3]
        
        source_path = os.path.join(lightmap_folder, f"{tile_data['LQ']}.png")
        with Image.open(source_path) as source_image:
            source_width, source_height = source_image.size
            actual_width = int(source_width * u_scale)
            actual_height = int(source_height * v_scale * 0.5)
            max_width = max(max_width, actual_width)
            max_height = max(max_height, actual_height)
    
    grid_size = int(pow(total_objects, 0.5) + 0.5)
    final_width = max_width * grid_size
    final_height = max_height * grid_size
    
    # 计算缩放比例,确保最终尺寸不超过2048x2048
    scale = 1.0
    if final_width > FINAL_TEXTURE_MAX_SIZE or final_height > FINAL_TEXTURE_MAX_SIZE:
        scale = min(FINAL_TEXTURE_MAX_SIZE / final_width, FINAL_TEXTURE_MAX_SIZE / final_height)
        max_width = int(max_width * scale)
        max_height = int(max_height * scale)
        final_width = max_width * grid_size
        final_height = max_height * grid_size
        print(f"图像尺寸超过限制,将按{scale:.2f}倍缩放")
    
    print(f"创建 {grid_size}x{grid_size} 的网格图像,大小为 {final_width}x{final_height}")
    
    # 创建一个数组来存储所有处理后的图片数据
    processed_images = []
    processed_images_direction = []
    
    for i, object_key in enumerate(object_keys):
        tile_data = lightmap_group[object_key]
        lq_name = tile_data['LQ']
        bias_scale = tile_data['BiasScale']
        
        coef_scale_light = tile_data['CoefScale'][8:12]
        coef_add_light = tile_data['CoefAdd'][8:12]

        coef_scale_direction = tile_data['CoefScale'][12:16]
        coef_add_direction = tile_data['CoefAdd'][12:16]

        try:
            source_path = os.path.join(lightmap_folder, f"{lq_name}.png")
            source_image = read_png(source_path)
            source_width, source_height = source_image.size
            
            u_offset, v_offset = bias_scale[0], bias_scale[1]
            u_scale, v_scale = bias_scale[2], bias_scale[3]
            
            x1 = int((0 * u_scale + u_offset) * source_width) + SHRINK_PIXELS
            y1 = int((0 * v_scale + v_offset) * 0.5 * source_height) + SHRINK_PIXELS
            x2 = int((1 * u_scale + u_offset) * source_width) - SHRINK_PIXELS
            y2 = int((1 * v_scale + v_offset) * 0.5 * source_height) - SHRINK_PIXELS
            
            # 使用缩放后的尺寸
            target_width = int(max_width)
            target_height = int(max_height)
            
            processed_array = direct_sample(source_image, x1, y1, x2, y2, 
                                         target_width, target_height,
                                         coef_scale_light, coef_add_light)
            
            processed_array_direction = direct_sample(source_image, x1, y1 + 0.5 * source_height, x2, y2 + 0.5 * source_height, 
                                         target_width, target_height,
                                         coef_scale_direction, coef_add_direction)
            
            # 存储处理后的数组和位置信息
            grid_x = i % grid_size
            grid_y = i // grid_size
            paste_x = grid_x * max_width
            paste_y = grid_y * max_height

            processed_images.append({
                'array': processed_array,
                'position': (paste_x, paste_y),
                'name': lq_name,
                'coef_scale': coef_scale_light,
                'coef_add': coef_add_light
            })
            

            processed_images_direction.append({
                'array': processed_array_direction,
                'position': (paste_x, paste_y),
                'name': lq_name,
                'coef_scale': coef_scale_direction,
                'coef_add': coef_add_direction
            })

            print(f"处理进度: {i+1}/{total_objects} ({(i+1)/total_objects*100:.1f}%) - {lq_name}")
            
        except Exception as e:
            traceback.print_exc()
            print(f"处理贴图 {lq_name} 时出错: {str(e)}")
    
    print("所有图片处理完成,开始后处理...")
    
    # 这里可以对processed_images数组进行整体操作
    processed_images, scale, add = ReQuantize(processed_images)
    processed_images_direction, scale_direction, add_direction = ReQuantize(processed_images_direction)
    print("光照图 scale:", scale)
    print("光照图 add:", add)
    print("方向图 scale:", scale_direction)
    print("方向图 add:", add_direction)
    
    # 将处理后的数组转换回图片 - 光照图
    final_image = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
    for img_data in processed_images:
        array = img_data['array']
        array = array.astype(np.uint8)
        img = Image.fromarray(array, 'RGBA')
        final_image.paste(img, img_data['position'])
    
    # 左旋90度并左右翻转
    final_image = final_image.rotate(-90, expand=True)
    final_image = final_image.transpose(Image.FLIP_LEFT_RIGHT)
    
    # 将处理后的数组转换回图片 - 方向图
    final_image_direction = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
    for img_data in processed_images_direction:
        array = img_data['array']
        array = array.astype(np.uint8)
        img = Image.fromarray(array, 'RGBA')
        final_image_direction.paste(img, img_data['position'])
    
    # 方向图也左旋90度并左右翻转
    final_image_direction = final_image_direction.rotate(-90, expand=True)
    final_image_direction = final_image_direction.transpose(Image.FLIP_LEFT_RIGHT)
    
    # 创建BigMap目录并保存最终图像 - 修改为使用与静态物体相同的路径
    bigmap_dir = ensure_bigmap_dir(lightmap_folder)
    output_name = f"{landscape_data['Name']}_combine_lightmap"
    output_path = os.path.join(bigmap_dir, f"{output_name}.png")
    save_png(output_path, final_image)
    
    output_name_direction = f"{landscape_data['Name']}_combine_direction"
    output_path_direction = os.path.join(bigmap_dir, f"{output_name_direction}.png")
    save_png(output_path_direction, final_image_direction)
    
    save_lightmap_data(json_path, landscape_data, output_name)
    
    print(f"已生成合并后的光照图: {output_path}")
    print(f"已生成合并后的方向图: {output_path_direction}")
    total_end_time = time.time()
    print(f"程序总运行时间: {total_end_time - total_start_time:.2f}秒")
    
    # 返回处理结果，包括贴图名称和系数
    result = {
        "combine_name": output_name,
        "lightmap_coef_scale": scale,
        "lightmap_coef_add": add,
        "direction_name": output_name_direction,
        "direction_coef_scale": scale_direction,
        "direction_coef_add": add_direction
    }
    
    return result

def main():
    start_time = time.time()  # 记录程序开始时间
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='处理场景地形的光照图')
    parser.add_argument('--scene', type=str, default="basic_level",
                        help='要处理的场景名称，默认为basic_level')
    args = parser.parse_args()
    
    # 获取场景配置
    scene_config = get_scene_config(args.scene)
    print(f"正在处理场景: {args.scene}")
    
    # 构建相关路径
    json_path = scene_config["source_lightmap_json_path"]
    lightmap_folder = scene_config["source_lightmap_texture_path"]
    
    # 确保light_map文件夹存在
    if not os.path.exists(lightmap_folder):
        os.makedirs(lightmap_folder)
    
    try:
        # 先处理texture json引用
        landscape_data = process_texture_json(json_path)
        #print("数据结构:", landscape_data.keys())
        process_lightmaps(landscape_data, lightmap_folder, json_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"处理失败: {str(e)}")
        print("请检查JSON文件结构是否正确")
    

    end_time = time.time()  # 记录程序结束时间
    print(f"\n总运行时间统计:")
    print(f"程序总运行时间: {end_time - start_time:.2f}秒")

if __name__ == "__main__":
    main()
