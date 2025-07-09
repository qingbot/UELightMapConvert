# 生成mipmap

import numpy as np
from PIL import Image
from typing import Union, Optional
import os

def generate_mipmap_half_resolution(
    input_image: Union[np.ndarray, Image.Image, str],
    output_path: Optional[str] = None,
    interpolation_method: str = "lanczos"
) -> Union[np.ndarray, Image.Image]:
    """
    生成原图1/2分辨率的mipmap
    
    Args:
        input_image: 输入图片，可以是以下格式之一：
            - np.ndarray: numpy数组形式的图片数据 (H, W, C)
            - PIL.Image.Image: PIL图片对象
            - str: 图片文件路径
        output_path: 可选，输出文件路径，如果提供则会保存到文件
        interpolation_method: 插值方法，可选值：
            - "lanczos": Lanczos插值（默认，高质量）
            - "bilinear": 双线性插值
            - "nearest": 最近邻插值
            - "bicubic": 双三次插值
    
    Returns:
        Union[np.ndarray, Image.Image]: 1/2分辨率的图片
            - 如果输入是numpy数组，返回numpy数组
            - 如果输入是PIL.Image，返回PIL.Image
            - 如果输入是文件路径，返回PIL.Image
    
    Raises:
        ValueError: 当输入格式不支持时
        FileNotFoundError: 当输入文件路径不存在时
    """
    # 函数实现由用户自己完成
    pass 