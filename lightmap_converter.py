import os
import json
import xml.etree.ElementTree as ET
import uuid
import argparse
import math
from datetime import datetime
from GlobalParameter import ALL_LIGHT_MAP_DATA

# 全局调试文件句柄
debug_file = None

def debug_print(message, also_console=True):
    """打印调试信息到文件和控制台"""
    global debug_file 
    if debug_file:
        debug_file.write(str(message) + '\n')
        debug_file.flush()  # 立即写入文件
    if also_console:
        print(message)

def init_debug_file(scene_name):
    """初始化调试文件"""
    global debug_file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_filename = f"lightmap_converter_debug_{scene_name}_{timestamp}.log"
    debug_file = open(debug_filename, 'w', encoding='utf-8')
    debug_print(f"调试日志文件: {debug_filename}")
    return debug_filename

def close_debug_file():
    """关闭调试文件"""
    global debug_file
    if debug_file:
        debug_file.close()
        debug_file = None

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

def convert_url_path_for_ast(url_path):
    """
    转换URL路径用于AST文件写入
    
    Args:
        url_path: 原始的URL路径
        
    Returns:
        str: 转换后的路径（转换为小写并将/替换为\）
    """
    if not url_path:
        return url_path
    
    # 转换为小写
    converted_path = url_path.lower()
    
    # 将所有的/替换为\
    converted_path = converted_path.replace('/', '\\')
    
    return converted_path

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
    
    # 提取光照图数据 - 必须有有效的lightmap数据才添加
    lightmap_data = {}
    has_valid_lightmap = False
    
    if "LightMap" in obj_data and isinstance(obj_data["LightMap"], dict):
        lm_data = obj_data["LightMap"]
        
        # 提取CoefAdd - 必须存在且有效
        if "CoefAdd" in lm_data and isinstance(lm_data["CoefAdd"], list) and len(lm_data["CoefAdd"]) > 0:
            lightmap_data["CoefAdd"] = lm_data["CoefAdd"]
            has_valid_lightmap = True
            print(f"找到CoefAdd: {lightmap_data['CoefAdd']}")
        
        # 提取CoefScale - 必须存在且有效
        if "CoefScale" in lm_data and isinstance(lm_data["CoefScale"], list) and len(lm_data["CoefScale"]) > 0:
            lightmap_data["CoefScale"] = lm_data["CoefScale"]
            has_valid_lightmap = True
            print(f"找到CoefScale: {lightmap_data['CoefScale']}")
        
        # 提取BiasScale
        if "BiasScale" in lm_data:
            lightmap_data["BiasScale"] = lm_data["BiasScale"]
            print(f"找到BiasScale: {lightmap_data['BiasScale']}")
        
        # 提取LQ (低质量贴图)
        if "LQ" in lm_data:
            lightmap_data["LQ"] = lm_data["LQ"]
            print(f"找到LQ: {lightmap_data['LQ']}")
    
    # 只有当有有效的lightmap数据时才添加物体
    if has_valid_lightmap and position:
        result_dict[obj_name] = {
            "position": position,
            "lightmap": lightmap_data
        }
        print(f"成功加载特殊格式JSON物体: {obj_name}, 位置: {position}, 有lightmap数据")
        return
    
    print(f"对象 {obj_name} 没有有效的lightmap数据，跳过")

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
        
    # 提取光照图数据 - 必须有有效的lightmap数据才添加
    lightmap_data = {}
    has_valid_lightmap = False
    
    # 查找lightmap相关的键
    lightmap_key = None
    for key in ["LightMap", "lightmap", "Lightmap", "LIGHTMAP"]:
        if key in obj_data:
            lightmap_key = key
            print(f"找到光照图键: {key}")
            break
    
    if lightmap_key:
        lm_data = obj_data[lightmap_key]
        
        # 提取CoefAdd - 必须存在且有效
        if "CoefAdd" in lm_data and isinstance(lm_data["CoefAdd"], list) and len(lm_data["CoefAdd"]) > 0:
            lightmap_data["CoefAdd"] = lm_data["CoefAdd"]
            has_valid_lightmap = True
            print(f"找到CoefAdd: {lightmap_data['CoefAdd']}")
        
        # 提取CoefScale - 必须存在且有效
        if "CoefScale" in lm_data and isinstance(lm_data["CoefScale"], list) and len(lm_data["CoefScale"]) > 0:
            lightmap_data["CoefScale"] = lm_data["CoefScale"]
            has_valid_lightmap = True
            print(f"找到CoefScale: {lightmap_data['CoefScale']}")
        
        # 提取BiasScale
        if "BiasScale" in lm_data:
            lightmap_data["BiasScale"] = lm_data["BiasScale"]
            print(f"找到BiasScale: {lightmap_data['BiasScale']}")
        
        # 提取LQ (低质量贴图)
        if "LQ" in lm_data:
            lightmap_data["LQ"] = lm_data["LQ"]
            print(f"找到LQ: {lightmap_data['LQ']}")
    
    # 只有当有有效的lightmap数据时才添加物体
    if has_valid_lightmap and position:
        result_dict[obj_name] = {
            "position": position,
            "lightmap": lightmap_data
        }
        print(f"成功加载JSON物体: {obj_name}, 位置: {position}, 有lightmap数据")
        return
    
    print(f"对象 {obj_name} 没有有效的lightmap数据，跳过")

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
        tuple: (matches, unmatched_xml, unmatched_json)
            matches: 包含匹配信息的列表，格式为 [{xml_name, json_name, data_ref, lightmap_data}, ...]
            unmatched_xml: 未匹配的XML物体字典
            unmatched_json: 未匹配的JSON物体字典
    """
    matches = []
    
    # 仅使用精确字符串匹配
    debug_print("\n开始进行精确字符串匹配...")
    for xml_name, xml_obj in xml_objects.items():
        # 检查是否有完全匹配的JSON对象键名
        if xml_name in json_objects:
            matches.append({
                "xml_name": xml_name,
                "json_name": xml_name,
                "data_ref": xml_obj["data_ref"],
                "lightmap_data": json_objects[xml_name]["lightmap"]
            })
            debug_print(f"精确匹配成功: XML物体 '{xml_name}' 与 JSON物体 '{xml_name}'")
    
    # 统计匹配情况
    matched_xml_names = [m["xml_name"] for m in matches]
    matched_json_names = [m["json_name"] for m in matches]
    
    unmatched_xml = {name: obj for name, obj in xml_objects.items() if name not in matched_xml_names}
    unmatched_json = {name: obj for name, obj in json_objects.items() if name not in matched_json_names}
    
    debug_print(f"\n匹配结果: 精确匹配成功 {len(matches)} 个物体")
    debug_print(f"XML中未匹配物体数量: {len(unmatched_xml)}")
    debug_print(f"JSON中未匹配物体数量: {len(unmatched_json)}")
    
    return matches, unmatched_xml, unmatched_json

def analyze_unmatched_objects(all_unmatched_xml, all_unmatched_json, target_object_name=None):
    """
    分析未匹配的物体，输出详细信息
    
    Args:
        all_unmatched_xml: 所有未匹配的XML物体
        all_unmatched_json: 所有未匹配的JSON物体
        target_object_name: 特定要查找的物体名称
    """
    debug_print("\n" + "="*80)
    debug_print("未匹配物体分析报告")
    debug_print("="*80)
    
    # 输出XML中未匹配的物体
    debug_print(f"\nXML中未匹配的物体 (共{len(all_unmatched_xml)}个):")
    debug_print("-" * 60)
    for i, (xml_name, xml_obj) in enumerate(all_unmatched_xml.items(), 1):
        debug_print(f"{i:4d}. {xml_name}")
        debug_print(f"      position: {xml_obj.get('position', 'N/A')}")
        debug_print(f"      data_ref: {xml_obj.get('data_ref', 'N/A')}")
        
        # 检查是否是目标物体
        if target_object_name and target_object_name in xml_name:
            debug_print(f"      *** 这是目标物体! ***")
    
    # 输出JSON中未匹配的物体  
    debug_print(f"\nJSON中未匹配的物体 (共{len(all_unmatched_json)}个):")
    debug_print("-" * 60)
    for i, (json_name, json_obj) in enumerate(all_unmatched_json.items(), 1):
        debug_print(f"{i:4d}. {json_name}")
        debug_print(f"      position: {json_obj.get('position', 'N/A')}")
        lightmap_data = json_obj.get('lightmap', {})
        if lightmap_data:
            debug_print(f"      lightmap keys: {list(lightmap_data.keys())}")
            if 'CoefAdd' in lightmap_data:
                debug_print(f"      CoefAdd length: {len(lightmap_data['CoefAdd']) if isinstance(lightmap_data['CoefAdd'], list) else 'not list'}")
            if 'CoefScale' in lightmap_data:
                debug_print(f"      CoefScale length: {len(lightmap_data['CoefScale']) if isinstance(lightmap_data['CoefScale'], list) else 'not list'}")
        else:
            debug_print(f"      lightmap: 空")
            
        # 检查是否包含目标物体名称的一部分
        if target_object_name:
            # 尝试部分匹配
            if target_object_name in json_name or json_name in target_object_name:
                debug_print(f"      *** 可能是目标物体的匹配项! ***")
    
    # 如果指定了目标物体，进行更详细的分析
    if target_object_name:
        debug_print(f"\n目标物体 '{target_object_name}' 详细分析:")
        debug_print("-" * 60)
        
        # 检查是否在XML中存在
        xml_found = False
        for xml_name in all_unmatched_xml.keys():
            if target_object_name in xml_name:
                debug_print(f"在XML中找到相似名称: {xml_name}")
                xml_found = True
        
        if not xml_found:
            debug_print("在XML中未找到包含此名称的物体")
        
        # 检查是否在JSON中存在相似的
        json_found = False
        debug_print("\nJSON中可能的匹配项:")
        for json_name in all_unmatched_json.keys():
            # 尝试多种匹配策略
            similarity_score = 0
            target_parts = target_object_name.split('_')
            json_parts = json_name.split('_')
            
            # 计算相同部分的数量
            common_parts = set(target_parts) & set(json_parts)
            if common_parts:
                similarity_score = len(common_parts) / max(len(target_parts), len(json_parts))
                debug_print(f"  {json_name} (相似度: {similarity_score:.2f}, 共同部分: {common_parts})")
                json_found = True
        
        if not json_found:
            debug_print("  在JSON中未找到相似的物体名称")
    
    debug_print("\n" + "="*80)

def generate_unmatched_summary(all_unmatched_xml, all_unmatched_json):
    """
    生成未匹配物体的总结报告
    
    Args:
        all_unmatched_xml: 所有未匹配的XML物体
        all_unmatched_json: 所有未匹配的JSON物体
    """
    debug_print("\n" + "="*80)
    debug_print("未匹配物体名称总结")
    debug_print("="*80)
    
    # XML未匹配物体名称列表
    debug_print(f"\n### XML中未匹配的物体名称 (共{len(all_unmatched_xml)}个) ###")
    debug_print("-" * 80)
    if all_unmatched_xml:
        for i, xml_name in enumerate(sorted(all_unmatched_xml.keys()), 1):
            debug_print(f"{i:4d}. {xml_name}")
    else:
        debug_print("无")
    
    # JSON未匹配物体名称列表
    debug_print(f"\n### JSON中未匹配的物体名称 (共{len(all_unmatched_json)}个) ###")
    debug_print("-" * 80)
    if all_unmatched_json:
        # 按名称排序便于查找
        sorted_json_names = sorted(all_unmatched_json.keys())
        for i, json_name in enumerate(sorted_json_names, 1):
            debug_print(f"{i:4d}. {json_name}")
    else:
        debug_print("无")
    
    # 添加一些分析提示
    debug_print(f"\n### 分析提示 ###")
    debug_print("-" * 80)
    debug_print(f"- XML未匹配物体数量: {len(all_unmatched_xml)}")
    debug_print(f"- JSON未匹配物体数量: {len(all_unmatched_json)}")
    
    if all_unmatched_xml and all_unmatched_json:
        debug_print(f"- 建议检查命名差异：大小写、特殊字符、前缀后缀等")
        debug_print(f"- 可以尝试部分匹配或模糊匹配来找到对应关系")
    elif len(all_unmatched_xml) > 0:
        debug_print(f"- XML中有未匹配物体，但JSON中已全部匹配，可能存在重复或映射问题")
    elif len(all_unmatched_json) > 0:
        debug_print(f"- JSON中有未匹配物体，但XML中已全部匹配，可能JSON包含了额外的物体")
    else:
        debug_print(f"- 所有物体都已匹配！")
    
    debug_print("\n" + "="*80)

def collect_all_unmatched_objects(xml_files, json_objects):
    """
    收集所有文件中未匹配的物体
    
    Returns:
        tuple: (all_unmatched_xml, all_unmatched_json)
    """
    all_unmatched_xml = {}
    all_matched_json_names = set()
    
    # 处理每个XML文件
    for xml_file in xml_files:
        debug_print(f"\n分析XML文件: {xml_file}")
        
        # 读取XML物体
        xml_objects = read_xml_objects(xml_file)
        if not xml_objects:
            debug_print(f"未能从{xml_file}中读取物体，跳过")
            continue
        
        # 匹配物体
        file_matches, unmatched_xml, unmatched_json = match_objects(xml_objects, json_objects)
        if not file_matches:
            debug_print(f"在{xml_file}中未找到匹配的物体，跳过此文件")
            continue
        
        # 收集未匹配的XML物体
        all_unmatched_xml.update(unmatched_xml)
        
        # 记录已匹配的JSON物体名称
        for match in file_matches:
            all_matched_json_names.add(match["json_name"])
    
    # 计算未匹配的JSON物体
    all_unmatched_json = {name: obj for name, obj in json_objects.items() 
                         if name not in all_matched_json_names}
    
    return all_unmatched_xml, all_unmatched_json

def create_lightmap_element(data_ref, lightmap_data, lightmap_id, converter_data=None, xml_name=None):
    """
    创建一个lightmap元素
    
    Args:
        data_ref: 目标的data_ref
        lightmap_data: 光照图数据（必须包含有效数据）
        lightmap_id: 光照图在lightmap_texture数组中的ID
        converter_data: converter数据（包含更新后的BiasScale）
        xml_name: XML物体名称（用于匹配converter数据）
        
    Returns:
        Element: 创建的lightmap元素
    """
    # 调试信息：打印传入的数据
    debug_print(f"\n=== 调试create_lightmap_element ===", False)
    debug_print(f"data_ref: {data_ref}", False)
    debug_print(f"lightmap_data类型: {type(lightmap_data)}", False)
    debug_print(f"lightmap_data内容: {lightmap_data}", False)
    debug_print(f"lightmap_id: {lightmap_id}", False)
    
    # 验证lightmap_data必须包含有效数据
    if not lightmap_data or not isinstance(lightmap_data, dict):
        debug_print(f"错误: lightmap_data为空或不是字典类型", False)
        return None
    
    # 验证必须包含CoefAdd或CoefScale中的至少一个
    has_coef_add = "CoefAdd" in lightmap_data and isinstance(lightmap_data["CoefAdd"], list) and len(lightmap_data["CoefAdd"]) > 0
    has_coef_scale = "CoefScale" in lightmap_data and isinstance(lightmap_data["CoefScale"], list) and len(lightmap_data["CoefScale"]) > 0
    
    if not (has_coef_add or has_coef_scale):
        debug_print(f"错误: lightmap_data缺少有效的CoefAdd或CoefScale数据", False)
        return None
    
    element = ET.Element("element", {"sketum_id": generate_sketum_id()})
    
    # 添加key元素（原来的Target）
    key = ET.SubElement(element, "key")
    key.text = data_ref if data_ref else "FFFF"
    
    # 添加data容器元素
    data = ET.SubElement(element, "data")
    
    # 在data容器内添加CoefAdd元素 - 只有存在有效数据时才添加
    if has_coef_add:
        coef_add = ET.SubElement(data, "CoefAdd")
        debug_print(f"\n--- 处理CoefAdd ---", False)
        coef_add_raw = lightmap_data["CoefAdd"]
        debug_print(f"原始CoefAdd数组长度: {len(coef_add_raw)}", False)
        debug_print(f"原始CoefAdd前12个元素: {coef_add_raw[:12] if len(coef_add_raw) >= 12 else coef_add_raw}", False)
        
        # 如果数组长度足够，取索引8-11位置的值，否则使用整个数组
        if len(lightmap_data["CoefAdd"]) > 11:
            coef_add_values = lightmap_data["CoefAdd"][8:12]
            debug_print(f"取索引8-11的CoefAdd值: {coef_add_values}", False)
        elif len(lightmap_data["CoefAdd"]) >= 4:
            coef_add_values = lightmap_data["CoefAdd"][:4]
            debug_print(f"取前4个CoefAdd值: {coef_add_values}", False)
        else:
            # 数据不足4个，但仍然使用现有数据，补充到4个
            coef_add_values = list(lightmap_data["CoefAdd"]) + [0.0] * (4 - len(lightmap_data["CoefAdd"]))
            debug_print(f"CoefAdd数据不足4个，补充到4个: {coef_add_values}", False)
        
        coef_add_value = " ".join([format_float(val) for val in coef_add_values])
        debug_print(f"最终CoefAdd字符串: {coef_add_value}", False)
        coef_add.text = coef_add_value
    
    # 在data容器内添加CoefScale元素 - 只有存在有效数据时才添加
    if has_coef_scale:
        coef_scale = ET.SubElement(data, "CoefScale")
        debug_print(f"\n--- 处理CoefScale ---", False)
        coef_scale_raw = lightmap_data["CoefScale"]
        debug_print(f"原始CoefScale数组长度: {len(coef_scale_raw)}", False)
        debug_print(f"原始CoefScale前12个元素: {coef_scale_raw[:12] if len(coef_scale_raw) >= 12 else coef_scale_raw}", False)
        
        # 如果数组长度足够，取索引8-11位置的值，否则使用整个数组
        if len(lightmap_data["CoefScale"]) > 11:
            coef_scale_values = lightmap_data["CoefScale"][8:12]
            debug_print(f"取索引8-11的CoefScale值: {coef_scale_values}", False)
        elif len(lightmap_data["CoefScale"]) >= 4:
            coef_scale_values = lightmap_data["CoefScale"][:4]
            debug_print(f"取前4个CoefScale值: {coef_scale_values}", False)
        else:
            # 数据不足4个，但仍然使用现有数据，补充到4个
            coef_scale_values = list(lightmap_data["CoefScale"]) + [0.0] * (4 - len(lightmap_data["CoefScale"]))
            debug_print(f"CoefScale数据不足4个，补充到4个: {coef_scale_values}", False)
        
        coef_scale_value = " ".join([format_float(val) for val in coef_scale_values])
        debug_print(f"最终CoefScale字符串: {coef_scale_value}", False)
        coef_scale.text = coef_scale_value
    
    # 在data容器内添加BiasScale元素 - 优先使用converter数据中的更新后BiasScale
    bias_scale_values = None
    
    # 首先尝试从converter数据中获取更新后的BiasScale
    if converter_data and "updated_lightmap_info" in converter_data and xml_name:
        updated_info = converter_data["updated_lightmap_info"]
        # 尝试通过xml_name精确匹配对应的物体
        if xml_name in updated_info:
            lightmap_info = updated_info[xml_name]
            if "new_bias_scale" in lightmap_info and isinstance(lightmap_info["new_bias_scale"], list):
                bias_scale_values = lightmap_info["new_bias_scale"][:4]
                debug_print(f"从converter数据获取物体'{xml_name}'的更新BiasScale: {bias_scale_values}", False)
        else:
            debug_print(f"在converter数据中未找到物体'{xml_name}'的更新BiasScale", False)
    
    # 如果converter数据中没有，则使用原始JSON中的BiasScale
    if bias_scale_values is None and "BiasScale" in lightmap_data:
        if isinstance(lightmap_data["BiasScale"], list) and len(lightmap_data["BiasScale"]) > 0:
            if len(lightmap_data["BiasScale"]) >= 4:
                bias_scale_values = lightmap_data["BiasScale"][:4]
            else:
                bias_scale_values = list(lightmap_data["BiasScale"]) + [0.0] * (4 - len(lightmap_data["BiasScale"]))
            debug_print(f"使用原始JSON中的BiasScale: {bias_scale_values}", False)
    
    # 如果找到有效的BiasScale值，则添加到XML中
    if bias_scale_values:
        bias_scale = ET.SubElement(data, "BiasScale")
        bias_scale_value = " ".join([format_float(val) for val in bias_scale_values])
        bias_scale.text = bias_scale_value
        debug_print(f"最终使用的BiasScale: {bias_scale_value}", False)
    
    # 在data容器内添加LightMapID元素，使用传入的lightmap_id
    light_map_id = ET.SubElement(data, "LightMapID")
    light_map_id.text = str(lightmap_id)
    
    debug_print(f"=== 调试create_lightmap_element结束 ===\n", False)
    return element

def create_or_update_lightmap_xml(matches, output_path, lightmap_path, terrain_data=None, scene_config=None, scene_name=None):
    """
    创建lightmap XML文件
    
    Args:
        matches: 匹配的物体列表
        output_path: 输出文件路径
        lightmap_path: 光照图路径
        terrain_data: 地形数据(可选)
        scene_config: 场景配置(可选)
        scene_name: 场景名称(可选)
    """
    try:
        # 构建lightmap_texture数组和获取mip0数量
        lightmap_texture_array = []
        mip0_count = 0
        mesh_to_lightmap_id = {}
        
        if scene_config:
            debug_print("构建lightmap_texture数组...")
            lightmap_texture_array, mip0_count = build_lightmap_texture_array(scene_config, scene_name, lightmap_path)
            debug_print(f"构建完成，共 {len(lightmap_texture_array)} 个纹理")
        
        # 加载打包结果以获取物体与lightmap_id的映射
        converter_data = None
        if scene_name:
            converter_data = load_lightmap_converter_data(scene_name)
            if converter_data:
                mesh_to_lightmap_id = converter_data.get('mesh_to_lightmap_id', {})
            else:
                mesh_to_lightmap_id = load_packing_results(scene_name)
        
        # 直接创建新的XML结构，不考虑向后兼容
        print(f"创建新的XML文件: {output_path}")
        root, lightmap_data = create_new_xml_structure(lightmap_path, scene_config, lightmap_texture_array, mip0_count, scene_name)
        tree = ET.ElementTree(root)
        
        # 添加所有匹配的物体到lightmap_data
        added_count = 0
        for match in matches:
            try:
                # 添加调试信息，特别关注指定的物体
                xml_name = match["xml_name"]
                if "objects_environment_buildings_wall_SSLM_citywall01_SSLM_citywall01_part_B_connect_01_lod0_mesh_ast_76" in xml_name:
                    debug_print(f"\n!!! 找到目标物体: {xml_name} !!!")
                    debug_print(f"match数据结构: {match.keys()}")
                    debug_print(f"lightmap_data类型: {type(match['lightmap_data'])}")
                    debug_print(f"lightmap_data内容: {match['lightmap_data']}")
                
                # 获取物体对应的lightmap_id
                lightmap_id = 0  # 默认ID
                if xml_name in mesh_to_lightmap_id:
                    lightmap_id = mesh_to_lightmap_id[xml_name]
                else:
                    # 如果没有找到映射关系，尝试使用LQ字段
                    if "LQ" in match["lightmap_data"]:
                        lq_name = match["lightmap_data"]["LQ"]
                        # 尝试从LQ名称中提取纹理索引
                        if lq_name.startswith("packed_lightmap_"):
                            try:
                                texture_index = int(lq_name.replace("packed_lightmap_", ""))
                                lightmap_id = texture_index  # 直接使用texture_index作为lightmap_id
                                debug_print(f"从LQ名称提取lightmap_id: {lightmap_id}")
                            except ValueError:
                                debug_print(f"无法从LQ名称提取索引: {lq_name}")
                    
                    debug_print(f"物体 {xml_name} 使用默认lightmap_id: {lightmap_id}")
                
                element = create_lightmap_element(match["data_ref"], match["lightmap_data"], lightmap_id, converter_data, xml_name)
                if element is not None:  # 只有成功创建元素时才添加
                    lightmap_data.append(element)
                    added_count += 1
                else:
                    print(f"跳过物体 {match['xml_name']}：没有有效的lightmap数据")
            except Exception as e:
                print(f"添加物体 {match['xml_name']} 时出错: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # 处理地形数据 - 在lightmap_data的同级添加terrain_lightmap_data
        if terrain_data and scene_config:
            debug_print("开始处理地形数据...")
            try:
                # 直接移除现有的terrain_lightmap_data元素
                for existing in root.findall("terrain_lightmap_data"):
                    root.remove(existing)
                
                # 创建新的terrain_lightmap_data元素
                terrain_lightmap_element = create_terrain_lightmap_element(terrain_data, lightmap_path, scene_config)
                
                # 将terrain_lightmap_data添加到root中，放在lightmap_data之后
                lightmap_data_index = -1
                for i, child in enumerate(root):
                    if child.tag == "lightmap_data":
                        lightmap_data_index = i
                        break
                
                if lightmap_data_index != -1:
                    # 在lightmap_data之后插入terrain_lightmap_data
                    root.insert(lightmap_data_index + 1, terrain_lightmap_element)
                    debug_print(f"在lightmap_data之后(索引{lightmap_data_index + 1})插入terrain_lightmap_data")
                else:
                    # 如果找不到lightmap_data，就添加到末尾
                    root.append(terrain_lightmap_element)
                    debug_print("在根元素末尾添加terrain_lightmap_data")
                
                print(f"成功添加地形光照图数据: {terrain_data['combine_name']}")
                
            except Exception as e:
                print(f"添加地形数据时出错: {str(e)}")
                import traceback
                traceback.print_exc()
        elif terrain_data:
            print("警告: 有地形数据但缺少场景配置，跳过地形数据处理")
        
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
        
        print(f"成功创建XML文件 {output_path}")
        print(f"  - 包含 {added_count} 个物体的lightmap数据")
        print(f"  - 包含 {len(lightmap_texture_array)} 个纹理的lightmap_texture数组")
        if terrain_data:
            print(f"  - 包含地形数据: {terrain_data['combine_name']}")
        if scene_config:
            level_left = scene_config.get("level_left_pos", [0, 0])
            level_right = scene_config.get("level_right_pos", [0, 0])
            # 转换坐标用于显示
            chaos_left = simple_convert_ue_to_chaos_position(level_left)
            chaos_right = simple_convert_ue_to_chaos_position(level_right)
            print(f"  - lightmap_area (UE坐标): ({level_left[0]}, {level_left[1]}) to ({level_right[0]}, {level_right[1]})")
            print(f"  - lightmap_area (Chaos坐标): ({chaos_left[0]:.2f}, {chaos_left[1]:.2f}) to ({chaos_right[0]:.2f}, {chaos_right[1]:.2f})")
            
            # 输出新增的元素信息
            runtime_distances = scene_config.get("lightmap_runtime_mip_distances", [])
            mip0_texture_size = scene_config.get("mip0_texture_size")
            max_mip_level = scene_config.get("max_mip_level", 0)
            
            # 显示运行时距离配置
            if runtime_distances:
                # 显示虚幻和Chaos的值（转换为整数）
                chaos_distances = [int(d / 100.0) for d in runtime_distances]
                print(f"  - lightmap_mip_distance (运行时加载距离, UE厘米): {runtime_distances}")
                print(f"  - lightmap_mip_distance (Chaos米，整数): {chaos_distances}")
            else:
                print("  - ⚠️ lightmap_mip_distance: 未配置运行时距离")
                
            if mip0_texture_size is not None:
                # 显示虚幻和Chaos的值（转换为整数）
                chaos_texture_size = int(mip0_texture_size / 100.0)
                print(f"  - lightmap_mip0_grid_size (UE厘米): {mip0_texture_size}")
                print(f"  - lightmap_mip0_grid_size (Chaos米，整数): {chaos_texture_size}")
            print(f"  - mip_number: {max_mip_level + 1}")
        
    except Exception as e:
        print(f"创建或更新lightmap XML失败: {str(e)}")
        import traceback
        traceback.print_exc()

def create_new_xml_structure(lightmap_path, scene_config=None, lightmap_texture_array=None, mip0_count=0, scene_name=None):
    """
    创建新的XML结构
    
    Args:
        lightmap_path: 光照图路径
        scene_config: 场景配置
        lightmap_texture_array: 纹理数组
        mip0_count: mip0数量 (已废弃，保留参数以兼容调用)
        scene_name: 场景名称（用于加载converter数据）
    
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
    
    # 添加lightmap_texture数组
    if lightmap_texture_array:
        lightmap_texture = ET.SubElement(root, "lightmap_texture")
        for texture_element in lightmap_texture_array:
            lightmap_texture.append(texture_element)
    
    # 添加lightmap_area元素
    if scene_config:
        level_left_pos = scene_config.get("level_left_pos", [0, 0])
        level_right_pos = scene_config.get("level_right_pos", [0, 0])
        
        # 将虚幻引擎坐标转换为Chaos坐标
        chaos_left_pos = simple_convert_ue_to_chaos_position(level_left_pos)
        chaos_right_pos = simple_convert_ue_to_chaos_position(level_right_pos)
        
        lightmap_area = ET.SubElement(root, "lightmap_area")
        lightmap_area.text = f"{format_float(chaos_left_pos[0])} {format_float(chaos_left_pos[1])} {format_float(chaos_right_pos[0])} {format_float(chaos_right_pos[1])}"
    
    # 添加新的lightmap相关元素
    if scene_config:
        # 添加lightmap_mip_distance数组，值来自lightmap_runtime_mip_distances（运行时加载距离）
        runtime_distances = scene_config.get("lightmap_runtime_mip_distances", [])
        if runtime_distances:
            lightmap_mip_distance = ET.SubElement(root, "lightmap_mip_distance")
            for distance in runtime_distances:
                element = ET.SubElement(lightmap_mip_distance, "element", {"sketum_id": generate_sketum_id()})
                # 虚幻引擎厘米转Chaos引擎米，除以100，转为正整数
                element.text = str(int(distance / 100.0))
        else:
            print("⚠️ 警告: 未配置lightmap_runtime_mip_distances，lightmap_mip_distance标签将不会被添加")
        
        # 添加lightmap_mip0_grid_size，值是mip0_texture_size（虚幻厘米转Chaos米，除以100）
        mip0_texture_size = scene_config.get("mip0_texture_size")
        if mip0_texture_size is not None:
            lightmap_mip0_grid_size = ET.SubElement(root, "lightmap_mip0_grid_size")
            # 虚幻引擎厘米转Chaos引擎米，除以100，转为正整数
            lightmap_mip0_grid_size.text = str(int(mip0_texture_size / 100.0))
        
        # 从converter数据获取lightmap_mip0_side_grid_number
        side_grid_number = None
        if scene_name:
            converter_data = load_lightmap_converter_data(scene_name)
            if converter_data:
                side_grid_number = converter_data.get('lightmap_mip0_side_grid_number')
                debug_print(f"从converter数据获取side_grid_number: {side_grid_number}")
                
                # 验证side_grid_number必须为偶数
                if side_grid_number is not None:
                    if side_grid_number % 2 != 0:
                        print(f"⚠️  警告: side_grid_number ({side_grid_number}) 不是偶数，四叉树管理可能有问题")
                    
                    lightmap_mip0_side_grid_number = ET.SubElement(root, "lightmap_mip0_side_grid_number")
                    lightmap_mip0_side_grid_number.text = str(side_grid_number)
            else:
                print("⚠️ 警告: 没有converter数据，无法设置lightmap_mip0_side_grid_number")
        else:
            print("⚠️ 警告: 未指定场景名称，无法获取converter数据")
        
        # 添加mip_number，值是max_mip_level + 1（因为mip等级从0开始计算）
        max_mip_level = scene_config.get("max_mip_level", 0)
        mip_number = ET.SubElement(root, "mip_number")
        mip_number.text = str(max_mip_level + 1)  # 确保为正整数
    
    return root, lightmap_data

def extract_terrain_data_from_json(json_data):
    """
    从JSON数据中提取地形的Lightmap数据
    
    Args:
        json_data: 完整的JSON数据对象
    
    Returns:
        dict: 包含地形Lightmap数据的字典，如果找不到则返回None
    """
    try:
        debug_print("开始提取地形数据...")
        
        # 查找地形数据 - 首先尝试直接在根级别查找
        if "Landscape" in json_data:
            debug_print("在根级别找到Landscape数据")
            landscape_data = json_data["Landscape"]
            
            # 检查是否有嵌套的Landscape
            if isinstance(landscape_data, dict) and "Landscape" in landscape_data:
                landscape_data = landscape_data["Landscape"]
                debug_print("找到嵌套的Landscape数据")
            
            # 检查是否有lightmapGroup
            if isinstance(landscape_data, dict) and "lightmapGroup" in landscape_data:
                lightmap_group = landscape_data["lightmapGroup"]
                debug_print(f"找到lightmapGroup，包含键: {list(lightmap_group.keys())}")
                
                # 检查是否有combine字段，这是合并后的贴图名称
                if "combine" in lightmap_group:
                    combine_name = lightmap_group["combine"]
                    debug_print(f"找到地形合并的Lightmap: {combine_name}")
                    
                    # 查找所有网格的系数数据
                    coef_scales = []
                    coef_adds = []
                    
                    # 遍历所有网格，收集系数
                    for key, tile_data in lightmap_group.items():
                        if key == "combine":
                            continue
                        
                        if isinstance(tile_data, dict):
                            if "CoefScale" in tile_data and "CoefAdd" in tile_data:
                                # 提取需要的系数数据
                                coef_scale = tile_data.get("CoefScale", [])
                                coef_add = tile_data.get("CoefAdd", [])
                                
                                debug_print(f"网格 {key}: CoefScale长度={len(coef_scale)}, CoefAdd长度={len(coef_add)}")
                                
                                # 确保我们有足够的数据
                                if len(coef_scale) >= 12 and len(coef_add) >= 12:
                                    # 通常系数在索引8-11位置
                                    coef_scales.append(coef_scale[8:12])
                                    coef_adds.append(coef_add[8:12])
                                    debug_print(f"网格 {key}: 提取的CoefScale[8:12]={coef_scale[8:12]}, CoefAdd[8:12]={coef_add[8:12]}")
                    
                    # 如果找到系数数据，计算平均值
                    if coef_scales and coef_adds:
                        # 计算平均系数
                        avg_coef_scale = [sum(col)/len(col) for col in zip(*coef_scales)]
                        avg_coef_add = [sum(col)/len(col) for col in zip(*coef_adds)]
                        
                        debug_print(f"计算了 {len(coef_scales)} 个网格的平均系数")
                        debug_print(f"平均CoefScale: {avg_coef_scale}")
                        debug_print(f"平均CoefAdd: {avg_coef_add}")
                        
                        # 返回结果
                        return {
                            "combine_name": combine_name,
                            "lightmap_coef_scale": avg_coef_scale,
                            "lightmap_coef_add": avg_coef_add
                        }
                    else:
                        debug_print("未找到有效的系数数据")
                        return None
                else:
                    debug_print("未找到地形合并的Lightmap名称")
                    return None
            else:
                debug_print("未找到lightmapGroup数据")
                return None
        else:
            debug_print("未在JSON中找到Landscape数据")
            
            # 如果在根级别找不到，尝试在'Terrain'字段中查找
            if "Terrain" in json_data:
                debug_print("尝试在Terrain字段中查找数据")
                terrain_data = json_data["Terrain"]
                
                # 查找合并的Lightmap信息
                if isinstance(terrain_data, dict) and "lightmap" in terrain_data:
                    lightmap_data = terrain_data["lightmap"]
                    
                    if "combine_name" in lightmap_data:
                        combine_name = lightmap_data["combine_name"]
                        debug_print(f"找到地形合并的Lightmap: {combine_name}")
                        
                        # 查找系数数据
                        if "coef_scale" in lightmap_data and "coef_add" in lightmap_data:
                            coef_scale = lightmap_data["coef_scale"]
                            coef_add = lightmap_data["coef_add"]
                            
                            return {
                                "combine_name": combine_name,
                                "lightmap_coef_scale": coef_scale,
                                "lightmap_coef_add": coef_add
                            }
        
        debug_print("未能找到有效的地形Lightmap数据")
        return None
        
    except Exception as e:
        debug_print(f"提取地形数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def create_terrain_lightmap_element(terrain_data, lightmap_path, scene_config):
    """
    创建一个terrain_lightmap_data元素
    
    Args:
        terrain_data: 地形光照图数据
        lightmap_path: 光照图路径
        scene_config: 场景配置信息
        
    Returns:
        Element: 创建的terrain_lightmap_data元素
    """
    debug_print(f"\n=== 创建terrain_lightmap_data元素 ===")
    debug_print(f"terrain_data: {terrain_data}")
    debug_print(f"lightmap_path: {lightmap_path}")
    
    # 创建terrain_lightmap_data元素
    terrain_lightmap_data = ET.Element("terrain_lightmap_data")
    
    # 创建CoefAdd元素
    coef_add = ET.SubElement(terrain_lightmap_data, "CoefAdd")
    coef_add_values = terrain_data["lightmap_coef_add"]
    coef_add_value = " ".join([format_float(val) for val in coef_add_values])
    coef_add.text = coef_add_value
    debug_print(f"CoefAdd: {coef_add_value}")
    
    # 创建CoefScale元素
    coef_scale = ET.SubElement(terrain_lightmap_data, "CoefScale")
    coef_scale_values = terrain_data["lightmap_coef_scale"]
    coef_scale_value = " ".join([format_float(val) for val in coef_scale_values])
    coef_scale.text = coef_scale_value
    debug_print(f"CoefScale: {coef_scale_value}")
    
    # 计算BiasScale值，使用terrain_size_offset参数
    if "terrain_size_offset" in scene_config:
        terrain_size_offset = scene_config["terrain_size_offset"]
        if len(terrain_size_offset) >= 4:
            size_x, size_y, offset_x, offset_y = terrain_size_offset
            
            # 计算scale和bias
            # scale = 1 / size
            scale_u = 1.0 / size_x if size_x != 0 else 0.0
            scale_v = 1.0 / size_y if size_y != 0 else 0.0
            
            # bias = offset / size (确保uv计算时能正确映射到[0,1]区间)
            bias_u = offset_x / size_x if size_x != 0 else 0.0
            bias_v = offset_y / size_y if size_y != 0 else 0.0
            
            bias_scale_text = f"{format_float(bias_u)} {format_float(bias_v)} {format_float(scale_u)} {format_float(scale_v)}"
            debug_print(f"使用配置的terrain_size_offset [{size_x}, {size_y}, {offset_x}, {offset_y}] 计算BiasScale: {bias_scale_text}")
        else:
            debug_print(f"警告: terrain_size_offset数组长度不足 ({len(terrain_size_offset)}), 使用默认BiasScale值")
            bias_scale_text = "0.000000 0.000000 1.000000 1.000000"
    else:
        debug_print(f"警告: 未找到terrain_size_offset配置, 使用默认BiasScale值")
        bias_scale_text = "0.000000 0.000000 1.000000 1.000000"
    
    # 创建BiasScale元素
    bias_scale = ET.SubElement(terrain_lightmap_data, "BiasScale")
    bias_scale.text = bias_scale_text
    debug_print(f"BiasScale: {bias_scale_text}")
    
    # 创建LightMap元素 (注意这里用的是LightMap而不是terrainLightMap，与示例保持一致)
    light_map = ET.SubElement(terrain_lightmap_data, "LightMap")
    
    # 创建url元素
    url = ET.SubElement(light_map, "url")
    combine_name = terrain_data["combine_name"]
    original_url = f"{lightmap_path}/{combine_name}.texture.ast"
    url.text = convert_url_path_for_ast(original_url)
    debug_print(f"LightMap URL (原始): {original_url}")
    debug_print(f"LightMap URL (转换后): {url.text}")
    
    # 创建guid和parameter元素
    guid = ET.SubElement(light_map, "guid")
    parameter = ET.SubElement(light_map, "parameter")
    parameters = ET.SubElement(parameter, "parameters")
    
    debug_print(f"=== terrain_lightmap_data元素创建完成 ===\n")
    return terrain_lightmap_data

def build_lightmap_texture_array_from_converter_data(converter_data, lightmap_path):
    """
    从converter数据构建lightmap_texture数组
    
    Args:
        converter_data: converter数据
        lightmap_path: chaos中的lightmap资源路径前缀
        
    Returns:
        tuple: (texture_array, mip0_count)
    """
    texture_array = []
    lightmap_texture_array = converter_data.get("lightmap_texture_array", [])
    mip0_count = converter_data.get("mip_info", {}).get("mip0_texture_count", 0)
    
    debug_print(f"从converter数据构建lightmap_texture数组，总数: {len(lightmap_texture_array)}")
    
    # 按类型和mip级别排序：先LQ，后Dir；先mip0，后高级mip
    def sort_key(item):
        mip_level = item.get("mip_level", 0)
        type_priority = 0 if item.get("type") == "LQ" else 1
        return (mip_level, type_priority, item.get("texture_index", 0), item.get("merge_index", 0))
    
    sorted_textures = sorted(lightmap_texture_array, key=sort_key)
    
    # 只添加LQ纹理到数组（XML中只需要LQ纹理）
    for texture_info in sorted_textures:
        if texture_info.get("type") == "LQ":
            # 将.png路径转换为.texture.ast路径
            url = texture_info.get("url", "")
            if url.endswith(".png"):
                url = url.replace(".png", ".texture.ast")
            
            # 确保URL包含正确的lightmap_path前缀
            if not url.startswith(lightmap_path):
                # 如果URL是相对路径，添加前缀
                if not url.startswith("/") and not url.startswith("_project"):
                    url = f"{lightmap_path}/{url}"
                # 如果URL已经是完整的相对路径（以_project开头），直接使用
                elif url.startswith("_project"):
                    pass  # 保持原样
                else:
                    # 其他情况，确保添加前缀
                    url = f"{lightmap_path}/{url.lstrip('/')}"
            
            lq_element = create_lightmap_texture_element(url, generate_sketum_id())
            texture_array.append(lq_element)
    
    debug_print(f"构建完成，数组长度: {len(texture_array)}, mip0数量: {mip0_count}")
    
    return texture_array, mip0_count

def build_lightmap_texture_array(scene_config, scene_name=None, lightmap_path=None):
    """
    构建lightmap_texture数组，按照打包工具的输出顺序（仅LQ纹理）
    
    Args:
        scene_config: 场景配置信息
        scene_name: 场景名称（可选，用于加载converter数据）
        lightmap_path: 光照图路径前缀（可选，如果提供则优先使用，否则从scene_config获取）
        
    Returns:
        tuple: (texture_array, mip0_count)
    """
    # 首先尝试从converter数据构建
    if scene_name:
        converter_data = load_lightmap_converter_data(scene_name)
        if converter_data:
            # 优先使用传入的lightmap_path参数，如果没有则从scene_config获取
            if lightmap_path is None:
                lightmap_path = scene_config["lightmap_path_in_chaos_assets"]
            return build_lightmap_texture_array_from_converter_data(converter_data, lightmap_path)
    
    # 如果没有converter数据，使用旧的方法
    print("使用旧方法构建lightmap_texture数组...")
    
    texture_array = []
    # 优先使用传入的lightmap_path参数，如果没有则从scene_config获取
    if lightmap_path is None:
        lightmap_path = scene_config["lightmap_path_in_chaos_assets"]
    max_mip_level = scene_config.get("max_mip_level", 0)
    
    # 构建输出目录路径 - 假设打包工具输出在BigMap文件夹
    source_lightmap_path = scene_config["source_lightmap_texture_path"]
    bigmap_dir = os.path.join(os.path.dirname(source_lightmap_path), "BigMap")
    
    lightmap_dir = os.path.join(bigmap_dir, "lightmap")
    
    debug_print(f"构建lightmap_texture数组，扫描目录：{lightmap_dir}")
    
    # 首先扫描mip0文件，确定mip0的数量
    mip0_count = 0
    if os.path.exists(lightmap_dir):
        # 扫描mip0文件 (packed_lightmap_0.png, packed_lightmap_1.png, ...)
        mip0_files = []
        for filename in os.listdir(lightmap_dir):
            if filename.startswith("packed_lightmap_") and filename.endswith(".png"):
                # 检查是否是mip0文件（不包含"mip"字样）
                if "_mip" not in filename.lower():
                    # 提取索引号
                    try:
                        index_str = filename.replace("packed_lightmap_", "").replace(".png", "")
                        index = int(index_str)
                        mip0_files.append((index, filename))
                    except ValueError:
                        continue
        
        # 按索引排序
        mip0_files.sort()
        mip0_count = len(mip0_files)
        
        debug_print(f"找到 {mip0_count} 个mip0文件")
        
        # 添加mip0的LQ纹理
        for index, filename in mip0_files:
            # 只添加LQ纹理，将.png改为.texture.ast
            filename_without_ext = os.path.splitext(filename)[0]
            lq_element = create_lightmap_texture_element(
                f"{lightmap_path}/lightmap/{filename_without_ext}.texture.ast",
                generate_sketum_id()
            )
            texture_array.append(lq_element)
    
    # 然后按mip级别添加合并的mip纹理
    for mip_level in range(1, max_mip_level + 1):
        if os.path.exists(lightmap_dir):
            # 扫描该mip级别的文件
            mip_files = []
            for filename in os.listdir(lightmap_dir):
                if filename.startswith(f"packed_lightmap_mip{mip_level}_") and filename.endswith(".png"):
                    # 提取索引号
                    try:
                        index_str = filename.replace(f"packed_lightmap_mip{mip_level}_", "").replace(".png", "")
                        index = int(index_str)
                        mip_files.append((index, filename))
                    except ValueError:
                        continue
            
            # 按索引排序
            mip_files.sort()
            
            debug_print(f"找到 {len(mip_files)} 个mip{mip_level}文件")
            
            # 添加该mip级别的LQ纹理
            for index, filename in mip_files:
                # 只添加LQ纹理，将.png改为.texture.ast
                filename_without_ext = os.path.splitext(filename)[0]
                lq_element = create_lightmap_texture_element(
                    f"{lightmap_path}/lightmap/{filename_without_ext}.texture.ast",
                    generate_sketum_id()
                )
                texture_array.append(lq_element)
    
    debug_print(f"构建完成，共 {len(texture_array)} 个纹理元素")
    
    return texture_array, mip0_count

def create_lightmap_texture_element(url, guid):
    """
    创建一个lightmap_texture元素
    
    Args:
        url: 纹理的URL路径
        guid: 纹理的GUID
        
    Returns:
        Element: 创建的lightmap_texture元素
    """
    element = ET.Element("element", {"sketum_id": generate_sketum_id()})
    
    # 添加url元素
    url_elem = ET.SubElement(element, "url")
    url_elem.text = convert_url_path_for_ast(url)
    
    # 添加guid元素
    guid_elem = ET.SubElement(element, "guid")
    guid_elem.text = guid
    
    # 添加parameter元素
    parameter = ET.SubElement(element, "parameter")
    parameters = ET.SubElement(parameter, "parameters")
    
    return element

def load_lightmap_converter_data(scene_name):
    """加载hybrid_lightmap_packer_nsh输出的converter数据
    
    Args:
        scene_name: 场景名称
        
    Returns:
        dict: converter数据，如果加载失败则返回None
    """
    # 构建converter数据JSON文件的路径
    output_dir = os.path.join("./output/lightmaps", scene_name)
    converter_data_path = os.path.join(output_dir, "lightmap_converter_data.json")
    
    if not os.path.exists(converter_data_path):
        print(f"错误: 找不到converter数据文件: {converter_data_path}")
        print("请先运行hybrid_lightmap_packer_nsh.py --process-staticmesh生成数据")
        return None
    
    try:
        # 读取converter数据
        with open(converter_data_path, 'r', encoding='utf-8') as f:
            converter_data = json.load(f)
        
        print(f"✓ 已加载lightmap_converter数据:")
        print(f"  - 场景: {converter_data.get('scene_name', 'Unknown')}")
        print(f"  - 区域边界: {converter_data.get('area_bounds', {}).get('left_pos', [0, 0])} 到 {converter_data.get('area_bounds', {}).get('right_pos', [0, 0])}")
        print(f"  - 格子数量: {converter_data.get('lightmap_mip0_side_grid_number', 0)} x {converter_data.get('lightmap_mip0_side_grid_number', 0)}")
        print(f"  - 纹理总数: {converter_data.get('mip_info', {}).get('total_texture_count', 0)}")
        print(f"  - 物体映射数: {len(converter_data.get('mesh_to_lightmap_id', {}))}")
        
        # 验证数据完整性
        validation = converter_data.get('validation', {})
        if not validation.get('grid_count_is_even', False):
            print("❌ 验证失败: 格子数量不是偶数")
            return None
        if not validation.get('area_is_square', False):
            print("❌ 验证失败: 区域不是正方形")
            return None
            
        print("✓ 数据验证通过")
        return converter_data
        
    except Exception as e:
        print(f"读取converter数据时出错: {e}")
        return None

def load_packing_results(scene_name):
    """
    从打包结果中加载物体与纹理的映射关系（向后兼容函数）
    
    Args:
        scene_name: 场景名称
        
    Returns:
        dict: 物体名称到lightmap_id的映射
    """
    # 首先尝试从新的converter数据中获取
    converter_data = load_lightmap_converter_data(scene_name)
    if converter_data:
        return converter_data.get('mesh_to_lightmap_id', {})
    
    # 如果没有converter数据，回退到旧的方法
    print("回退到旧的打包结果文件...")
    output_dir = os.path.join("./output/lightmaps", scene_name)
    debug_file_path = os.path.join(output_dir, "packing_debug.json")
    
    mesh_to_lightmap_id = {}
    
    if os.path.exists(debug_file_path):
        try:
            with open(debug_file_path, 'r', encoding='utf-8') as f:
                packing_results = json.load(f)
            
            debug_print(f"加载打包结果文件: {debug_file_path}")
            
            # 解析打包结果，构建物体到lightmap_id的映射
            for texture_result in packing_results.get('texture_results', []):
                texture_index = texture_result.get('texture_index', 0)
                
                # 现在每个纹理直接对应一个lightmap_id（只有LQ纹理）
                lightmap_id = texture_index
                
                # 获取该纹理中的所有物体
                for rect in texture_result.get('rectangles', []):
                    mesh_id = rect.get('mesh_id')
                    if mesh_id:
                        mesh_to_lightmap_id[mesh_id] = lightmap_id
                        debug_print(f"物体 {mesh_id} 映射到 lightmap_id {lightmap_id}")
                        
        except Exception as e:
            debug_print(f"加载打包结果文件失败: {e}")
    
    else:
        debug_print(f"打包结果文件不存在: {debug_file_path}")
    
    return mesh_to_lightmap_id

def extract_scene_config_from_converter_data(converter_data):
    """从converter数据中提取必要的场景配置信息
    
    Args:
        converter_data: converter数据字典
        
    Returns:
        dict: 场景配置字典
    """
    # 获取必要的路径和参数
    bigmap_dir = converter_data.get("bigmap_directory", "")
    area_bounds = converter_data.get("area_bounds", {})
    mip_info = converter_data.get("mip_info", {})
    
    # 构建场景配置，只包含lightmap_converter需要的数据
    scene_config = {
        # 路径相关 - 从converter数据推断
        "source_scene_xml_folder_path": ".",  # 需要用户通过命令行参数或其他方式提供
        "source_lightmap_json_path": ".",     # 需要用户通过命令行参数或其他方式提供  
        "lightmap_data_ast_path_in_chaos": "output_lightmap.ast",  # 默认输出路径
        "lightmap_path_in_chaos_assets": "_project/lightMaps",     # 默认资源路径
        
        # 区域和格子相关 - 从converter数据获取
        "level_left_pos": area_bounds.get("left_pos", [0, 0]),
        "level_right_pos": area_bounds.get("right_pos", [0, 0]),
        "grid_size": area_bounds.get("grid_size", 1024),
        "grid_count_x": area_bounds.get("grid_count_x", 2),
        "grid_count_y": area_bounds.get("grid_count_y", 2),
        
        # Mip相关 - 从converter数据获取
        "max_mip_level": mip_info.get("max_mip_level", 0),
        "lightmap_texture_size": 2048,  # 默认值，实际不太需要
        
        # 地形相关 - 默认值
        "terrain_size_offset": [512, 512, 512, 512],
        "mip0_texture_size": area_bounds.get("grid_size", 1024),
        
        # 运行时距离配置 - 默认值，建议用户在GlobalParameter中配置
        "lightmap_runtime_mip_distances": [area_bounds.get("grid_size", 1024) * 10, 
                                          area_bounds.get("grid_size", 1024) * 20,
                                          area_bounds.get("grid_size", 1024) * 40,
                                          area_bounds.get("grid_size", 1024) * 80],  # 基于格子大小的合理运行时距离
    }
    
    print(f"✓ 从converter数据提取场景配置:")
    print(f"  - 区域边界: {scene_config['level_left_pos']} 到 {scene_config['level_right_pos']}")
    print(f"  - 格子数量: {scene_config['grid_count_x']} x {scene_config['grid_count_y']}")
    print(f"  - 格子大小: {scene_config['mip0_texture_size']} (用于lightmap_mip0_grid_size)")
    print(f"  - Mip级别: {scene_config['max_mip_level']}")
    
    # 显示运行时距离配置
    runtime_distances = scene_config.get('lightmap_runtime_mip_distances', [])
    if runtime_distances:
        chaos_runtime_distances = [int(d / 100.0) for d in runtime_distances]
        print(f"  - 运行时加载距离 (UE厘米): {runtime_distances}")
        print(f"  - 运行时加载距离 (Chaos米): {chaos_runtime_distances}")
    else:
        print(f"  - ⚠️ 未配置运行时距离，将使用LOD距离作为后备")
    
    return scene_config

def simple_convert_ue_to_chaos_position(position):
    """简单的UE到Chaos坐标转换（不依赖GlobalParameter）
    
    Args:
        position: UE位置坐标 [x, y]
        
    Returns:
        list: Chaos坐标 [y, x] (交换XY并转换为米单位)
    """
    if not isinstance(position, (list, tuple)) or len(position) != 2:
        print(f"警告: 位置坐标格式不正确，应为[x, y]格式，当前: {position}")
        return position
    
    # 交换x和y坐标：(x, y) -> (y, x)，并从厘米转换为米
    local_location = [position[1] / 100.0, position[0] / 100.0]
    
    return local_location

def main():
    parser = argparse.ArgumentParser(description="匹配XML和JSON物体并生成lightmap XML")
    
    parser.add_argument("--scene", "-s", type=str, default="carcassonne", 
                      help=f"要处理的场景名称，默认为carcassonne")
    
    parser.add_argument("--force-match", "-f", action="store_true",
                      help="强制匹配模式，尝试匹配所有JSON物体")
                      
    parser.add_argument("--test-mode", "-t", action="store_true",
                      help="测试模式，使用测试数据进行匹配")
    
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="详细输出模式，打印更多调试信息")
    
    parser.add_argument("--copy-textures", "-c", action="store_true",
                      help="处理完成后自动复制光照图贴图到Chaos引擎目录")
    

    
    args = parser.parse_args()
    
    # 获取场景名称
    scene_name = args.scene
    
    # 首先检查场景是否在GlobalParameter中配置
    if scene_name not in ALL_LIGHT_MAP_DATA:
        print(f"错误: 场景 '{scene_name}' 未在GlobalParameter中配置")
        print(f"可用的场景: {list(ALL_LIGHT_MAP_DATA.keys())}")
        return
    
    # 然后检查场景的converter数据是否存在
    converter_data = load_lightmap_converter_data(scene_name)
    if not converter_data:
        print(f"错误: 场景 '{scene_name}' 的converter数据不存在")
        print("请先运行 hybrid_lightmap_packer_nsh.py --process-staticmesh 生成数据")
        return
    
    # 初始化调试文件
    debug_filename = init_debug_file(scene_name)
    
    try:
        
        # 从GlobalParameter获取场景配置
        global_scene_config = ALL_LIGHT_MAP_DATA[scene_name]
        
        # 从converter数据中获取必要的场景配置（用于mip等信息）
        scene_config = extract_scene_config_from_converter_data(converter_data)
        
        # 合并GlobalParameter中的重要配置到scene_config
        # 运行时距离配置优先使用GlobalParameter中的配置
        if "lightmap_runtime_mip_distances" in global_scene_config:
            scene_config["lightmap_runtime_mip_distances"] = global_scene_config["lightmap_runtime_mip_distances"]
            print(f"✓ 从GlobalParameter加载运行时距离配置: {global_scene_config['lightmap_runtime_mip_distances']}")
        
        # 使用GlobalParameter中的路径配置
        xml_folder_path = global_scene_config["source_scene_xml_folder_path"]
        json_path = global_scene_config["source_lightmap_json_path"]
        output_path = global_scene_config["lightmap_data_ast_path_in_chaos"]
        lightmap_path = global_scene_config["lightmap_path_in_chaos_assets"]


        print(f"\n处理场景: {scene_name}")
        print(f"XML文件夹路径: {xml_folder_path}")
        print(f"JSON文件路径: {json_path}")
        print(f"输出文件路径: {output_path}")
        print(f"光照图路径: {lightmap_path}")
        print(f"调试日志文件: {debug_filename}\n")
        
        debug_print(f"开始处理场景: {scene_name}")
        debug_print(f"XML文件夹路径: {xml_folder_path}")
        debug_print(f"JSON文件路径: {json_path}")
        debug_print(f"输出文件路径: {output_path}")
        debug_print(f"光照图路径: {lightmap_path}")
        
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
        xml_file_objects = {}  # 记录每个文件的物体，用于详细分析
        for xml_file in xml_files:
            print(f"\n处理XML文件: {xml_file}")
            xml_objects = read_xml_objects(xml_file)
            xml_file_objects[xml_file] = xml_objects
            all_xml_objects.update(xml_objects)
        
        print(f"\n所有XML文件中共找到 {len(all_xml_objects)} 个物体")
        
        all_matches = []
        all_unmatched_xml = {}
        all_unmatched_json = {}
        file_match_details = {}  # 记录每个文件的匹配详情
        
        # 目标物体名称
        target_object_name = "objects_environment_buildings_wall_SSLM_citywall01_SSLM_citywall01_part_B_connect_01_lod0_mesh_ast_76"
        
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
            matched_json_names = [m["json_name"] for m in all_matches]
            all_unmatched_xml = {name: obj for name, obj in all_xml_objects.items() if name not in matched_xml_names}
            all_unmatched_json = {name: obj for name, obj in json_objects.items() if name not in matched_json_names}
            
            print(f"\n强制匹配模式下，精确匹配成功 {len(all_matches)} 个物体，仍有 {len(all_unmatched_xml)} 个物体未匹配")
            
        else:
            # 常规匹配模式：处理每个XML文件
            for xml_file in xml_files:
                print(f"\n处理XML文件: {xml_file}")
                
                # 读取XML物体
                xml_objects = xml_file_objects[xml_file]
                if not xml_objects:
                    print(f"未能从{xml_file}中读取物体，跳过此文件")
                    file_match_details[xml_file] = {
                        "matches": [],
                        "unmatched_xml": {},
                        "unmatched_json": {},
                        "status": "无物体数据"
                    }
                    continue
                
                # 匹配物体
                file_matches, unmatched_xml, unmatched_json = match_objects(xml_objects, json_objects)
                file_match_details[xml_file] = {
                    "matches": file_matches,
                    "unmatched_xml": unmatched_xml,
                    "unmatched_json": unmatched_json,
                    "status": f"匹配{len(file_matches)}个物体" if file_matches else "无匹配物体"
                }
                
                if not file_matches:
                    print(f"在{xml_file}中未找到匹配的物体，跳过此文件")
                    continue
                
                all_matches.extend(file_matches)
            
            # 收集所有未匹配的物体
            all_unmatched_xml, all_unmatched_json = collect_all_unmatched_objects(xml_files, json_objects)
        
        if not all_matches:
            print("未找到任何匹配的物体，程序退出")
            return
        
        print(f"\n所有文件处理完成，共找到 {len(all_matches)} 个匹配物体")
        
        # 从JSON中提取地形数据
        terrain_data = None
        try:
            print("\n开始提取地形数据...")
            # 重新读取完整的JSON数据以提取地形信息
            with open(json_path, 'r', encoding='utf-8') as f:
                full_json_data = json.load(f)
            
            terrain_data = extract_terrain_data_from_json(full_json_data)
            if terrain_data:
                print(f"成功提取地形数据: {terrain_data['combine_name']}")
                debug_print(f"地形数据: combine_name={terrain_data['combine_name']}")
                debug_print(f"地形CoefScale: {terrain_data['lightmap_coef_scale']}")
                debug_print(f"地形CoefAdd: {terrain_data['lightmap_coef_add']}")
            else:
                print("未找到地形数据，将仅处理静态物体")
                debug_print("未找到地形数据")
        except Exception as e:
            print(f"提取地形数据时出错: {str(e)}")
            debug_print(f"提取地形数据时出错: {str(e)}")
            terrain_data = None
        
        # 创建lightmap XML，包含地形数据
        create_or_update_lightmap_xml(all_matches, output_path, lightmap_path, terrain_data, scene_config, scene_name)
        
        # 复制光照图贴图到Chaos引擎目录（如果启用）
        if args.copy_textures:
            print("\n=== 复制光照图贴图到Chaos引擎 ===")
            try:
                # 导入复制函数
                from run_texture_tools import copy_lightmap_textures_to_chaos
                
                # 执行复制
                copy_success = copy_lightmap_textures_to_chaos(scene_name)
                
                if copy_success:
                    print("✅ 光照图贴图复制完成")
                else:
                    print("❌ 光照图贴图复制失败")
                    
            except Exception as e:
                print(f"❌ 复制光照图贴图时出错: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("\n💡 提示: 使用 --copy-textures 参数可以自动复制光照图贴图到Chaos引擎目录")
        
        # 生成最终的完整调试报告
        generate_final_debug_report(
            xml_files, 
            xml_file_objects, 
            json_objects, 
            all_matches, 
            all_unmatched_xml, 
            all_unmatched_json, 
            file_match_details,
            target_object_name,
            args.force_match
        )
        
        print("处理完成!")
        print(f"详细调试信息已保存到: {debug_filename}")
        
        # 显示完整的工作流程提示
        print("\n" + "="*80)
        print("完整的光照图处理工作流程:")
        print("="*80)
        print("1. 打包光照图:")
        print(f"   python hybrid_lightmap_packer_nsh.py --scene {scene_name} --process-staticmesh --process-terrain")
        print("2. 生成XML元数据:")
        print(f"   python lightmap_converter.py --scene {scene_name}")
        print("3. 复制贴图到Chaos引擎:")
        print(f"   python run_texture_tools.py copy --scene {scene_name}")
        print("   或者在步骤2中使用 --copy-textures 参数自动复制")
        print("="*80)
        
    finally:
        # 确保调试文件被关闭
        close_debug_file()

def generate_final_debug_report(xml_files, xml_file_objects, json_objects, all_matches, 
                               all_unmatched_xml, all_unmatched_json, file_match_details,
                               target_object_name, force_match_mode):
    """
    生成最终的完整调试报告
    
    Args:
        xml_files: 所有XML文件列表
        xml_file_objects: 每个XML文件的物体数据
        json_objects: JSON物体数据
        all_matches: 所有匹配的物体
        all_unmatched_xml: 所有未匹配的XML物体
        all_unmatched_json: 所有未匹配的JSON物体
        file_match_details: 每个文件的匹配详情
        target_object_name: 目标物体名称
        force_match_mode: 是否为强制匹配模式
    """
    debug_print("\n" + "="*100)
    debug_print("                         最终完整调试报告")
    debug_print("="*100)
    
    # 报告概要
    debug_print(f"\n### 处理概要 ###")
    debug_print(f"匹配模式: {'强制匹配' if force_match_mode else '常规匹配'}")
    debug_print(f"处理的XML文件数量: {len(xml_files)}")
    debug_print(f"XML中总物体数量: {sum(len(objs) for objs in xml_file_objects.values())}")
    debug_print(f"JSON中总物体数量: {len(json_objects)}")
    debug_print(f"成功匹配的物体数量: {len(all_matches)}")
    debug_print(f"XML中未匹配物体数量: {len(all_unmatched_xml)}")
    debug_print(f"JSON中未匹配物体数量: {len(all_unmatched_json)}")
    
    # 各文件处理详情
    debug_print(f"\n### 各XML文件处理详情 ###")
    debug_print("-" * 80)
    for i, xml_file in enumerate(xml_files, 1):
        xml_objects = xml_file_objects.get(xml_file, {})
        details = file_match_details.get(xml_file, {})
        
        debug_print(f"\n{i:2d}. 文件: {os.path.basename(xml_file)}")
        debug_print(f"    完整路径: {xml_file}")
        debug_print(f"    物体数量: {len(xml_objects)}")
        debug_print(f"    处理状态: {details.get('status', '未知')}")
        
        if xml_objects:
            # 显示前5个物体名称作为示例
            object_names = list(xml_objects.keys())
            debug_print(f"    示例物体名称:")
            for j, name in enumerate(object_names[:5], 1):
                debug_print(f"      {j}. {name}")
            if len(object_names) > 5:
                debug_print(f"      ... 还有 {len(object_names) - 5} 个物体")
    
    # 成功匹配的物体详情
    debug_print(f"\n### 成功匹配的物体详情 (共{len(all_matches)}个) ###")
    debug_print("-" * 80)
    if all_matches:
        for i, match in enumerate(all_matches, 1):
            debug_print(f"\n{i:4d}. XML物体: {match['xml_name']}")
            debug_print(f"      JSON物体: {match['json_name']}")
            debug_print(f"      data_ref: {match.get('data_ref', 'N/A')}")
            
            # 显示光照图数据概要
            lightmap_data = match.get('lightmap_data', {})
            if lightmap_data:
                debug_print(f"      光照图数据:")
                for key, value in lightmap_data.items():
                    if isinstance(value, list):
                        debug_print(f"        {key}: [列表，{len(value)}个元素] {value[:4] if len(value) > 4 else value}{'...' if len(value) > 4 else ''}")
                    else:
                        debug_print(f"        {key}: {value}")
            else:
                debug_print(f"      光照图数据: 空")
            
            # 特别标记目标物体
            if target_object_name and target_object_name in match['xml_name']:
                debug_print(f"      *** 这是目标物体! ***")
    else:
        debug_print("无匹配物体")
    
    # XML中未匹配的物体详情
    debug_print(f"\n### XML中未匹配的物体详情 (共{len(all_unmatched_xml)}个) ###")
    debug_print("-" * 80)
    if all_unmatched_xml:
        for i, (xml_name, xml_obj) in enumerate(sorted(all_unmatched_xml.items()), 1):
            debug_print(f"\n{i:4d}. {xml_name}")
            debug_print(f"      position: {xml_obj.get('position', 'N/A')}")
            debug_print(f"      data_ref: {xml_obj.get('data_ref', 'N/A')}")
            
            # 检查是否是目标物体
            if target_object_name and target_object_name in xml_name:
                debug_print(f"      *** 这是目标物体! ***")
            
            # 尝试在JSON中找到相似的名称
            similar_json_names = []
            for json_name in json_objects.keys():
                if xml_name in json_name or json_name in xml_name:
                    similar_json_names.append(json_name)
            
            if similar_json_names:
                debug_print(f"      可能的JSON匹配项:")
                for similar_name in similar_json_names[:3]:  # 最多显示3个
                    debug_print(f"        - {similar_name}")
                if len(similar_json_names) > 3:
                    debug_print(f"        ... 还有 {len(similar_json_names) - 3} 个相似项")
    else:
        debug_print("无未匹配的XML物体")
    
    # JSON中未匹配的物体详情
    debug_print(f"\n### JSON中未匹配的物体详情 (共{len(all_unmatched_json)}个) ###")
    debug_print("-" * 80)
    if all_unmatched_json:
        for i, (json_name, json_obj) in enumerate(sorted(all_unmatched_json.items()), 1):
            debug_print(f"\n{i:4d}. {json_name}")
            debug_print(f"      position: {json_obj.get('position', 'N/A')}")
            
            # 显示光照图数据概要
            lightmap_data = json_obj.get('lightmap', {})
            if lightmap_data:
                debug_print(f"      光照图数据:")
                for key, value in lightmap_data.items():
                    if isinstance(value, list):
                        debug_print(f"        {key}: [列表，{len(value)}个元素]")
                    else:
                        debug_print(f"        {key}: {value}")
            else:
                debug_print(f"      光照图数据: 空")
            
            # 检查是否包含目标物体名称的一部分
            if target_object_name and (target_object_name in json_name or json_name in target_object_name):
                debug_print(f"      *** 可能是目标物体的匹配项! ***")
            
            # 尝试在XML中找到相似的名称
            similar_xml_names = []
            for xml_name in all_unmatched_xml.keys():
                if json_name in xml_name or xml_name in json_name:
                    similar_xml_names.append(xml_name)
            
            if similar_xml_names:
                debug_print(f"      可能的XML匹配项:")
                for similar_name in similar_xml_names[:3]:  # 最多显示3个
                    debug_print(f"        - {similar_name}")
                if len(similar_xml_names) > 3:
                    debug_print(f"        ... 还有 {len(similar_xml_names) - 3} 个相似项")
    else:
        debug_print("无未匹配的JSON物体")
    
    # 目标物体特别分析
    if target_object_name:
        debug_print(f"\n### 目标物体 '{target_object_name}' 特别分析 ###")
        debug_print("-" * 80)
        
        # 检查是否在匹配列表中
        target_matched = False
        for match in all_matches:
            if target_object_name in match['xml_name']:
                debug_print(f"✓ 目标物体已成功匹配!")
                debug_print(f"  XML名称: {match['xml_name']}")
                debug_print(f"  JSON名称: {match['json_name']}")
                debug_print(f"  data_ref: {match.get('data_ref', 'N/A')}")
                target_matched = True
                break
        
        if not target_matched:
            debug_print(f"✗ 目标物体未匹配")
            
            # 在XML中查找
            xml_found = [name for name in all_unmatched_xml.keys() if target_object_name in name]
            if xml_found:
                debug_print(f"  在XML中找到 {len(xml_found)} 个相关物体:")
                for name in xml_found:
                    debug_print(f"    - {name}")
            else:
                debug_print(f"  在XML中未找到相关物体")
            
            # 在JSON中查找相似的
            json_similar = []
            for json_name in all_unmatched_json.keys():
                # 计算相似度
                target_parts = set(target_object_name.lower().split('_'))
                json_parts = set(json_name.lower().split('_'))
                common_parts = target_parts & json_parts
                if len(common_parts) > 2:  # 至少有3个共同部分
                    similarity = len(common_parts) / len(target_parts | json_parts)
                    json_similar.append((json_name, similarity, common_parts))
            
            # 按相似度排序
            json_similar.sort(key=lambda x: x[1], reverse=True)
            
            if json_similar:
                debug_print(f"  在JSON中找到 {len(json_similar)} 个相似物体:")
                for json_name, similarity, common_parts in json_similar[:5]:  # 显示前5个最相似的
                    debug_print(f"    - {json_name} (相似度: {similarity:.2f}, 共同部分: {common_parts})")
            else:
                debug_print(f"  在JSON中未找到相似物体")
    
    # 匹配统计和建议
    debug_print(f"\n### 匹配统计和建议 ###")
    debug_print("-" * 80)
    
    total_xml_objects = sum(len(objs) for objs in xml_file_objects.values())
    total_json_objects = len(json_objects)
    
    if total_xml_objects > 0:
        xml_match_rate = len(all_matches) / total_xml_objects * 100
        debug_print(f"XML物体匹配率: {xml_match_rate:.1f}% ({len(all_matches)}/{total_xml_objects})")
    
    if total_json_objects > 0:
        json_match_rate = len(all_matches) / total_json_objects * 100
        debug_print(f"JSON物体匹配率: {json_match_rate:.1f}% ({len(all_matches)}/{total_json_objects})")
    
    # 提供改进建议
    debug_print(f"\n改进建议:")
    if len(all_unmatched_xml) > 0 and len(all_unmatched_json) > 0:
        debug_print(f"- 考虑实现模糊匹配算法，基于物体名称的相似度进行匹配")
        debug_print(f"- 检查命名规范：大小写、下划线、特殊字符等")
        debug_print(f"- 分析未匹配物体的命名模式，寻找规律")
    
    if len(all_unmatched_xml) > len(all_unmatched_json):
        debug_print(f"- XML中未匹配物体较多，可能JSON数据不完整")
    elif len(all_unmatched_json) > len(all_unmatched_xml):
        debug_print(f"- JSON中未匹配物体较多，可能XML数据不完整或存在冗余")
    
    debug_print(f"\n" + "="*100)
    debug_print("                         调试报告结束")
    debug_print("="*100)

if __name__ == "__main__":
    main() 