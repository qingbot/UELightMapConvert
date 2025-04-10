import json
import xml.etree.ElementTree as ET
import uuid
import os
import re
import sys
import argparse
from PIL import Image
import GlobalParameter
from datetime import datetime

# 当前的场景名称, 由用户输入
CURRENT_LIGHT_MAP_SCENE_NAME = GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME

# 注册命名空间
ET.register_namespace('', "http://www.boominggames.com")
# XML命名空间
XML_NS = {"ns": "http://www.boominggames.com"}

def generate_sketum_id():
    """生成唯一的sketum_id"""
    return str(uuid.uuid4()).replace('-', '').upper()[:16]

def format_float(value):
    """格式化浮点数,保持最大精度""" 
    # 使用科学计数法并保留17位有效数字（Python float的最大精度）
    return f"{value:.17g}"

def create_lightmap_component(parent, lightmap_data, object_name):
    """创建LightMapComponentDefinition元素"""
    # 获取当前场景的lightmap资源路径
    lightmap_path = GlobalParameter.ALL_LIGHT_MAP_DATA[CURRENT_LIGHT_MAP_SCENE_NAME]["lightmap_path_in_chaos_assets"]
    
    # 检查lightmap_data是否直接在对象中,或者需要从特定键中提取
    if "LightMap" in lightmap_data:
        actual_lightmap_data = lightmap_data["LightMap"]
    elif "lightmap" in lightmap_data:
        actual_lightmap_data = lightmap_data["lightmap"]
    elif "Lightmap" in lightmap_data:
        actual_lightmap_data = lightmap_data["Lightmap"]
    else:
        # 如果找不到标准键,尝试查找任何包含"lightmap"的键（不区分大小写）
        lightmap_key = None
        for key in lightmap_data:
            if "lightmap" in key.lower():
                lightmap_key = key
                break
        
        if lightmap_key:
            actual_lightmap_data = lightmap_data[lightmap_key]
        else:
            # 如果仍未找到,假设整个对象就是lightmap数据
            actual_lightmap_data = lightmap_data
    
    # 打印调试信息
    print(f"为对象 {object_name} 创建LightMap组件,数据类型: {type(actual_lightmap_data)}")
    if isinstance(actual_lightmap_data, dict):
        print(f"LightMap键: {', '.join(actual_lightmap_data.keys())}")
    
    # 创建LightMapComponentDefinition元素
    lightmap_comp = ET.SubElement(parent, "element", {
        "sketum_id": generate_sketum_id(), 
        "type": "LightMapComponentDefinition"
    })
    
    # 添加group元素
    group = ET.SubElement(lightmap_comp, "group")
    group.text = "default"
    
    # 添加LQ元素
    lq = ET.SubElement(lightmap_comp, "LQ")
    lq_url = ET.SubElement(lq, "url")
    
    # 尝试提取LQ值,考虑不同的键名和数据结构
    lq_value = extract_value(actual_lightmap_data, ["LQ", "lq", "lowquality", "low_quality"])
    if lq_value:
        lq_url.text = f"{lightmap_path}/{lq_value}.texture.ast"
    else:
        lq_url.text = ""
    
    # 添加guid和parameter元素到LQ
    guid_lq = ET.SubElement(lq, "guid")
    param_lq = ET.SubElement(lq, "parameter")
    params_lq = ET.SubElement(param_lq, "parameters")
    
    # 添加Dir元素
    dir_elem = ET.SubElement(lightmap_comp, "Dir")
    dir_url = ET.SubElement(dir_elem, "url")
    
    # 尝试提取Dir值,考虑不同的键名和数据结构
    dir_value = extract_value(actual_lightmap_data, ["Dir", "dir", "direction", "DIR"])
    if dir_value:
        dir_url.text = f"{lightmap_path}/{dir_value}.texture.ast"
    else:
        dir_url.text = ""
    
    # 添加guid和parameter元素到Dir
    guid_dir = ET.SubElement(dir_elem, "guid")
    param_dir = ET.SubElement(dir_elem, "parameter")
    params_dir = ET.SubElement(param_dir, "parameters")
    
    # 添加BiasScale元素
    bias_scale = ET.SubElement(lightmap_comp, "BiasScale")
    
    # 尝试提取BiasScale值,考虑不同的键名和数据结构
    bias_scale_value = extract_value(actual_lightmap_data, ["BiasScale", "biasscale", "bias_scale", "bias"])
    if bias_scale_value and isinstance(bias_scale_value, list):
        # 格式化BiasScale数据为空格分隔的字符串
        bias_scale.text = " ".join([format_float(val) for val in bias_scale_value])
    else:
        bias_scale.text = "0.0 0.0 0.0 0.0"
    
    # 添加CoefAdd元素
    coef_add = ET.SubElement(lightmap_comp, "CoefAdd")
    
    # 尝试提取CoefAdd值,考虑不同的键名和数据结构
    coef_add_value = extract_value(actual_lightmap_data, ["CoefAdd", "coefadd", "coef_add"])
    if coef_add_value and isinstance(coef_add_value, list):
        for val in coef_add_value:
            element = ET.SubElement(coef_add, "element", {"sketum_id": generate_sketum_id()})
            element.text = format_float(val)
    
    # 添加CoefScale元素
    coef_scale = ET.SubElement(lightmap_comp, "CoefScale")
    
    # 尝试提取CoefScale值,考虑不同的键名和数据结构
    coef_scale_value = extract_value(actual_lightmap_data, ["CoefScale", "coefscale", "coef_scale"])
    if coef_scale_value and isinstance(coef_scale_value, list):
        for val in coef_scale_value:
            element = ET.SubElement(coef_scale, "element", {"sketum_id": generate_sketum_id()})
            element.text = format_float(val)
            
    print(f"已为对象 {object_name} 创建LightMap组件")
    return lightmap_comp

def extract_value(data, possible_keys):
    """从数据对象中提取值,考虑多种可能的键名"""
    if not isinstance(data, dict):
        return None
    
    # 尝试不同的键名
    for key in possible_keys:
        if key in data:
            return data[key]
    
    # 如果未找到,尝试忽略大小写的比较
    for key in data:
        for possible_key in possible_keys:
            if key.lower() == possible_key.lower():
                return data[key]
    
    return None

def position_match(json_pos, xml_pos, tolerance=0.1):
    """比较JSON和XML中的位置是否匹配（考虑到可能的精度差异）"""
    xml_values = [float(val) for val in xml_pos.split()]
    if len(xml_values) != 3 or len(json_pos) != 3:
        return False
    
    # 计算距离的平方
    dist_squared = sum((a - b) ** 2 for a, b in zip(json_pos, xml_values))
    return dist_squared < tolerance ** 2

def save_xml_with_original_tags(tree, output_path, original_file_path):
    """
    保存XML文件,但保持原有的标签名称（防止<name>变成<n>等问题）
    """
    # 先将树写入字符串
    xml_str = ET.tostring(tree.getroot(), encoding='UTF-8', method='xml')
    xml_str_decoded = xml_str.decode('UTF-8')
    
    # 直接替换所有<n>和</n>标签为<name>和</name>
    xml_str_decoded = xml_str_decoded.replace('<n>', '<name>')
    xml_str_decoded = xml_str_decoded.replace('</n>', '</name>')
    
    # 写入文件
    try:
        with open(output_path, 'w', encoding='UTF-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(xml_str_decoded[xml_str_decoded.find('<'):])
        
        print(f"已保存XML文件到: {output_path}")
    except Exception as e:
        print(f"尝试保持原始标签名称时出错: {str(e)}")
        # 如果出错,使用普通方式保存
        tree.write(output_path, encoding='UTF-8', xml_declaration=True)
        print(f"已使用标准方式保存XML文件到: {output_path}")

def find_lightmaps_recursively(data, path="", results=None):
    """
    递归搜索对象中的LightMap或lightmap信息
    
    Args:
        data: 要搜索的数据对象（可以是字典或列表）
        path: 当前路径,用于跟踪位置
        results: 存储结果的字典
        
    Returns:
        包含所有找到的带有LightMap信息的对象的字典
    """
    if results is None:
        results = {}
    
    # 如果是字典,检查键
    if isinstance(data, dict):
        # 检查是否有LightMap或lightmap键
        has_lightmap = False
        lightmap_data = None
        
        # 检查不同大小写的lightmap键
        for key in ["LightMap", "lightmap", "Lightmap", "LIGHTMAP"]:
            if key in data:
                has_lightmap = True
                lightmap_data = data[key]
                break
        
        # 如果当前对象有名称和LightMap数据,将其添加到结果中
        if has_lightmap and "Name" in data:
            object_name = data["Name"]
            results[object_name] = data
            print(f"找到LightMap对象: {object_name} 在路径 {path}")
        
        # 递归搜索所有子属性
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            find_lightmaps_recursively(value, new_path, results)
    
    # 如果是列表,递归搜索每个元素
    elif isinstance(data, list):
        for i, item in enumerate(data):
            new_path = f"{path}[{i}]"
            find_lightmaps_recursively(item, new_path, results)
    
    return results

def update_xml_with_json(xml_path=None):
    """从JSON文件提取带有Lightmap的物体,并更新到XML文件中"""
    # 获取当前场景的配置
    scene_config = GlobalParameter.ALL_LIGHT_MAP_DATA[CURRENT_LIGHT_MAP_SCENE_NAME]
    
    # 选择正确的文件路径
    json_path = scene_config["source_lightmap_json_path"]
    
    # xml_path参数为空时，从配置获取XML文件夹路径
    xml_folder_path = scene_config["source_scene_xml_folder_path"] if xml_path is None else os.path.dirname(xml_path)
    
    # 如果是单个文件处理模式
    single_file_mode = xml_path is not None
    
    # 如果源文件不存在,尝试使用测试文件
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"无法找到JSON文件: {json_path}")
    
    if single_file_mode and not os.path.exists(xml_path):
        print(f"警告: 源XML文件 {xml_path} 不存在")
        raise FileNotFoundError(f"无法找到XML文件: {xml_path}")
    
    if not single_file_mode and not os.path.exists(xml_folder_path):
        print(f"警告: 源XML文件夹 {xml_folder_path} 不存在")
        raise FileNotFoundError(f"无法找到XML文件夹: {xml_folder_path}")
    
    print(f"正在读取JSON文件: {json_path}")
    
    # 读取JSON数据
    try:
        with open(json_path, 'r') as f:
            json_data = json.load(f)
            print(f"成功读取JSON文件,包含 {len(json_data)} 个对象")
            # 打印前5个对象的名称,提供样本
            sample_keys = list(json_data.keys())[:5]
            print(f"对象示例: {', '.join(sample_keys)}")
    except Exception as e:
        raise Exception(f"读取JSON文件 {json_path} 失败: {str(e)}")
    
    # 筛选出有Lightmap的物体 - 使用新的递归方法
    print("开始递归搜索LightMap信息...")
    objects_with_lightmap = find_lightmaps_recursively(json_data)
    
    # 如果使用新方法仍然没有找到,尝试旧方法
    if not objects_with_lightmap:
        print("使用递归方法未找到LightMap信息,尝试直接搜索...")
        for obj_name, obj_data in json_data.items():
            if isinstance(obj_data, dict):
                # 直接检查是否存在LightMap属性（不区分大小写）
                lightmap_key = None
                for key in obj_data:
                    if key.lower() == "lightmap":
                        lightmap_key = key
                        break
                
                if lightmap_key:
                    objects_with_lightmap[obj_name] = obj_data
                    print(f"找到LightMap对象: {obj_name} (使用键: {lightmap_key})")
                # 检查嵌套的情况
                elif "properties" in obj_data and isinstance(obj_data["properties"], dict):
                    props = obj_data["properties"]
                    for key in props:
                        if key.lower() == "lightmap":
                            objects_with_lightmap[obj_name] = obj_data
                            print(f"找到LightMap对象: {obj_name} (嵌套在properties中)")
                            break
    
    # 如果仍然没有找到任何带有LightMap的对象,打印JSON的基本结构
    if not objects_with_lightmap:
        print("未找到任何带有LightMap的对象,打印JSON结构:")
        print_json_structure(json_data)
        return []
    
    print(f"找到 {len(objects_with_lightmap)} 个带有LightMap的物体")
    
    # 如果找到了带有LightMap的物体,打印前3个作为样本
    if objects_with_lightmap:
        sample_objects = list(objects_with_lightmap.keys())[:3]
        print(f"带LightMap的物体示例: {', '.join(sample_objects)}")
    
    # 获取要处理的XML文件列表
    xml_files = []
    if single_file_mode:
        xml_files = [xml_path]
    else:
        # 获取文件夹中所有.ast结尾的文件
        xml_files = [os.path.join(xml_folder_path, f) for f in os.listdir(xml_folder_path) if f.endswith('.ast')]
    
    if not xml_files:
        print(f"警告: 没有找到需要处理的XML文件")
        return []
    
    print(f"找到 {len(xml_files)} 个XML文件需要处理")
    
    # 创建backup目录
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup")
    os.makedirs(backup_dir, exist_ok=True)
    
    # 创建以时间戳命名的子目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = os.path.join(backup_dir, timestamp)
    os.makedirs(backup_subdir, exist_ok=True)
    print(f"创建备份子目录: {backup_subdir}")
    
    updated_files = []
    
    # 处理每个XML文件
    for xml_file in xml_files:
        print(f"\n正在处理XML文件: {xml_file}")
        try:
            # 读取XML文件
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                print(f"成功读取XML文件,根元素标签: {root.tag}")
            except Exception as e:
                print(f"读取XML文件 {xml_file} 失败: {str(e)}")
                continue
            
            # 查找所有StaticObjectInstanceData元素,处理命名空间
            # 尝试不同的查询方式来查找元素
            
            # 尝试直接查找不带命名空间的元素
            static_objects = root.findall(".//element[@type='StaticObjectInstanceData']")
            
            # 如果没有找到,尝试使用命名空间查询
            if not static_objects:
                static_objects = root.findall(".//ns:element[@type='StaticObjectInstanceData']", XML_NS)
            
            # 如果仍然没有找到,尝试其他方法
            if not static_objects:
                # 直接找所有element元素
                all_elements = root.findall(".//element")
                if not all_elements:
                    all_elements = root.findall(".//ns:element", XML_NS)
                
                # 打印前5个element的属性,帮助调试
                print(f"在XML中找到 {len(all_elements)} 个element元素")
                for i, elem in enumerate(all_elements[:5]):
                    print(f"Element {i+1}: {elem.attrib}")
                
                # 过滤出StaticObjectInstanceData类型的元素
                static_objects = [elem for elem in all_elements if elem.get("type") == "StaticObjectInstanceData"]
            
            print(f"在XML中找到 {len(static_objects)} 个StaticObjectInstanceData元素")
            
            # 如果仍然没有找到,可能是标签名称不同
            if not static_objects:
                # 尝试查找各种可能的对象类型
                possible_types = ["StaticObjectInstanceData", "StaticMesh", "Object", "MeshActor"]
                for elem_type in possible_types:
                    elements = root.findall(f".//element[@type='{elem_type}']")
                    if elements:
                        static_objects.extend(elements)
                        print(f"找到 {len(elements)} 个 {elem_type} 元素")
                
                # 如果仍然没有找到,尝试查找所有带有name子元素的元素
                if not static_objects:
                    # 遍历所有元素,查找name子元素
                    for elem in root.findall(".//*"):
                        name_elem = elem.find("name")
                        if name_elem is not None and name_elem.text:
                            static_objects.append(elem)
                            print(f"找到带有name元素的XML节点: {elem.tag}, name={name_elem.text}")
            
            updated_count = 0
            created_count = 0
            
            # 创建物体名称到XML元素的映射,用于快速查找
            name_to_element = {}
            position_info = {}  # 存储位置信息,用于后续匹配
            
            for element in static_objects:
                # 获取物体名称
                name_elem = element.find("name")
                if name_elem is None:
                    name_elem = element.find("ns:name", XML_NS)
                
                if name_elem is not None and name_elem.text:
                    obj_name = name_elem.text
                    name_to_element[obj_name] = element
                    print(f"找到XML中的物体: {obj_name}")
                    
                    # 提取位置信息,用于后续匹配
                    transform_elem = element.find("transform")
                    if transform_elem is not None:
                        position_elem = transform_elem.find("position")
                        if position_elem is not None and position_elem.text:
                            position_info[obj_name] = position_elem.text
            
            print(f"创建了名称映射,包含 {len(name_to_element)} 个命名物体")
            
            # 创建XML元素到JSON对象的映射
            matched_elements = {}
            
            # 先按名称匹配
            for obj_name, json_obj in objects_with_lightmap.items():
                if obj_name in name_to_element:
                    matched_elements[obj_name] = (name_to_element[obj_name], json_obj)
                    print(f"通过名称匹配: {obj_name}")
            
            # 对于未匹配的物体,尝试通过位置匹配
            unmatched_json_objects = {obj_name: obj_data for obj_name, obj_data in objects_with_lightmap.items() 
                                     if obj_name not in matched_elements}
            
            if unmatched_json_objects:
                print(f"尝试通过位置匹配 {len(unmatched_json_objects)} 个未匹配的物体...")
                
                for obj_name, json_obj in unmatched_json_objects.items():
                    if "Location" in json_obj and isinstance(json_obj["Location"], list):
                        json_location = json_obj["Location"]
                        
                        # 查找位置相似的XML物体
                        for xml_name, xml_position in position_info.items():
                            if xml_name in matched_elements:
                                continue  # 跳过已匹配的物体
                            
                            if position_match(json_location, xml_position):
                                matched_elements[obj_name] = (name_to_element[xml_name], json_obj)
                                print(f"通过位置匹配: {obj_name} -> {xml_name}")
                                break
            
            # 处理所有匹配的物体
            for obj_name, (element, json_obj) in matched_elements.items():
                print(f"处理物体: {obj_name}")
                
                # 找到匹配的物体后,更新或创建LightMap组件
                added_components = element.find("added_components")
                if added_components is None:
                    added_components = element.find("ns:added_components", XML_NS)
                
                if added_components is None:
                    # 如果没有added_components元素,创建一个
                    added_components = ET.SubElement(element, "added_components")
                    lightmap_comp = create_lightmap_component(added_components, json_obj, obj_name)
                    created_count += 1
                else:
                    # 查找现有的LightMapComponentDefinition
                    found = False
                    lightmap_comps = added_components.findall("element[@type='LightMapComponentDefinition']")
                    if not lightmap_comps:
                        lightmap_comps = added_components.findall("ns:element[@type='LightMapComponentDefinition']", XML_NS)
                    
                    for comp in lightmap_comps:
                        # 已找到现有的LightMap组件,更新它
                        added_components.remove(comp)  # 移除现有组件
                        lightmap_comp = create_lightmap_component(added_components, json_obj, obj_name)
                        updated_count += 1
                        found = True
                        break
                    
                    if not found:
                        # 没有找到现有的LightMap组件,创建一个新的
                        lightmap_comp = create_lightmap_component(added_components, json_obj, obj_name)
                        created_count += 1
            
            # 如果没有找到任何匹配的物体,生成更多的调试信息
            if updated_count == 0 and created_count == 0:
                print(f"警告: 在 {xml_file} 中未找到任何匹配的物体进行更新!")
                continue
            
            # 使用原始文件名创建备份文件
            xml_filename = os.path.basename(xml_file)
            backup_path = os.path.join(backup_subdir, xml_filename)
            
            # 复制原文件作为备份
            import shutil
            shutil.copy2(xml_file, backup_path)
            print(f"已创建备份文件: {backup_path}")
            
            # 保存到原文件
            save_xml_with_original_tags(tree, xml_file, xml_file)
            
            print(f"已更新 {updated_count} 个物体的LightMap组件,新创建了 {created_count} 个LightMap组件")
            print(f"已将更新后的XML保存回原文件: {xml_file}")
            
            updated_files.append({
                "original_path": xml_file, 
                "backup_path": backup_path,
                "updated_count": updated_count,
                "created_count": created_count
            })
            
        except Exception as e:
            print(f"处理XML文件 {xml_file} 时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return updated_files

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="从JSON文件提取Lightmap信息并更新到XML文件")
    
    # 添加场景名称参数
    parser.add_argument("--scene", "-s", type=str, default=CURRENT_LIGHT_MAP_SCENE_NAME,
                        help=f"指定要处理的场景名称，默认为{CURRENT_LIGHT_MAP_SCENE_NAME}")
    
    # 添加处理类型参数
    parser.add_argument("--process-staticmesh", action="store_true", default=False,
                        help="处理StaticMesh的光照图")
    parser.add_argument("--process-terrain", action="store_true", default=False,
                        help="处理地形的光照图")
    parser.add_argument("--process-all", action="store_true", default=False,
                        help="处理所有类型的光照图（包括StaticMesh和地形）")
    
    # 解析参数
    args = parser.parse_args()
    
    # 检查场景是否存在
    if args.scene not in GlobalParameter.ALL_LIGHT_MAP_DATA:
        print(f"错误: 指定的场景 '{args.scene}' 不存在")
        print(f"可用的场景有: {', '.join(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())}")
        sys.exit(1)
    
    # 如果没有指定处理类型，默认处理StaticMesh
    if not (args.process_staticmesh or args.process_terrain or args.process_all):
        args.process_staticmesh = True
    
    # 如果指定了process_all，则同时处理StaticMesh和地形
    if args.process_all:
        args.process_staticmesh = True
        args.process_terrain = True
    
    return args

def process_scene(scene_name, process_staticmesh=True, process_terrain=False):
    """处理单个场景"""
    global CURRENT_LIGHT_MAP_SCENE_NAME
    
    # 设置全局变量
    CURRENT_LIGHT_MAP_SCENE_NAME = scene_name
    
    # 获取场景配置
    scene_config = GlobalParameter.ALL_LIGHT_MAP_DATA[scene_name]
    
    print(f"\n正在处理场景: {scene_name}")
    print(f"场景XML文件夹: {scene_config['source_scene_xml_folder_path']}")
    print(f"JSON数据文件: {scene_config['source_lightmap_json_path']}")
    print(f"Lightmap路径: {scene_config['lightmap_path_in_chaos_assets']}")
    
    results = {
        "staticmesh_updated": False,
        "terrain_updated": False,
        "staticmesh_files": [],
        "terrain_file": None
    }
    
    # 处理StaticMesh
    if process_staticmesh:
        print(f"\n== 开始处理StaticMesh光照图 ==")
        try:
            # 更新XML文件
            updated_files = update_xml_with_json()
            
            if updated_files:
                print(f"\nStaticMesh处理完成! 更新了 {len(updated_files)} 个XML文件:")
                for file_info in updated_files:
                    print(f"  - {file_info['original_path']} (更新: {file_info['updated_count']}, 创建: {file_info['created_count']})")
                    print(f"    备份文件: {file_info['backup_path']}")
                
                results["staticmesh_updated"] = True
                results["staticmesh_files"] = updated_files
            else:
                print(f"\nStaticMesh未更新任何文件")
        except Exception as e:
            print(f"处理StaticMesh失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    # 处理地形
    if process_terrain:
        print(f"\n== 开始处理地形光照图 ==")
        try:
            # 检查地形XML文件是否存在
            if "source_terrain_xml_path" not in scene_config or not scene_config["source_terrain_xml_path"]:
                print(f"错误: 场景 {scene_name} 未配置地形XML文件路径")
            elif not os.path.exists(scene_config["source_terrain_xml_path"]):
                print(f"错误: 地形XML文件不存在: {scene_config['source_terrain_xml_path']}")
            else:
                # 直接从JSON文件中解析地形数据
                json_path = scene_config["source_lightmap_json_path"]
                if not os.path.exists(json_path):
                    print(f"错误: JSON文件不存在: {json_path}")
                else:
                    # 更新地形XML文件
                    if update_terrain_xml(json_path, scene_config):
                        results["terrain_updated"] = True
                        results["terrain_file"] = scene_config["source_terrain_xml_path"]
                        print(f"\n地形光照图处理成功!")
                    else:
                        print(f"\n地形XML更新失败")
        except Exception as e:
            print(f"处理地形失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    return results

def main():
    """主函数"""
    # 解析命令行参数
    args = parse_arguments()
    scene_name = args.scene
    
    try:
        print(f"将处理场景: {scene_name}")
        print(f"处理StaticMesh: {'是' if args.process_staticmesh else '否'}")
        print(f"处理地形: {'是' if args.process_terrain else '否'}")
        
        try:
            results = process_scene(scene_name, args.process_staticmesh, args.process_terrain)
            
            print(f"\n=============== 处理结果汇总 ===============")
            if args.process_staticmesh:
                if results["staticmesh_updated"]:
                    print(f"StaticMesh: 成功 (更新了 {len(results['staticmesh_files'])} 个文件)")
                    for file_info in results["staticmesh_files"]:
                        print(f"  - {os.path.basename(file_info['original_path'])} (更新: {file_info['updated_count']}, 创建: {file_info['created_count']})")
                else:
                    print(f"StaticMesh: 未找到需要更新的文件")
            
            if args.process_terrain:
                if results["terrain_updated"]:
                    print(f"地形: 成功 (更新了文件: {os.path.basename(results['terrain_file'])})")
                else:
                    print(f"地形: 未更新")
            
            print(f"===========================================")
        except Exception as e:
            print(f"\n处理结果: 失败")
            print(f"处理场景 {scene_name} 失败: {str(e)}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
        import traceback
        traceback.print_exc()

def print_json_structure(data, max_depth=3, current_depth=0, path=""):
    """
    打印JSON的结构,帮助调试
    
    Args:
        data: 要打印的数据
        max_depth: 最大深度,防止无限递归
        current_depth: 当前深度
        path: 当前路径
    """
    if current_depth > max_depth:
        print(f"{' ' * (current_depth * 2)}{path}: ... (达到最大深度)")
        return
    
    if isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{path}.{key}" if path else key
            
            if isinstance(value, dict):
                print(f"{' ' * (current_depth * 2)}{new_path}: 字典 ({len(value)} 个键)")
                print_json_structure(value, max_depth, current_depth + 1, new_path)
            elif isinstance(value, list):
                print(f"{' ' * (current_depth * 2)}{new_path}: 列表 ({len(value)} 个元素)")
                if len(value) > 0:
                    # 打印列表的第一个元素的类型
                    item = value[0]
                    if isinstance(item, dict):
                        print(f"{' ' * ((current_depth+1) * 2)}第一个元素: 字典 ({len(item)} 个键)")
                        for k in list(item.keys())[:3]:  # 只打印前3个键
                            print(f"{' ' * ((current_depth+2) * 2)}{k}")
                        if len(item) > 3:
                            print(f"{' ' * ((current_depth+2) * 2)}... 等 {len(item)-3} 个键")
                    else:
                        print(f"{' ' * ((current_depth+1) * 2)}第一个元素: {type(item).__name__}")
            else:
                value_str = str(value)
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                print(f"{' ' * (current_depth * 2)}{new_path}: {type(value).__name__} = {value_str}")
    elif isinstance(data, list):
        print(f"{' ' * (current_depth * 2)}{path}: 列表 ({len(data)} 个元素)")
        if len(data) > 0:
            # 只打印第一个元素
            print_json_structure(data[0], max_depth, current_depth + 1, f"{path}[0]")
            if len(data) > 1:
                print(f"{' ' * (current_depth * 2)}... 等 {len(data)-1} 个元素")

def extract_terrain_data_from_json(json_path):
    """
    从JSON文件中提取地形的Lightmap数据
    
    Args:
        json_path: JSON文件路径
    
    Returns:
        dict: 包含地形Lightmap数据的字典，如果找不到则返回None
    """
    try:
        # 读取JSON文件
        with open(json_path, 'r') as f:
            json_data = json.load(f)
        
        print(f"正在从JSON文件提取地形数据: {json_path}")
        
        # 查找地形数据 - 首先尝试直接在根级别查找
        if "Landscape" in json_data:
            print("在根级别找到Landscape数据")
            landscape_data = json_data["Landscape"]
            
            # 检查是否有嵌套的Landscape
            if isinstance(landscape_data, dict) and "Landscape" in landscape_data:
                landscape_data = landscape_data["Landscape"]
                print("找到嵌套的Landscape数据")
            
            # 检查是否有lightmapGroup
            if isinstance(landscape_data, dict) and "lightmapGroup" in landscape_data:
                lightmap_group = landscape_data["lightmapGroup"]
                
                # 检查是否有combine字段，这是合并后的贴图名称
                if "combine" in lightmap_group:
                    combine_name = lightmap_group["combine"]
                    print(f"找到地形合并的Lightmap: {combine_name}")
                    
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
                                
                                # 确保我们有足够的数据
                                if len(coef_scale) >= 12 and len(coef_add) >= 12:
                                    # 通常系数在索引8-11位置
                                    coef_scales.append(coef_scale[8:12])
                                    coef_adds.append(coef_add[8:12])
                    
                    # 如果找到系数数据，计算平均值
                    if coef_scales and coef_adds:
                        # 计算平均系数
                        avg_coef_scale = [sum(col)/len(col) for col in zip(*coef_scales)]
                        avg_coef_add = [sum(col)/len(col) for col in zip(*coef_adds)]
                        
                        print(f"计算了 {len(coef_scales)} 个网格的平均系数")
                        print(f"平均CoefScale: {avg_coef_scale}")
                        print(f"平均CoefAdd: {avg_coef_add}")
                        
                        # 返回结果
                        return {
                            "combine_name": combine_name,
                            "lightmap_coef_scale": avg_coef_scale,
                            "lightmap_coef_add": avg_coef_add
                        }
                    else:
                        print("未找到有效的系数数据")
                else:
                    print("未找到地形合并的Lightmap名称")
            else:
                print("未找到lightmapGroup数据")
        else:
            print("未在JSON中找到Landscape数据")
            
            # 如果在根级别找不到，尝试在'Terrain'字段中查找
            if "Terrain" in json_data:
                print("尝试在Terrain字段中查找数据")
                terrain_data = json_data["Terrain"]
                
                # 查找合并的Lightmap信息
                if isinstance(terrain_data, dict) and "lightmap" in terrain_data:
                    lightmap_data = terrain_data["lightmap"]
                    
                    if "combine_name" in lightmap_data:
                        combine_name = lightmap_data["combine_name"]
                        print(f"找到地形合并的Lightmap: {combine_name}")
                        
                        # 查找系数数据
                        if "coef_scale" in lightmap_data and "coef_add" in lightmap_data:
                            coef_scale = lightmap_data["coef_scale"]
                            coef_add = lightmap_data["coef_add"]
                            
                            return {
                                "combine_name": combine_name,
                                "lightmap_coef_scale": coef_scale,
                                "lightmap_coef_add": coef_add
                            }
        
        # 如果没有找到地形数据，打印JSON结构以帮助调试
        print("未能找到有效的地形Lightmap数据，打印JSON结构:")
        print_json_structure(json_data)
        
        return None
    except Exception as e:
        print(f"提取地形数据时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def update_terrain_xml(json_path, scene_config):
    """
    更新地形XML文件中的lightmap数据
    
    Args:
        json_path: JSON文件路径，包含地形的Lightmap数据
        scene_config: 场景配置信息
    
    Returns:
        bool: 更新是否成功
    """
    xml_path = scene_config["source_terrain_xml_path"]
    if not os.path.exists(xml_path):
        print(f"错误: 地形XML文件不存在: {xml_path}")
        return False
    
    # 获取lightmap资源路径
    lightmap_path = scene_config["lightmap_path_in_chaos_assets"]
    
    # 从JSON中提取地形数据
    terrain_result = extract_terrain_data_from_json(json_path)
    if not terrain_result:
        print(f"无法从JSON中提取地形Lightmap数据: {json_path}")
        return False
    
    try:
        # 解析XML文件
        print(f"正在读取地形XML文件: {xml_path}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # 查找terrain_lightmap_data元素
        terrain_lightmap_data = root.find(".//terrain_lightmap_data")
        if terrain_lightmap_data is None:
            terrain_lightmap_data = root.find(".//ns:terrain_lightmap_data", XML_NS)
        
        if terrain_lightmap_data is None:
            print(f"警告: 在XML文件中未找到terrain_lightmap_data元素")
            return False
        
        # 备份原始XML用于调试
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp:
            debug_path = tmp.name
            tree.write(debug_path)
            print(f"已创建XML调试文件: {debug_path}")
        
        # 创建一个全新的terrain_lightmap_data元素
        new_data = ET.Element("terrain_lightmap_data")
        
        # 创建CoefAdd元素
        coef_add = ET.SubElement(new_data, "CoefAdd")
        coef_add_value = " ".join([format_float(val) for val in terrain_result["lightmap_coef_add"]])
        coef_add.text = coef_add_value
        
        # 创建CoefScale元素
        coef_scale = ET.SubElement(new_data, "CoefScale")
        coef_scale_value = " ".join([format_float(val) for val in terrain_result["lightmap_coef_scale"]])
        coef_scale.text = coef_scale_value
        
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
                print(f"使用配置的terrain_size_offset [{size_x}, {size_y}, {offset_x}, {offset_y}] 计算BiasScale: {bias_scale_text}")
            else:
                print(f"警告: terrain_size_offset数组长度不足 ({len(terrain_size_offset)}), 使用默认BiasScale值")
                bias_scale_text = "0.000000 0.000000 1.000000 1.000000"
        else:
            print(f"警告: 未找到terrain_size_offset配置, 使用默认BiasScale值")
            bias_scale_text = "0.000000 0.000000 1.000000 1.000000"
        
        # 创建BiasScale元素
        bias_scale = ET.SubElement(new_data, "BiasScale")
        bias_scale.text = bias_scale_text
        
        # 创建terrainLightMap元素
        terrain_light_map = ET.SubElement(new_data, "terrainLightMap")
        
        # 创建url元素
        url = ET.SubElement(terrain_light_map, "url")
        url.text = f"{lightmap_path}/{terrain_result['combine_name']}.texture.ast"
        
        # 创建guid和parameter元素
        guid = ET.SubElement(terrain_light_map, "guid")
        parameter = ET.SubElement(terrain_light_map, "parameter")
        parameters = ET.SubElement(parameter, "parameters")
        
        # 找到terrain_lightmap_data的父元素和索引位置
        parent = None
        index = -1
        for elem in root.iter():
            for i, child in enumerate(list(elem)):
                if child == terrain_lightmap_data:
                    parent = elem
                    index = i
                    break
            if parent:
                break
        
        if parent is None:
            print("无法找到terrain_lightmap_data的父元素")
            return False
            
        # 确保我们替换的元素保持在原来的位置，以维持与其他元素的相对位置关系
        # 直接替换而不是删除后添加，这样可以保持原来的顺序
        parent[index] = new_data
        
        # 调试信息
        print(f"已替换地形XML中的terrain_lightmap_data元素在索引 {index}")
        # 打印父元素的所有子元素名称，确认顺序
        child_elements = [child.tag for child in parent]
        print(f"父元素的子元素顺序: {child_elements}")
        
        # 创建backup目录
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        # 创建以时间戳命名的子目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = os.path.join(backup_dir, timestamp)
        os.makedirs(backup_subdir, exist_ok=True)
        
        # 使用原始文件名创建备份文件
        xml_filename = os.path.basename(xml_path)
        backup_path = os.path.join(backup_subdir, xml_filename)
        
        # 复制原文件作为备份
        import shutil
        shutil.copy2(xml_path, backup_path)
        print(f"已创建备份文件: {backup_path}")
        
        # 保存修改后的XML
        save_xml_with_original_tags(tree, xml_path, xml_path)
        print(f"已更新地形XML文件: {xml_path}")
        print(f"Lightmap URL: {f'{lightmap_path}/{terrain_result['combine_name']}.texture.ast'}")
        print(f"CoefAdd: {coef_add_value}")
        print(f"CoefScale: {coef_scale_value}")
        print(f"BiasScale: {bias_scale_text}")
        
        return True
    except Exception as e:
        print(f"更新地形XML文件时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main() 