import os
import json
import xml.etree.ElementTree as ET
import uuid
import argparse
from datetime import datetime
import GlobalParameter

# 该程序从给定的文件夹中读取全部的xml文件，然后读取xml文件中的物体信息，
# 然后读取json文件中的物体信息，然后匹配xml和json中的物体信息
# 将匹配的结果，从二者中提取出lightmap相关的数据，然后更新到xml文件中

# 注册命名空间
ET.register_namespace('', "http://www.boominggames.com")
# XML命名空间
XML_NS = {"ns": "http://www.boominggames.com"}

def generate_sketum_id():
    """生成唯一的sketum_id"""
    return str(uuid.uuid4()).replace('-', '').upper()[:16]

def format_float(value):
    """格式化浮点数,保持最大精度""" 
    return f"{value:.6f}"

def read_xml_objects(xml_path):
    """
    从XML文件中读取所有物体信息，包括名字和position
    
    Returns:
        dict: 包含物体信息的字典，格式为 {名字: {position: [...], data_ref: ...}}
    """
    try:
        print(f"正在读取XML文件: {xml_path}")
        # 使用显式的编码方式读取XML
        try:
            parser = ET.XMLParser(encoding="utf-8")
            tree = ET.parse(xml_path, parser=parser)
        except Exception as e:
            print(f"使用utf-8解析失败，尝试使用gb2312: {str(e)}")
            parser = ET.XMLParser(encoding="gb2312")
            tree = ET.parse(xml_path, parser=parser)
            
        root = tree.getroot()
        
        objects = {}
        
        # 打印根节点及其直接子节点的标签，帮助调试
        print(f"根节点标签: {root.tag}")
        
        # 尝试多种方式查找元素
        elements = []
        
        # 方法1：查找layers节点下的元素
        layers = root.find('.//{http://www.boominggames.com}layers')
        if layers is not None:
            elements = list(layers)
            print(f"从layers节点找到 {len(elements)} 个元素")
        
        # 方法2：直接查找element元素
        if not elements:
            elements = root.findall(".//{http://www.boominggames.com}element")
            if elements:
                print(f"从命名空间查找找到 {len(elements)} 个元素")
        
        # 方法3：不使用命名空间查找
        if not elements:
            elements = root.findall(".//element")
            if elements:
                print(f"从非命名空间查找找到 {len(elements)} 个元素")
        
        # 方法4：在data节点下查找
        if not elements:
            data = root.find('.//{http://www.boominggames.com}data')
            if data is not None:
                for child in data:
                    if child.tag.endswith('element'):
                        elements.append(child)
                print(f"从data节点找到 {len(elements)} 个元素")
        
        # 方法5：遍历所有节点寻找元素
        if not elements:
            for elem in root.iter():
                if elem.tag.endswith('element') or elem.tag == 'element':
                    elements.append(elem)
            print(f"从遍历所有节点找到 {len(elements)} 个元素")
        
        print(f"总共在XML中找到 {len(elements)} 个元素")
        
        # 处理每个元素
        for element in elements:
            # 查找名称 - 使用多种可能的标签名
            name_elem = None
            for name_tag in ['name', 'n', '{http://www.boominggames.com}name', '{http://www.boominggames.com}n']:
                name_elem = element.find(name_tag)
                if name_elem is not None and name_elem.text:
                    break
            
            # 如果找不到名称，尝试从属性中获取
            if name_elem is None or not name_elem.text:
                if 'name' in element.attrib:
                    name_text = element.attrib['name']
                    # 创建一个虚拟的名称元素
                    name_elem = ET.Element('name')
                    name_elem.text = name_text
            
            # 查找位置信息
            position = None
            transform_elem = element.find("transform")
            if transform_elem is None:
                transform_elem = element.find("{http://www.boominggames.com}transform")
            
            if transform_elem is not None:
                position_elem = transform_elem.find("position")
                if position_elem is None:
                    position_elem = transform_elem.find("{http://www.boominggames.com}position")
                
                if position_elem is not None and position_elem.text:
                    try:
                        position = [float(x) for x in position_elem.text.split()]
                    except (ValueError, TypeError) as e:
                        print(f"位置转换错误: {e}, 原始文本: {position_elem.text}")
            
            # 如果找不到transform/position，直接查找position元素
            if position is None:
                position_elem = element.find("position")
                if position_elem is None:
                    position_elem = element.find("{http://www.boominggames.com}position")
                
                if position_elem is not None and position_elem.text:
                    try:
                        position = [float(x) for x in position_elem.text.split()]
                    except (ValueError, TypeError) as e:
                        print(f"位置转换错误: {e}, 原始文本: {position_elem.text}")
            
            # 查找data_ref信息
            data_ref = None
            for data_ref_tag in ["data_ref", "{http://www.boominggames.com}data_ref"]:
                data_ref_elem = element.find(data_ref_tag)
                if data_ref_elem is not None and data_ref_elem.text:
                    data_ref = data_ref_elem.text.strip()
                    break
            
            # 如果找不到data_ref，尝试从属性中获取
            if data_ref is None:
                if 'data_ref' in element.attrib:
                    data_ref = element.attrib['data_ref']
            
            # 如果有名称和位置，则添加到对象列表
            if name_elem is not None and name_elem.text and position:
                obj_name = name_elem.text.strip()
                objects[obj_name] = {
                    "position": position,
                    "data_ref": data_ref
                }
        
        print(f"共找到 {len(objects)} 个有效物体")
        return objects
    
    except Exception as e:
        print(f"读取XML文件失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def read_json_objects(json_path):
    """
    从JSON文件中读取所有物体信息，包括名字、position、CoefAdd、CoefScale和BiasScale
    
    支持多种JSON格式:
    1. 扁平结构: { "物体名": { "数据"... } }
    2. 嵌套结构: { "StaticMesh": { "物体名": { "数据"... } } }
    3. 测试格式: { "Static Mesh": { "物体名": { "Name", "Location", "LightMap"... } } }
    
    Returns:
        dict: 包含物体信息的字典
    """
    try:
        print(f"正在读取JSON文件: {json_path}")
        
        # 使用显式UTF-8编码读取文件以正确处理中文
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        if not json_data:
            print("JSON文件为空或格式错误")
            return {}
            
        print(f"JSON根级键: {list(json_data.keys())}")
        
        # 打印部分JSON内容用于调试
        print("JSON部分内容示例:")
        if len(json_data) > 0:
            first_key = list(json_data.keys())[0]
            print(f"第一个键: {first_key}")
            if isinstance(json_data[first_key], dict) and len(json_data[first_key]) > 0:
                first_obj_name = list(json_data[first_key].keys())[0]
                print(f"第一个对象名: {first_obj_name}")
                print(f"第一个对象数据结构: {list(json_data[first_key][first_obj_name].keys())}")
            
        objects = {}
        
        # 检查格式类型并处理
        if "Static Mesh" in json_data and isinstance(json_data["Static Mesh"], dict):
            print("检测到特殊格式: 'Static Mesh' 结构")
            # 使用Static Mesh下的物体
            for obj_name, obj_data in json_data["Static Mesh"].items():
                process_special_object(obj_name, obj_data, objects)
        elif "StaticMesh" in json_data and isinstance(json_data["StaticMesh"], dict):
            print("检测到嵌套的StaticMesh结构")
            # 使用StaticMesh下的物体
            for obj_name, obj_data in json_data["StaticMesh"].items():
                process_object(obj_name, obj_data, objects)
        else:
            # 尝试扁平结构 (物体名称 -> 数据)
            print("尝试解析扁平结构")
            for obj_name, obj_data in json_data.items():
                if isinstance(obj_data, dict):
                    # 检测是否是测试数据格式（包含中文或'测试'字样）
                    if "测试" in obj_name or "LightMap" in obj_data:
                        process_object(obj_name, obj_data, objects)
        
        print(f"从JSON中加载了 {len(objects)} 个物体")
        
        # 打印部分对象名称用于调试
        if objects:
            print("加载的部分对象名称:")
            for i, name in enumerate(list(objects.keys())[:5]):
                print(f"对象 {i+1}: {name}")
        
        # 如果没有找到物体，打印更多调试信息
        if not objects:
            print("未找到物体，打印JSON结构:")
            print_json_structure(json_data)
            
        return objects
    
    except Exception as e:
        print(f"读取JSON文件失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def process_special_object(obj_name, obj_data, result_dict):
    """处理特殊格式的对象（'Static Mesh'格式）"""
    if not isinstance(obj_data, dict):
        print(f"对象 {obj_name} 的数据不是字典类型，跳过")
        return
    
    # 提取位置信息
    position = None
    if "Location" in obj_data and isinstance(obj_data["Location"], list):
        position = obj_data["Location"]
        print(f"找到位置信息: {position}")
    
    if not position:
        print(f"对象 {obj_name} 缺少位置信息，跳过")
        return
    
    # 提取光照图数据
    lightmap_data = {}
    if "LightMap" in obj_data and isinstance(obj_data["LightMap"], dict):
        lm_data = obj_data["LightMap"]
        
        # 提取CoefAdd - 修改逻辑，不再要求长度>11，不再只取固定索引
        if "CoefAdd" in lm_data and isinstance(lm_data["CoefAdd"], list):
            lightmap_data["CoefAdd"] = lm_data["CoefAdd"]
            print(f"找到CoefAdd: {lightmap_data['CoefAdd']}")
        
        # 提取CoefScale - 修改逻辑，不再要求长度>11，不再只取固定索引
        if "CoefScale" in lm_data and isinstance(lm_data["CoefScale"], list):
            lightmap_data["CoefScale"] = lm_data["CoefScale"]
            print(f"找到CoefScale: {lightmap_data['CoefScale']}")
        
        # 提取BiasScale
        if "BiasScale" in lm_data:
            lightmap_data["BiasScale"] = lm_data["BiasScale"]
            print(f"找到BiasScale: {lightmap_data['BiasScale']}")
        
        # 提取LQ (低质量贴图)
        if "LQ" in lm_data:
            lightmap_data["LQ"] = lm_data["LQ"]
            print(f"找到LQ: {lightmap_data['LQ']}")
    
    # 即使没有完整的光照图数据，也添加物体 - 放宽条件
    if position:
        result_dict[obj_name] = {
            "position": position,
            "lightmap": lightmap_data
        }
        print(f"成功加载特殊格式JSON物体: {obj_name}, 位置: {position}")
        return
    
    print(f"对象 {obj_name} 缺少位置信息，跳过")

def process_object(obj_name, obj_data, result_dict):
    """处理单个物体的数据并添加到结果字典中"""
    if not isinstance(obj_data, dict):
        print(f"对象 {obj_name} 的数据不是字典类型，跳过")
        return
        
    # 提取位置信息
    position = None
    location_keys = ["Location", "location", "LOCATION", "pos", "position", "Position"]
    
    for key in location_keys:
        if key in obj_data and isinstance(obj_data[key], list):
            position = obj_data[key]
            print(f"找到位置信息 (键: {key}): {position}")
            break
    
    if not position:
        print(f"对象 {obj_name} 缺少位置信息，跳过")
        return
        
    # 提取光照图数据
    lightmap_data = {}
    # 查找lightmap相关的键
    lightmap_key = None
    for key in ["LightMap", "lightmap", "Lightmap", "LIGHTMAP"]:
        if key in obj_data:
            lightmap_key = key
            print(f"找到光照图键: {key}")
            break
    
    if lightmap_key:
        lm_data = obj_data[lightmap_key]
        
        # 提取CoefAdd - 修改逻辑，不再要求长度>11，不再只取固定索引
        if "CoefAdd" in lm_data and isinstance(lm_data["CoefAdd"], list):
            lightmap_data["CoefAdd"] = lm_data["CoefAdd"]
            print(f"找到CoefAdd: {lightmap_data['CoefAdd']}")
        
        # 提取CoefScale - 修改逻辑，不再要求长度>11，不再只取固定索引
        if "CoefScale" in lm_data and isinstance(lm_data["CoefScale"], list):
            lightmap_data["CoefScale"] = lm_data["CoefScale"]
            print(f"找到CoefScale: {lightmap_data['CoefScale']}")
        
        # 提取BiasScale
        if "BiasScale" in lm_data:
            lightmap_data["BiasScale"] = lm_data["BiasScale"]
            print(f"找到BiasScale: {lightmap_data['BiasScale']}")
        
        # 提取LQ (低质量贴图)
        if "LQ" in lm_data:
            lightmap_data["LQ"] = lm_data["LQ"]
            print(f"找到LQ: {lightmap_data['LQ']}")
    
    # 即使没有完整的光照图数据，也添加物体 - 放宽条件
    if position:
        result_dict[obj_name] = {
            "position": position,
            "lightmap": lightmap_data
        }
        print(f"成功加载JSON物体: {obj_name}, 位置: {position}")
        return
    
    print(f"对象 {obj_name} 缺少位置信息，跳过")

def print_json_structure(data, level=0, max_level=3):
    """打印JSON的结构以便调试"""
    indent = "  " * level
    
    if level >= max_level:
        print(f"{indent}...")
        return
        
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                print(f"{indent}{key}: ")
                print_json_structure(value, level + 1, max_level)
            else:
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                print(f"{indent}{key}: {value_str}")
    elif isinstance(data, list):
        if data:
            print(f"{indent}[数组，{len(data)}个元素]")
            if level < max_level - 1:
                print_json_structure(data[0], level + 1, max_level)
        else:
            print(f"{indent}[空数组]")
    else:
        print(f"{indent}{data}")

def match_objects(xml_objects, json_objects):
    """
    匹配XML和JSON中的物体，仅使用精确的字符串匹配
    
    Returns:
        list: 包含匹配信息的列表，格式为 [{xml_name, json_name, data_ref, lightmap_data}, ...]
    """
    matches = []
    
    # 仅使用精确字符串匹配
    print("\n开始进行精确字符串匹配...")
    for xml_name, xml_obj in xml_objects.items():
        # 检查是否有完全匹配的JSON对象键名
        if xml_name in json_objects:
            matches.append({
                "xml_name": xml_name,
                "json_name": xml_name,
                "data_ref": xml_obj["data_ref"],
                "lightmap_data": json_objects[xml_name]["lightmap"]
            })
            print(f"精确匹配成功: XML物体 '{xml_name}' 与 JSON物体 '{xml_name}'")
    
    # 统计匹配情况
    matched_xml_names = [m["xml_name"] for m in matches]
    unmatched_xml = {name: obj for name, obj in xml_objects.items() if name not in matched_xml_names}
    
    print(f"\n匹配结果: 精确匹配成功 {len(matches)} 个物体，未匹配 {len(unmatched_xml)} 个物体")
    
    # 测试模式下的特殊处理已被移除，遵循严格的精确匹配原则
    
    return matches

def create_lightmap_element(data_ref, lightmap_data, lightmap_path):
    """
    创建一个lightmap元素
    
    Args:
        data_ref: 目标的data_ref
        lightmap_data: 光照图数据
        lightmap_path: 光照图路径
        
    Returns:
        Element: 创建的lightmap元素
    """
    element = ET.Element("element", {"sketum_id": generate_sketum_id()})
    
    # 添加Target元素
    target = ET.SubElement(element, "Target")
    target.text = data_ref if data_ref else "FFFF"
    
    # 添加CoefAdd元素
    coef_add = ET.SubElement(element, "CoefAdd")
    if "CoefAdd" in lightmap_data and isinstance(lightmap_data["CoefAdd"], list):
        # 如果数组长度足够，取索引8-11位置的值，否则使用整个数组或默认值
        if len(lightmap_data["CoefAdd"]) > 11:
            coef_add_values = lightmap_data["CoefAdd"][8:12]
        elif len(lightmap_data["CoefAdd"]) >= 4:
            coef_add_values = lightmap_data["CoefAdd"][:4]
        else:
            coef_add_values = [1.0, 0.0, 0.0, 0.0]
        coef_add_value = " ".join([format_float(val) for val in coef_add_values])
    else:
        coef_add_value = "1.000000 0.000000 0.000000 0.000000"
    coef_add.text = coef_add_value
    
    # 添加CoefScale元素
    coef_scale = ET.SubElement(element, "CoefScale")
    if "CoefScale" in lightmap_data and isinstance(lightmap_data["CoefScale"], list):
        # 如果数组长度足够，取索引8-11位置的值，否则使用整个数组或默认值
        if len(lightmap_data["CoefScale"]) > 11:
            coef_scale_values = lightmap_data["CoefScale"][8:12]
        elif len(lightmap_data["CoefScale"]) >= 4:
            coef_scale_values = lightmap_data["CoefScale"][:4]
        else:
            coef_scale_values = [1.0, 1.0, 0.0, 0.0]
        coef_scale_value = " ".join([format_float(val) for val in coef_scale_values])
    else:
        coef_scale_value = "1.000000 1.000000 0.000000 0.000000"
    coef_scale.text = coef_scale_value
    
    # 添加BiasScale元素
    bias_scale = ET.SubElement(element, "BiasScale")
    if "BiasScale" in lightmap_data and isinstance(lightmap_data["BiasScale"], list):
        if len(lightmap_data["BiasScale"]) >= 4:
            bias_scale_values = lightmap_data["BiasScale"][:4]
        else:
            bias_scale_values = [1.0, 0.0, 0.0, 0.0]
        bias_scale_value = " ".join([format_float(val) for val in bias_scale_values])
    else:
        bias_scale_value = "1.000000 0.000000 0.000000 0.000000"
    bias_scale.text = bias_scale_value
    
    # 添加LightMap元素
    light_map = ET.SubElement(element, "LightMap")
    
    # 添加url元素
    url = ET.SubElement(light_map, "url")
    if "LQ" in lightmap_data:
        lq_name = lightmap_data["LQ"]
        url.text = f"{lightmap_path}/{lq_name}.texture.ast"
    else:
        url.text = f"{lightmap_path}/default.texture.ast"
    
    # 添加guid元素
    guid = ET.SubElement(light_map, "guid")
    
    # 添加parameter元素
    parameter = ET.SubElement(light_map, "parameter")
    parameters = ET.SubElement(parameter, "parameters")
    
    return element

def create_or_update_lightmap_xml(matches, output_path, lightmap_path, overwrite_all=False):
    """
    创建或更新lightmap XML文件
    
    Args:
        matches: 匹配的物体列表
        output_path: 输出文件路径
        lightmap_path: 光照图路径
        overwrite_all: 是否完全覆盖生成新文件
    """
    try:
        # 检查是否需要完全覆盖
        if overwrite_all and os.path.exists(output_path):
            print(f"启用完全覆盖模式，将创建全新XML文件替换 {output_path}")
            root, lightmap_data = create_new_xml_structure(lightmap_path)
            tree = ET.ElementTree(root)
        # 创建新的XML或加载现有XML
        elif os.path.exists(output_path):
            print(f"更新现有的XML文件: {output_path}")
            try:
                tree = ET.parse(output_path)
                root = tree.getroot()
                
                # 查找lightmap_data元素
                lightmap_data = root.find("lightmap_data")
                if lightmap_data is None:
                    lightmap_data = root.find("ns:lightmap_data", XML_NS)
                
                # 如果找不到，创建一个
                if lightmap_data is None:
                    print("在XML中找不到lightmap_data元素，正在创建...")
                    lightmap_data = ET.SubElement(root, "lightmap_data")
                else:
                    # 清除现有元素
                    print(f"找到现有的lightmap_data元素，包含 {len(lightmap_data)} 个子元素，正在清除...")
                    # 保存元素数量以便输出日志
                    original_element_count = len(lightmap_data)
                    lightmap_data.clear()
                    print(f"已清除原有的 {original_element_count} 个lightmap_data子元素，准备覆盖数据")
            except Exception as e:
                print(f"读取现有XML文件失败: {str(e)}，创建新文件")
                # 创建新的XML文件
                root, lightmap_data = create_new_xml_structure(lightmap_path)
                tree = ET.ElementTree(root)
        else:
            print(f"创建新的XML文件: {output_path}")
            # 创建新的XML结构
            root, lightmap_data = create_new_xml_structure(lightmap_path)
            tree = ET.ElementTree(root)
        
        # 添加所有匹配的物体到lightmap_data
        added_count = 0
        for match in matches:
            try:
                element = create_lightmap_element(match["data_ref"], match["lightmap_data"], lightmap_path)
                lightmap_data.append(element)
                added_count += 1
            except Exception as e:
                print(f"添加物体 {match['xml_name']} 时出错: {str(e)}")
        
        # 格式化XML以便更好的可读性
        def indent(elem, level=0):
            i = "\n" + level*"  "
            if len(elem):
                if not elem.text or not elem.text.strip():
                    elem.text = i + "  "
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i
                for e in elem:
                    indent(e, level+1)
                if not e.tail or not e.tail.strip():
                    e.tail = i
            else:
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i
        
        # 应用缩进
        indent(root)
        
        # 保存XML
        tree.write(output_path, encoding='UTF-8', xml_declaration=True)
        
        if overwrite_all and os.path.exists(output_path):
            print(f"成功使用全新的XML文件替换 {output_path}，包含 {added_count} 个物体")
        elif os.path.exists(output_path):
            print(f"成功写入 {added_count} 个物体到 {output_path}，完全覆盖了原有的lightmap_data内容")
        else:
            print(f"成功创建包含 {added_count} 个物体的新XML文件 {output_path}")
        
    except Exception as e:
        print(f"创建或更新lightmap XML失败: {str(e)}")
        import traceback
        traceback.print_exc()

def create_new_xml_structure(lightmap_path):
    """
    创建新的XML结构
    
    Returns:
        tuple: (root元素, lightmap_data元素)
    """
    # 创建根元素
    root = ET.Element("LevelLightmapData", {"xmlns": "http://www.boominggames.com"})
    
    # 添加header元素
    header = ET.SubElement(root, "header")
    guid = ET.SubElement(header, "guid")
    guid.text = generate_sketum_id()
    
    description = ET.SubElement(header, "description")
    version = ET.SubElement(description, "version")
    version.text = "0"
    
    tags = ET.SubElement(description, "tags")
    comments = ET.SubElement(description, "comments")
    thumbnails = ET.SubElement(description, "thumbnails")
    client_only = ET.SubElement(description, "client_only")
    client_only.text = "0"
    
    data_reference = ET.SubElement(header, "data_reference")
    template = ET.SubElement(header, "template")
    is_template = ET.SubElement(template, "is_template")
    is_template.text = "0"
    interface_parameter_pathes = ET.SubElement(template, "interface_parameter_pathes")
    
    cooked_info = ET.SubElement(header, "cooked_info")
    file_id = ET.SubElement(cooked_info, "file_id")
    file_id.text = "Donot touch"
    md5 = ET.SubElement(cooked_info, "md5")
    referenced_asset_count = ET.SubElement(cooked_info, "referenced_asset_count")
    referenced_asset_count.text = "0"
    
    # 添加variable_interface元素
    variable_interface = ET.SubElement(root, "variable_interface")
    variables = ET.SubElement(variable_interface, "variables")
    variable_references_map = ET.SubElement(variable_interface, "variable_references_map")
    
    # 添加generated_traits元素
    generated_traits = ET.SubElement(root, "generated_traits")
    
    # 添加lightmap_data元素
    lightmap_data = ET.SubElement(root, "lightmap_data")
    
    return root, lightmap_data

def main():
    parser = argparse.ArgumentParser(description="匹配XML和JSON物体并生成lightmap XML")
    
    parser.add_argument("--scene", "-s", type=str, default=GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME, 
                      help=f"要处理的场景名称，默认为{GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME}")
    
    parser.add_argument("--force-match", "-f", action="store_true",
                      help="强制匹配模式，尝试匹配所有JSON物体")
                      
    parser.add_argument("--test-mode", "-t", action="store_true",
                      help="测试模式，使用测试数据进行匹配")
    
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="详细输出模式，打印更多调试信息")
    
    parser.add_argument("--overwrite-all", "-o", action="store_true",
                      help="完全覆盖模式，生成全新的XML文件而不是仅替换<lightmap_data>节点")
    
    args = parser.parse_args()
    
    # 检查场景是否存在
    scene_name = args.scene
    if scene_name not in GlobalParameter.ALL_LIGHT_MAP_DATA:
        print(f"错误: 场景 '{scene_name}' 不存在")
        print(f"可用场景: {', '.join(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())}")
        return
    
    # 获取场景配置
    scene_config = GlobalParameter.ALL_LIGHT_MAP_DATA[scene_name]
    
    # 获取路径信息
    xml_folder_path = scene_config["source_scene_xml_folder_path"]
    json_path = scene_config["source_lightmap_json_path"]
    output_path = scene_config["lightmap_data_ast_path_in_chaos"]
    lightmap_path = scene_config["lightmap_path_in_chaos_assets"]

    print(f"\n处理场景: {scene_name}")
    print(f"XML文件夹路径: {xml_folder_path}")
    print(f"JSON文件路径: {json_path}")
    print(f"输出文件路径: {output_path}")
    print(f"光照图路径: {lightmap_path}\n")
    
    # 获取XML文件列表
    xml_files = []
    try:
        # 如果是测试模式，直接使用测试XML文件
        if args.test_mode:
            xml_files = ["test_scene.xml"]
        else:
            # 从文件夹中获取所有.ast文件
            for file in os.listdir(xml_folder_path):
                if file.endswith('.ast'):
                    xml_files.append(os.path.join(xml_folder_path, file))
    except Exception as e:
        print(f"读取XML文件夹失败: {str(e)}")
        return
    
    if not xml_files:
        print(f"未在{xml_folder_path}找到任何.ast或.xml文件")
        return
    
    print(f"找到 {len(xml_files)} 个XML文件需要处理")
    
    # 读取JSON物体
    json_objects = read_json_objects(json_path)
    if not json_objects:
        print("未能从JSON中读取物体，程序退出")
        return
    
    # 收集所有XML物体
    all_xml_objects = {}
    for xml_file in xml_files:
        print(f"\n处理XML文件: {xml_file}")
        xml_objects = read_xml_objects(xml_file)
        all_xml_objects.update(xml_objects)
    
    print(f"\n所有XML文件中共找到 {len(all_xml_objects)} 个物体")
    
    all_matches = []
    
    if args.force_match:
        # 强制匹配模式：仅使用精确字符串匹配
        print("\n启用强制匹配模式，仅使用精确字符串匹配...")
        
        for xml_name, xml_obj in all_xml_objects.items():
            # 检查是否有精确匹配的JSON对象键名
            if xml_name in json_objects:
                all_matches.append({
                    "xml_name": xml_name,
                    "json_name": xml_name,
                    "data_ref": xml_obj["data_ref"],
                    "lightmap_data": json_objects[xml_name]["lightmap"]
                })
                print(f"强制精确匹配: XML物体 '{xml_name}' 与 JSON物体 '{xml_name}'")
        
        # 统计未匹配的物体
        matched_xml_names = [m["xml_name"] for m in all_matches]
        unmatched_xml = {name: obj for name, obj in all_xml_objects.items() if name not in matched_xml_names}
        print(f"\n强制匹配模式下，精确匹配成功 {len(all_matches)} 个物体，仍有 {len(unmatched_xml)} 个物体未匹配")
    else:
        # 常规匹配模式：处理每个XML文件
        for xml_file in xml_files:
            print(f"\n处理XML文件: {xml_file}")
            
            # 读取XML物体
            xml_objects = read_xml_objects(xml_file)
            if not xml_objects:
                print(f"未能从{xml_file}中读取物体，跳过此文件")
                continue
            
            # 匹配物体
            file_matches = match_objects(xml_objects, json_objects)
            if not file_matches:
                print(f"在{xml_file}中未找到匹配的物体，跳过此文件")
                continue
            
            all_matches.extend(file_matches)
    
    if not all_matches:
        print("未找到任何匹配的物体，程序退出")
        return
    
    print(f"\n所有文件处理完成，共找到 {len(all_matches)} 个匹配物体")
    
    # 创建或更新lightmap XML
    create_or_update_lightmap_xml(all_matches, output_path, lightmap_path, args.overwrite_all)
    
    print("处理完成!")

if __name__ == "__main__":
    main() 