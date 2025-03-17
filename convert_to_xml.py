import json
import xml.etree.ElementTree as ET
import uuid
import os
import re
import sys
import argparse
from PIL import Image
import GlobalParameter


# 当前的场景名称, 由用户输入
CURRENT_LIGHT_MAP_SCENE_NAME = GlobalParameter.DEFAULT_LIGHT_MAP_SCENE_NAME

# 为了测试方便，如果文件不存在，可以使用以下临时测试文件
TEST_JSON_PATH = "test_scene_data.json"
TEST_XML_PATH = "test_scene.xml"

# 是否使用测试文件
USE_TEST_FILES = False  # 使用真实数据文件

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
    
    # 添加HQ元素
    hq = ET.SubElement(lightmap_comp, "HQ")
    hq_url = ET.SubElement(hq, "url")
    
    # 尝试提取HQ值,考虑不同的键名和数据结构
    hq_value = extract_value(actual_lightmap_data, ["HQ", "hq", "highquality", "high_quality"])
    if hq_value:
        hq_url.text = f"{lightmap_path}/{hq_value}.texture.ast"
    else:
        hq_url.text = ""
    
    # 添加guid和parameter元素到HQ
    guid_hq = ET.SubElement(hq, "guid")
    param_hq = ET.SubElement(hq, "parameter")
    params_hq = ET.SubElement(param_hq, "parameters")
    
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

def update_xml_with_json():
    """从JSON文件提取带有Lightmap的物体,并更新到XML文件中"""
    # 获取当前场景的配置
    scene_config = GlobalParameter.ALL_LIGHT_MAP_DATA[CURRENT_LIGHT_MAP_SCENE_NAME]
    
    # 选择正确的文件路径
    json_path = TEST_JSON_PATH if USE_TEST_FILES else scene_config["source_lightmap_json_path"]
    xml_path = TEST_XML_PATH if USE_TEST_FILES else scene_config["source_scene_xml_path"]
    
    # 如果源文件不存在,尝试使用测试文件
    if not os.path.exists(json_path):
        print(f"警告: 源JSON文件 {json_path} 不存在,尝试使用测试文件 {TEST_JSON_PATH}")
        if os.path.exists(TEST_JSON_PATH):
            json_path = TEST_JSON_PATH
        else:
            raise FileNotFoundError(f"无法找到JSON文件: {json_path} 或 {TEST_JSON_PATH}")
    
    if not os.path.exists(xml_path):
        print(f"警告: 源XML文件 {xml_path} 不存在,尝试使用测试文件 {TEST_XML_PATH}")
        if os.path.exists(TEST_XML_PATH):
            xml_path = TEST_XML_PATH
        else:
            raise FileNotFoundError(f"无法找到XML文件: {xml_path} 或 {TEST_XML_PATH}")
    
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
    
    print(f"找到 {len(objects_with_lightmap)} 个带有LightMap的物体")
    
    # 如果找到了带有LightMap的物体,打印前3个作为样本
    if objects_with_lightmap:
        sample_objects = list(objects_with_lightmap.keys())[:3]
        print(f"带LightMap的物体示例: {', '.join(sample_objects)}")
    
    # 读取XML文件
    print(f"正在读取XML文件: {xml_path}")
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        print(f"成功读取XML文件,根元素标签: {root.tag}")
    except Exception as e:
        raise Exception(f"读取XML文件 {xml_path} 失败: {str(e)}")
    
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
        print("警告: 未找到任何匹配的物体进行更新!")
        print(f"JSON中物体名称: {list(objects_with_lightmap.keys())[:10]}")
        print(f"XML中物体名称: {list(name_to_element.keys())[:10]}")
    
    # 保存修改后的XML文件
    output_path = xml_path.replace(".ast", "_updated.ast")
    if output_path == xml_path:  # 防止覆盖原文件
        output_path = xml_path + ".updated"
    
    # 使用自定义函数保存,保持原有的标签名称
    save_xml_with_original_tags(tree, output_path, xml_path)
    
    print(f"已更新 {updated_count} 个物体的LightMap组件,新创建了 {created_count} 个LightMap组件")
    print(f"已将更新后的XML保存到: {output_path}")
    
    return output_path  # 返回更新后的文件路径,方便后续处理

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="从JSON文件提取Lightmap信息并更新到XML文件")
    
    # 添加场景名称参数
    parser.add_argument("--scene", "-s", type=str, default=DEFAULT_LIGHT_MAP_SCENE_NAME,
                        help=f"指定要处理的场景名称，默认为{DEFAULT_LIGHT_MAP_SCENE_NAME}")
    
    # 添加多场景处理参数
    parser.add_argument("--all", "-a", action="store_true",
                        help="处理所有可用的场景")
    
    # 添加多场景列表参数
    parser.add_argument("--scenes", type=str,
                        help="指定要处理的多个场景，用逗号分隔，例如: scene1,scene2,scene3")
    
    # 添加测试模式参数
    parser.add_argument("--test", "-t", action="store_true",
                        help="使用测试文件代替实际文件")
    
    # 添加输出路径参数
    parser.add_argument("--output", "-o", type=str,
                        help="指定输出文件路径，默认为<原文件名>_updated.ast")
    
    # 添加详细模式参数
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="输出详细的处理信息")
    
    # 添加列出所有场景参数
    parser.add_argument("--list-scenes", "-l", action="store_true",
                        help="列出所有可用的场景配置")
    
    # 解析参数
    args = parser.parse_args()
    
    # 处理列出所有场景
    if args.list_scenes:
        print("可用的场景配置:")
        for scene_name, config in GlobalParameter.ALL_LIGHT_MAP_DATA.items():
            print(f"  - {scene_name}:")
            for key, value in config.items():
                print(f"      {key}: {value}")
        sys.exit(0)
    
    # 确定要处理的场景列表
    scenes_to_process = []
    
    if args.all:
        # 处理所有场景
        scenes_to_process = list(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())
    elif args.scenes:
        # 处理指定的多个场景
        scenes_to_process = [scene.strip() for scene in args.scenes.split(',')]
        # 检查指定的场景是否都存在
        for scene in scenes_to_process:
            if scene not in GlobalParameter.ALL_LIGHT_MAP_DATA:
                print(f"错误: 指定的场景 '{scene}' 不存在")
                print(f"可用的场景有: {', '.join(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())}")
                sys.exit(1)
    else:
        # 处理单个场景
        if args.scene not in GlobalParameter.ALL_LIGHT_MAP_DATA:
            print(f"错误: 指定的场景 '{args.scene}' 不存在")
            print(f"可用的场景有: {', '.join(GlobalParameter.ALL_LIGHT_MAP_DATA.keys())}")
            sys.exit(1)
        scenes_to_process = [args.scene]
    
    return args, scenes_to_process

def process_scene(scene_name, use_test_files, output_path=None, verbose=False):
    """处理单个场景"""
    global CURRENT_LIGHT_MAP_SCENE_NAME, USE_TEST_FILES
    
    # 设置全局变量
    CURRENT_LIGHT_MAP_SCENE_NAME = scene_name
    USE_TEST_FILES = use_test_files
    
    # 获取场景配置
    scene_config = GlobalParameter.ALL_LIGHT_MAP_DATA[scene_name]
    
    print(f"\n正在处理场景: {scene_name}")
    print(f"场景XML文件: {scene_config['source_scene_xml_path']}")
    print(f"JSON数据文件: {scene_config['source_lightmap_json_path']}")
    print(f"Lightmap路径: {scene_config['lightmap_path_in_chaos_assets']}")
    
    # 是否使用测试文件
    if use_test_files:
        print(f"使用测试文件: {TEST_JSON_PATH}, {TEST_XML_PATH}")
    
    # 更新XML文件
    result_path = update_xml_with_json()
    
    # 如果指定了输出路径，重命名文件
    if output_path:
        # 为多场景处理添加场景名前缀
        if len(output_path) > 0:
            base_name, ext = os.path.splitext(output_path)
            scene_output = f"{base_name}_{scene_name}{ext}"
        else:
            scene_output = f"{scene_name}_updated.ast"
        
        try:
            os.rename(result_path, scene_output)
            print(f"已将输出文件重命名为: {scene_output}")
            result_path = scene_output
        except Exception as e:
            print(f"重命名输出文件失败: {str(e)}")
    
    print(f"场景 {scene_name} 处理完成! 输出文件: {result_path}")
    return result_path

def main():
    """主函数"""
    # 解析命令行参数
    args, scenes_to_process = parse_arguments()
    
    try:
        print(f"将处理 {len(scenes_to_process)} 个场景: {', '.join(scenes_to_process)}")
        
        results = []
        for scene_name in scenes_to_process:
            try:
                output_path = process_scene(scene_name, args.test, args.output, args.verbose)
                results.append((scene_name, output_path, "成功"))
            except Exception as e:
                print(f"处理场景 {scene_name} 失败: {str(e)}")
                if args.verbose:
                    import traceback
                    traceback.print_exc()
                results.append((scene_name, None, f"失败: {str(e)}"))
        
        # 打印处理结果摘要
        print("\n处理结果摘要:")
        for scene_name, output_path, status in results:
            print(f"  - {scene_name}: {status}")
            if output_path:
                print(f"    输出文件: {output_path}")
        
        # 统计成功和失败的场景数量
        success_count = sum(1 for _, _, status in results if status == "成功")
        fail_count = len(results) - success_count
        
        print(f"\n总计: {len(results)} 个场景, {success_count} 个成功, {fail_count} 个失败")
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
        import traceback
        traceback.print_exc()

def process_image(image_path, target_directory=None):
    """处理图像文件"""
    # 如果未提供目标目录,使用当前场景配置的Lightmap路径
    if target_directory is None:
        target_directory = GlobalParameter.ALL_LIGHT_MAP_DATA[CURRENT_LIGHT_MAP_SCENE_NAME]["lightmap_absolute_path"]
    
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

if __name__ == "__main__":
    main() 