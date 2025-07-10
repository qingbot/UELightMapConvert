# 生成mipmap

import numpy as np
from PIL import Image
from typing import Union, Optional, List, Tuple
import os

def generate_mipmap_half_resolution(
    input_image: Union[np.ndarray, Image.Image, str],
    output_path: Optional[str] = None
) -> Union[np.ndarray, Image.Image]:
    """
    生成原图1/2分辨率的mipmap
    
    Args:
        input_image: 输入图片，可以是以下格式之一：
            - np.ndarray: numpy数组形式的图片数据 (H, W, C)
            - PIL.Image.Image: PIL图片对象
            - str: 图片文件路径
        output_path: 可选，输出文件路径，如果提供则会保存到文件
    
    Returns:
        Union[np.ndarray, Image.Image]: 1/2分辨率的图片
            - 如果输入是numpy数组，返回numpy数组
            - 如果输入是PIL.Image，返回PIL.Image
            - 如果输入是文件路径，返回PIL.Image
    
    Raises:
        ValueError: 当输入格式不支持时
        FileNotFoundError: 当输入文件路径不存在时
    """
    # 统一转换为numpy数组格式进行计算
    if isinstance(input_image, str):
        # 文件路径输入
        if not os.path.exists(input_image):
            raise FileNotFoundError(f"输入文件不存在: {input_image}")
        
        pil_image = Image.open(input_image)
        image_array = np.array(pil_image)
        return_pil = True
    elif isinstance(input_image, Image.Image):
        # PIL.Image输入 - 转换为numpy数组方便计算
        image_array = np.array(input_image)
        return_pil = True
    elif isinstance(input_image, np.ndarray):
        # numpy数组输入
        image_array = input_image.copy()
        return_pil = False
    else:
        raise ValueError(f"不支持的输入格式: {type(input_image)}")
    
    # 生成单级mipmap
    mipmap_array = generate_lightmap_mipmap_single_level(image_array)
    
    # 根据原始输入类型确定返回格式
    if return_pil:
        result_image = Image.fromarray(mipmap_array)
    else:
        result_image = mipmap_array
    
    # 如果提供了输出路径，保存文件
    if output_path is not None:
        if isinstance(result_image, np.ndarray):
            Image.fromarray(result_image).save(output_path)
        else:
            result_image.save(output_path)
        print(f"Mipmap已保存到: {output_path}")
    
    return result_image

def generate_lightmap_mipmap_single_level(image_array: np.ndarray) -> np.ndarray:
    """
    生成单级lightmap mipmap，参考虚幻引擎算法
    
    Args:
        image_array: 输入图像数组
        
    Returns:
        np.ndarray: 1/2分辨率的mipmap数组
    """
    # 检查图片维度
    if len(image_array.shape) < 2:
        raise ValueError("输入图片至少需要2个维度")
    
    # 获取原始尺寸
    original_height, original_width = image_array.shape[:2]
    
    # 计算新尺寸（1/2分辨率）
    new_height = max(1, original_height // 2)
    new_width = max(1, original_width // 2)
    
    # 计算mip factor
    mip_factor_x = original_width // new_width
    mip_factor_y = original_height // new_height
    
    # 创建coverage数组（简化处理：非零像素为有效）
    if len(image_array.shape) == 3:
        # 彩色图像，使用alpha通道或亮度作为coverage
        if image_array.shape[2] == 4:
            # 有alpha通道
            coverage_array = (image_array[:, :, 3] > 0).astype(np.int8) * 127
        else:
            # 使用亮度作为coverage
            gray = np.dot(image_array[:, :, :3], [0.299, 0.587, 0.114])
            coverage_array = (gray > 0).astype(np.int8) * 127
    else:
        # 灰度图像
        coverage_array = (image_array > 0).astype(np.int8) * 127
    
    # 转换为线性颜色空间（简化处理，假设输入已经是线性的）
    linear_image = image_array.astype(np.float32) / 255.0
    
    # 生成下一级mip
    mipmap_linear, mipmap_coverage = downsample_with_coverage(
        linear_image, coverage_array, new_width, new_height, mip_factor_x, mip_factor_y
    )
    
    # 执行dilate操作
    mipmap_linear, mipmap_coverage = dilate_lightmap(mipmap_linear, mipmap_coverage)
    
    # 转换回uint8
    mipmap_array = (np.clip(mipmap_linear, 0, 1) * 255).astype(np.uint8)
    
    return mipmap_array

def downsample_with_coverage(
    image_array: np.ndarray, 
    coverage_array: np.ndarray,
    dest_width: int,
    dest_height: int,
    mip_factor_x: int,
    mip_factor_y: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    基于coverage信息的降采样，参考虚幻引擎算法
    
    Args:
        image_array: 线性颜色空间的图像数组
        coverage_array: coverage信息数组
        dest_width: 目标宽度
        dest_height: 目标高度
        mip_factor_x: X方向的缩放因子
        mip_factor_y: Y方向的缩放因子
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: (降采样后的图像, 降采样后的coverage)
    """
    # 创建结果数组
    if len(image_array.shape) == 3:
        channels = image_array.shape[2]
        result_image = np.zeros((dest_height, dest_width, channels), dtype=np.float32)
    else:
        result_image = np.zeros((dest_height, dest_width), dtype=np.float32)
    
    result_coverage = np.zeros((dest_height, dest_width), dtype=np.int8)
    
    # 遍历目标图像的每个像素
    for y in range(dest_height):
        for x in range(dest_width):
            # 计算源图像中对应的区域
            min_source_y = y * mip_factor_y
            max_source_y = (y + 1) * mip_factor_y
            min_source_x = x * mip_factor_x
            max_source_x = (x + 1) * mip_factor_x
            
            # 确保不超出边界
            max_source_y = min(max_source_y, image_array.shape[0])
            max_source_x = min(max_source_x, image_array.shape[1])
            
            # 累积颜色和coverage
            if len(image_array.shape) == 3:
                accumulated_color = np.zeros(channels, dtype=np.float32)
            else:
                accumulated_color = 0.0
            
            total_coverage = 0
            
            # 遍历源区域
            for source_y in range(min_source_y, max_source_y):
                for source_x in range(min_source_x, max_source_x):
                    source_coverage = coverage_array[source_y, source_x]
                    if source_coverage > 0:
                        source_color = image_array[source_y, source_x]
                        accumulated_color += source_color * source_coverage
                        total_coverage += source_coverage
            
            # 计算结果
            if total_coverage > 0:
                result_image[y, x] = accumulated_color / total_coverage
                result_coverage[y, x] = total_coverage // (mip_factor_x * mip_factor_y)
            else:
                result_image[y, x] = 0
                result_coverage[y, x] = 0
    
    return result_image, result_coverage

def dilate_lightmap(image_array: np.ndarray, coverage_array: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    对lightmap执行dilate操作，将有效像素扩展到相邻的无效像素
    参考虚幻引擎算法
    
    Args:
        image_array: 图像数组
        coverage_array: coverage数组
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: (处理后的图像, 处理后的coverage)
    """
    height, width = image_array.shape[:2]
    result_image = image_array.copy()
    result_coverage = coverage_array.copy()
    
    # 权重矩阵（参考虚幻引擎）
    weights = np.array([
        [1, 255, 1],
        [255, 0, 255],
        [1, 255, 1]
    ], dtype=np.float32)
    
    # 遍历每个像素
    for y in range(height):
        for x in range(width):
            # 只处理coverage为0的像素
            if coverage_array[y, x] == 0:
                if len(image_array.shape) == 3:
                    channels = image_array.shape[2]
                    accumulated_color = np.zeros(channels, dtype=np.float32)
                else:
                    accumulated_color = 0.0
                
                total_coverage = 0
                
                # 检查3x3邻域
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        if dx == 0 and dy == 0:
                            continue
                            
                        source_y = y + dy
                        source_x = x + dx
                        
                        # 边界检查
                        if (source_y >= 0 and source_y < height and 
                            source_x >= 0 and source_x < width):
                            
                            source_coverage = coverage_array[source_y, source_x]
                            if source_coverage > 0:
                                source_color = image_array[source_y, source_x]
                                weight = weights[dx + 1, dy + 1]
                                
                                accumulated_color += source_color * source_coverage * weight
                                total_coverage += source_coverage * weight
                
                # 如果找到了有效的邻居，设置像素值
                if total_coverage > 0:
                    result_image[y, x] = accumulated_color / total_coverage
                    result_coverage[y, x] = -1  # 标记为dilated
    
    return result_image, result_coverage

def generate_lightmap_mipmap_chain(
    input_image: Union[np.ndarray, Image.Image, str],
    num_mips: int = 0,
    output_dir: Optional[str] = None
) -> List[np.ndarray]:
    """
    生成完整的lightmap mipmap链，参考虚幻引擎算法
    
    Args:
        input_image: 输入图片
        num_mips: 生成的mip级数，0表示自动计算
        output_dir: 输出目录，如果提供则保存所有mip级别
        
    Returns:
        List[np.ndarray]: mipmap链，从原图到最小尺寸
    """
    # 统一转换为numpy数组
    if isinstance(input_image, str):
        if not os.path.exists(input_image):
            raise FileNotFoundError(f"输入文件不存在: {input_image}")
        pil_image = Image.open(input_image)
        image_array = np.array(pil_image)
    elif isinstance(input_image, Image.Image):
        image_array = np.array(input_image)
    elif isinstance(input_image, np.ndarray):
        image_array = input_image.copy()
    else:
        raise ValueError(f"不支持的输入格式: {type(input_image)}")
    
    # 计算mip级数
    if num_mips == 0:
        height, width = image_array.shape[:2]
        num_mips = int(np.log2(max(width, height))) + 1
    
    # 生成mipmap链
    mipmap_chain = [image_array]
    current_mip = image_array
    
    for mip_index in range(1, num_mips):
        # 检查是否已经到达最小尺寸
        if current_mip.shape[0] <= 1 and current_mip.shape[1] <= 1:
            break
            
        # 生成下一级mip
        current_mip = generate_lightmap_mipmap_single_level(current_mip)
        mipmap_chain.append(current_mip)
    
    # 保存mipmap链
    if output_dir is not None:
        os.makedirs(output_dir, exist_ok=True)
        for i, mip in enumerate(mipmap_chain):
            output_path = os.path.join(output_dir, f"mip_{i}.png")
            Image.fromarray(mip).save(output_path)
            print(f"Mip {i} 已保存到: {output_path}")
    
    return mipmap_chain 