import json
import xml.etree.ElementTree as ET
import uuid
import os
from PIL import Image

# 全局变量
SOURCE_XML_PATH = "C:/Users/qingbo.tang/Desktop/ai/basic_level.terrain.ast"  # 源XML文件路径

# 注册命名空间
ET.register_namespace('', "http://www.boominggames.com")

def generate_sketum_id():
    """生成唯一的sketum_id"""
    return str(uuid.uuid4()).replace('-', '').upper()[:16]

def format_float(value):
    """格式化浮点数，保持最大精度""" 
    # 使用科学计数法并保留17位有效数字（Python float的最大精度）
    return f"{value:.17g}"
                        
def create_coef_element(parent, coef_data):
    """创建一个系数元素"""      
    # 创建主element节点      
    element = ET.SubElement(parent, "element", {"sketum_id": generate_sketum_id()})
                        
    # 创建CoefAdd节点       
    coef_add = ET.SubElement(element, "CoefAdd")
    for value in coef_data['coef_add']:
        add_element = ET.SubElement(coef_add, "element", {"sketum_id": generate_sketum_id()})
        add_element.text = format_float(value)
                        
    # 创建CoefScale节点     
    coef_scale = ET.SubElement(element, "CoefScale")
    for value in coef_data['coef_scale']:
        scale_element = ET.SubElement(coef_scale, "element", {"sketum_id": generate_sketum_id()})
        scale_element.text = format_float(value)

def update_xml_with_json():
    """读取JSON数据并更新XML文件"""
    # 读取源XML文件
    if not os.path.exists(SOURCE_XML_PATH):
        raise FileNotFoundError(f"找不到源XML文件: {SOURCE_XML_PATH}")
    
    tree = ET.parse(SOURCE_XML_PATH)
    root = tree.getroot()
    
    # 查找TerrainLightmapCoef节点（使用完整的命名空间路径）
    ns = {"ns": "http://www.boominggames.com"}
    terrain_coef = root.find(".//ns:TerrainLightmapCoef", namespaces=ns)
    if terrain_coef is None:
        terrain_coef = ET.SubElement(root, "TerrainLightmapCoef")
    else:
        # 清除现有的element节点
        terrain_coef.clear()
    
    # 读取JSON数据
    json_path = os.path.join("C:/chaos_integrated_tools/data_analysis/scene/light/light_map", "Landscape.json")
    try:
        with open(json_path, 'r') as f:
            coef_data = json.load(f)
    except Exception as e:
        raise Exception(f"读取JSON文件失败: {str(e)}")
    
    # 为每组数据创建element节点
    for data in coef_data:
        create_coef_element(terrain_coef, data)
    
    # 保存回原文件，使用自定义的格式化方式
    tree.write(SOURCE_XML_PATH, encoding='UTF-8', xml_declaration=True)
    print(f"已更新XML文件: {SOURCE_XML_PATH}")

def main():
    try:
        update_xml_with_json()
    except Exception as e:
        print(f"处理失败: {str(e)}")

def process_image(image_path):
    """处理图像文件"""
    # 修改图像路径后缀为.bmp
    image_path = image_path.replace('.png', '.bmp')
    image_path = image_path.replace('.tga', '.bmp')
    
    # 使用PIL读取BMP图像
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            return width, height
    except Exception as e:
        print(f"处理图像文件出错: {image_path}")
        print(f"错误信息: {str(e)}")
        return None, None

if __name__ == "__main__":
    main() 