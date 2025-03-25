import unreal
import os
import re

# 清除所有材质中，hash值相同的材质
# 目前来说，就是名字以_origin结尾的材质，和它同名的材质的hash是一致的
# 所以，需要清除所有名字以_origin结尾的材质

def get_clean_material_name(material):
    """
    获取材质的纯名称，去除任何路径、前缀和类型信息
    """
    # 获取路径名称
    try:
        full_path = material.get_path_name()
        # 提取最后一部分作为名称
        material_name = os.path.basename(full_path)
        # 如果有点，去掉点后面的部分（类型信息）
        if '.' in material_name:
            material_name = material_name.split('.')[-1]
    except:
        # 备用方案：直接获取名称
        material_name = material.get_name()
    
    return material_name

def find_origin_materials_and_replacements():
    """
    查找所有名字以_origin结尾的材质，同时寻找不带_origin和他同名的材质。
    如果找到匹配，先输出会用什么材质替换什么材质的引用。
    """
    unreal.log(">>> 开始查找以_origin结尾的材质和可能的替换材质...")
    
    # 获取所有材质
    try:
        # 方法1：使用EditorAssetLibrary直接获取所有资产
        unreal.log("尝试获取项目中的所有资产...")
        asset_lib = unreal.EditorAssetLibrary()
        all_assets = asset_lib.list_assets("/Game/", recursive=True, include_folder=False)
        unreal.log(f"找到总计 {len(all_assets)} 个资产")
        
        # 过滤材质类型并记录名称
        material_assets = []
        material_names = []  # 用于调试
        
        for asset_path in all_assets:
            try:
                asset = unreal.load_asset(asset_path)
                if asset is None:
                    continue
                
                # 检查是否为材质资产
                class_name = asset.get_class().get_name()
                if class_name == "Material" or class_name == "MaterialInstanceConstant":
                    material_name = get_clean_material_name(asset)
                    material_assets.append((asset, material_name))
                    material_names.append(material_name)
            except Exception as e:
                unreal.log_warning(f"无法加载资产 {asset_path}: {str(e)}")
        
        unreal.log(f"找到 {len(material_assets)} 个材质资产")
        
        # 调试：输出一些材质名称示例
        sample_count = min(10, len(material_assets))
        if sample_count > 0:
            unreal.log("材质名称示例:")
            for i in range(sample_count):
                asset, name = material_assets[i]
                unreal.log(f"  {name} (路径: {asset.get_path_name()})")
        
        # 查找以_origin结尾的材质
        origin_materials = []
        origin_names = set()
        for material, material_name in material_assets:
            if material_name.endswith("_origin"):
                origin_materials.append((material, material_name))
                origin_names.add(material_name)
        
        unreal.log(f"找到 {len(origin_materials)} 个以_origin结尾的材质")
        
        # 查找不带_origin的对应材质
        base_materials = {}
        for material, material_name in material_assets:
            # 跳过以_origin结尾的材质
            if material_name.endswith("_origin"):
                continue
                
            # 检查是否有对应的_origin材质
            origin_name = material_name + "_origin"
            if origin_name in origin_names:
                base_materials[material_name] = material
        
        # 构建替换对
        replacement_pairs = []
        
        for origin_material, origin_name in origin_materials:
            # 获取基础名称（去掉_origin）
            base_name = origin_name[:-7]
            
            if base_name in base_materials:
                # 找到对应的基础材质
                base_material = base_materials[base_name]
                
                replacement_pairs.append({
                    "base_name": base_name,
                    "origin": origin_material,
                    "regular": base_material
                })
        
        # 输出替换计划
        if len(replacement_pairs) == 0:
            unreal.log("\n未找到任何可替换的材质对")
            
            # 调试信息：输出所有_origin材质和所有基础材质
            unreal.log("\n以_origin结尾的材质:")
            for _, origin_name in origin_materials:
                unreal.log(f"  {origin_name}")
                
            unreal.log("\n可能的替换基础材质:")
            for base_name in base_materials.keys():
                unreal.log(f"  {base_name}")
        else:
            unreal.log(f"\n找到 {len(replacement_pairs)} 对可替换的材质引用:")
            
            for pair in replacement_pairs:
                origin_material = pair["origin"]
                regular_material = pair["regular"]
                
                origin_path = origin_material.get_path_name()
                regular_path = regular_material.get_path_name()
                
                unreal.log(f"将替换引用: {origin_path}")
                unreal.log(f"替换为引用: {regular_path}")
                unreal.log("---")
            
            unreal.log("\n*** 注意：此操作仅替换材质引用，不会删除任何原始材质 ***")
            unreal.log("*** 请仔细检查上述替换计划，确认无误后再执行替换操作 ***")
            unreal.log("\n如需执行替换，请调用replace_origin_materials()函数")
        
        return replacement_pairs
    
    except Exception as e:
        unreal.log_error(f"执行过程中出错: {str(e)}")
        import traceback
        unreal.log_error(traceback.format_exc())
        return []

def check_scene_materials():
    """
    扫描场景中的所有材质引用，生成报告
    这个函数用于调试，帮助找出场景中使用的所有材质
    """
    unreal.log(">>> 开始扫描场景中的所有材质引用...")
    
    try:
        # 获取场景中的所有Actor
        editor_level_lib = unreal.EditorLevelLibrary()
        all_actors = editor_level_lib.get_all_level_actors()
        unreal.log(f"场景中共有 {len(all_actors)} 个Actor")
        
        # 用于记录所有发现的材质
        all_materials = {}
        origin_materials = {}
        total_material_count = 0
        
        # 设置计数器，用于显示进度
        actor_count = len(all_actors)
        progress_step = max(1, actor_count // 20)
        
        # 遍历所有Actor，搜集材质引用
        for i, actor in enumerate(all_actors):
            # 显示进度
            if i % progress_step == 0:
                progress = int((i / actor_count) * 100)
                unreal.log(f"处理进度: {progress}% ({i}/{actor_count})")
            
            try:
                # 获取所有组件
                components = actor.get_components_by_class(unreal.PrimitiveComponent)
                
                for component in components:
                    comp_name = component.get_name()
                    
                    # 检查是否具有材质功能
                    has_materials_method = hasattr(component, "get_materials")
                    has_material_method = hasattr(component, "get_material")
                    
                    if not (has_materials_method and has_material_method):
                        continue
                    
                    # 获取组件材质数量
                    num_materials = 0
                    try:
                        materials = component.get_materials()
                        if materials:
                            num_materials = len(materials)
                    except Exception as e:
                        continue
                    
                    if num_materials == 0:
                        continue
                    
                    # 检查每个材质
                    for idx in range(num_materials):
                        try:
                            current_material = component.get_material(idx)
                            if current_material is None:
                                continue
                            
                            material_path = current_material.get_path_name()
                            material_name = get_clean_material_name(current_material)
                            
                            # 记录材质使用情况
                            if material_path not in all_materials:
                                all_materials[material_path] = {
                                    "name": material_name,
                                    "count": 0,
                                    "actors": set()
                                }
                            
                            all_materials[material_path]["count"] += 1
                            all_materials[material_path]["actors"].add(actor.get_name())
                            total_material_count += 1
                            
                            # 特别记录_origin材质
                            if material_name.endswith("_origin"):
                                if material_path not in origin_materials:
                                    origin_materials[material_path] = {
                                        "name": material_name,
                                        "count": 0,
                                        "actors": set()
                                    }
                                
                                origin_materials[material_path]["count"] += 1
                                origin_materials[material_path]["actors"].add(actor.get_name())
                        
                        except Exception as e:
                            unreal.log_warning(f"处理组件 '{comp_name}' 的材质 {idx} 时出错: {str(e)}")
            
            except Exception as e:
                unreal.log_warning(f"处理Actor '{actor.get_name()}' 时出错: {str(e)}")
        
        # 输出报告
        unreal.log(f"\n报告：场景中总共有 {len(all_materials)} 种不同材质，使用了 {total_material_count} 次")
        
        # 列出所有以_origin结尾的材质
        if len(origin_materials) > 0:
            unreal.log(f"\n在场景中找到 {len(origin_materials)} 种_origin材质:")
            
            for mat_path, info in origin_materials.items():
                actors_str = ", ".join(list(info["actors"])[:5])
                if len(info["actors"]) > 5:
                    actors_str += f"... 等 {len(info['actors'])} 个Actor"
                
                unreal.log(f"  材质: {mat_path}")
                unreal.log(f"    使用次数: {info['count']}")
                unreal.log(f"    使用者: {actors_str}")
                unreal.log("    ---")
        else:
            unreal.log("\n场景中没有找到任何以_origin结尾的材质")
        
        # 列出使用最多的前10种材质
        unreal.log("\n使用最多的前10种材质:")
        sorted_materials = sorted(all_materials.items(), key=lambda x: x[1]["count"], reverse=True)
        
        for i, (mat_path, info) in enumerate(sorted_materials[:10]):
            actors_str = ", ".join(list(info["actors"])[:3])
            if len(info["actors"]) > 3:
                actors_str += f"... 等 {len(info['actors'])} 个Actor"
            
            unreal.log(f"  {i+1}. 材质: {mat_path}")
            unreal.log(f"     使用次数: {info['count']}")
            unreal.log(f"     使用者示例: {actors_str}")
        
        return origin_materials
    
    except Exception as e:
        unreal.log_error(f"扫描材质时出错: {str(e)}")
        import traceback
        unreal.log_error(traceback.format_exc())
        return {}

def replace_origin_materials(replacement_pairs=None, save_changes=True, force_replace=False):
    """
    执行实际的材质引用替换操作。
    所有引用_origin材质的对象都会改为引用对应的非_origin材质。
    不会删除任何原始材质。
    
    Args:
        replacement_pairs: 材质替换对列表。如果为None，将自动调用查找函数。
        save_changes: 是否保存更改到关卡。默认为True。
        force_replace: 是否强制替换，即使找不到匹配的材质引用也尝试替换所有材质。默认为False。
    """
    if replacement_pairs is None:
        replacement_pairs = find_origin_materials_and_replacements()
        
    if len(replacement_pairs) == 0:
        unreal.log("没有找到可替换的材质对，操作取消")
        return []
    
    unreal.log(f">>> 开始执行 {len(replacement_pairs)} 对材质引用的替换操作...")
    
    # 如果启用了强制替换模式，先进行场景材质扫描
    if force_replace:
        unreal.log("强制替换模式已启用，先检查场景中的材质...")
        scene_materials = check_scene_materials()
        if len(scene_materials) == 0:
            unreal.log("场景中没有找到任何_origin材质，但将继续执行替换...")
    
    replacement_count = 0
    total_ref_count = 0
    material_paths_replaced = set()  # 记录哪些材质路径已被替换
    modified_actors = set()
    
    # 创建路径映射和对象映射，用于快速查找
    material_map = {}          # 对象到对象映射
    material_path_map = {}     # 路径到对象映射
    material_name_map = {}     # 名称到对象映射
    regex_patterns = []        # 正则表达式模式，用于更灵活的匹配
    
    for pair in replacement_pairs:
        origin_material = pair["origin"]
        regular_material = pair["regular"]
        base_name = pair["base_name"]
        
        # 记录材质对象映射
        material_map[origin_material] = regular_material
        
        # 记录路径映射
        origin_path = origin_material.get_path_name()
        material_path_map[origin_path] = regular_material
        
        # 记录名称映射（去掉路径和类型）
        origin_name = get_clean_material_name(origin_material)
        material_name_map[origin_name] = regular_material
        
        # 创建正则表达式模式匹配_origin结尾的材质，不区分大小写
        pattern = re.compile(r'{}(_origin)$'.format(re.escape(base_name)), re.IGNORECASE)
        regex_patterns.append((pattern, regular_material))
        
        # 调试输出
        unreal.log(f"材质映射: {origin_path} -> {regular_material.get_path_name()}")
    
    # 获取场景中的所有Actor
    unreal.log("\n开始查找场景中使用到这些材质的对象...")
    editor_level_lib = unreal.EditorLevelLibrary()
    all_actors = editor_level_lib.get_all_level_actors()
    unreal.log(f"场景中共有 {len(all_actors)} 个Actor")
    
    # 设置计数器，用于显示进度
    actor_count = len(all_actors)
    progress_step = max(1, actor_count // 20)  # 大约每5%更新一次进度
    
    # 遍历所有Actor，查找并替换材质引用
    for i, actor in enumerate(all_actors):
        # 显示进度
        if i % progress_step == 0:
            progress = int((i / actor_count) * 100)
            unreal.log(f"处理进度: {progress}% ({i}/{actor_count})")
            
        try:
            actor_modified = False
            actor_name = actor.get_name()
            
            # 获取所有组件
            # 1. 首先尝试获取所有材质组件
            components = actor.get_components_by_class(unreal.PrimitiveComponent)
            
            for component in components:
                comp_name = component.get_name()
                
                # 检查是否具有材质功能
                has_materials_method = hasattr(component, "get_materials")
                has_material_method = hasattr(component, "get_material")
                has_set_material_method = hasattr(component, "set_material")
                
                if not (has_materials_method and has_material_method and has_set_material_method):
                    continue
                
                # 获取组件材质数量
                num_materials = 0
                try:
                    materials = component.get_materials()
                    if materials:
                        num_materials = len(materials)
                except Exception as e:
                    unreal.log_warning(f"获取组件 '{comp_name}' 的材质列表时出错: {str(e)}")
                    continue
                
                if num_materials == 0:
                    continue
                
                # 检查每个材质槽位
                for idx in range(num_materials):
                    try:
                        current_material = component.get_material(idx)
                        if current_material is None:
                            continue
                        
                        # 尝试各种方式匹配材质：对象匹配、路径匹配、名称匹配、正则匹配
                        replacement = None
                        match_type = None
                        
                        # 1. 直接对象匹配
                        if current_material in material_map:
                            replacement = material_map[current_material]
                            match_type = "对象匹配"
                        else:
                            # 2. 路径匹配
                            try:
                                current_path = current_material.get_path_name()
                                if current_path in material_path_map:
                                    replacement = material_path_map[current_path]
                                    match_type = "路径匹配"
                                else:
                                    # 3. 名称匹配
                                    current_name = get_clean_material_name(current_material)
                                    if current_name.endswith("_origin"):
                                        base_name = current_name[:-7]  # 移除"_origin"
                                        
                                        # 查找对应的基础材质
                                        for pair in replacement_pairs:
                                            if pair["base_name"] == base_name:
                                                replacement = pair["regular"]
                                                match_type = "名称匹配"
                                                break
                                        
                                        # 4. 正则表达式匹配
                                        if replacement is None:
                                            for pattern, mat in regex_patterns:
                                                if pattern.search(current_name):
                                                    replacement = mat
                                                    match_type = "正则匹配"
                                                    break
                            except Exception as e:
                                unreal.log_warning(f"材质 {idx} 路径处理时出错: {str(e)}")
                                continue
                        
                        # 如果强制替换模式，则尝试模糊匹配
                        if replacement is None and force_replace:
                            try:
                                current_name = get_clean_material_name(current_material)
                                for pair in replacement_pairs:
                                    # 检查名称是否包含基础名称，且以_origin结尾
                                    if pair["base_name"] in current_name and current_name.endswith("_origin"):
                                        replacement = pair["regular"]
                                        match_type = "强制匹配"
                                        break
                            except Exception as e:
                                pass
                        
                        # 如果找到了替换材质，执行替换
                        if replacement:
                            try:
                                origin_path = current_material.get_path_name()
                                regular_path = replacement.get_path_name()
                                
                                # 记录哪些材质路径被替换
                                material_paths_replaced.add(origin_path)
                                
                                # 执行替换
                                component.set_material(idx, replacement)
                                unreal.log(f"在Actor '{actor_name}' 的组件 '{comp_name}' 索引 {idx} 处替换了材质")
                                unreal.log(f"  从: {origin_path}")
                                unreal.log(f"  到: {regular_path}")
                                unreal.log(f"  匹配方式: {match_type}")
                                
                                actor_modified = True
                                total_ref_count += 1
                            except Exception as e:
                                unreal.log_warning(f"替换材质时出错: {str(e)}")
                    
                    except Exception as e:
                        unreal.log_warning(f"处理组件 '{comp_name}' 的材质槽 {idx} 时出错: {str(e)}")
            
            # 处理特殊情况：检查Actor是否有直接的材质属性
            if hasattr(actor, "get_editor_property") and hasattr(actor, "set_editor_property"):
                try:
                    # 获取所有属性
                    for prop_name in ["Material", "BaseMaterial", "OriginalMaterial"]:
                        try:
                            if hasattr(actor, prop_name):
                                material_prop = actor.get_editor_property(prop_name)
                                if material_prop and material_prop in material_map:
                                    replacement = material_map[material_prop]
                                    actor.set_editor_property(prop_name, replacement)
                                    unreal.log(f"在Actor '{actor_name}' 中替换了属性 '{prop_name}'")
                                    actor_modified = True
                                    total_ref_count += 1
                        except:
                            pass
                except Exception as e:
                    unreal.log_warning(f"处理Actor '{actor_name}' 的材质属性时出错: {str(e)}")
            
            # 如果Actor被修改，则标记为脏，并添加到修改列表
            if actor_modified:
                modified_actors.add(actor)
                # 标记Actor为脏
                try:
                    if hasattr(actor, "mark_package_dirty"):
                        actor.mark_package_dirty()
                    # 标记为待保存
                    if hasattr(actor, "mark_dirty"):
                        actor.mark_dirty()
                except Exception as e:
                    unreal.log_warning(f"标记Actor '{actor_name}' 为脏时出错: {str(e)}")
                
                replacement_count += 1
        
        except Exception as e:
            unreal.log_warning(f"处理Actor '{actor.get_name()}' 时出错: {str(e)}")
    
    # 输出统计信息
    unreal.log(f"\n找到并替换了 {replacement_count} 个Actor上的材质引用，共 {total_ref_count} 处引用")
    unreal.log(f"替换了 {len(material_paths_replaced)} 种不同的材质路径")
    
    # 如果没有找到任何引用，提供一些调试信息
    if total_ref_count == 0:
        unreal.log("\n没有找到任何需要替换的材质引用。可能的原因:")
        unreal.log("1. 这些材质在当前场景中没有被使用")
        unreal.log("2. 材质可能以不同方式引用，当前检测方法无法识别")
        unreal.log("3. 之前的替换操作已经成功完成，没有剩余的_origin材质引用")
        unreal.log("\n建议使用以下命令扫描场景中的所有材质:")
        unreal.log("import test")
        unreal.log("test.check_scene_materials()")
    
    # 保存更改 - 使用简化的保存方法
    if save_changes and total_ref_count > 0:
        unreal.log("\n正在保存更改到关卡...")
        try:
            # 调用Editor Command - 这是最可靠的保存方法
            command_result = unreal.PythonBridge.exec_py_command("import unreal; unreal.EditorLevelLibrary.save_current_level()")
            if command_result:
                unreal.log("使用命令执行保存关卡成功")
            else:
                # 尝试直接调用保存功能
                try:
                    unreal.EditorLevelLibrary.save_current_level()
                    unreal.log("直接调用保存关卡函数成功")
                except Exception as e:
                    unreal.log_warning(f"直接保存关卡失败: {str(e)}")
                    
                    # 最后尝试使用编辑器命令
                    try:
                        unreal.EditorUtilityLibrary.save_loaded_asset(unreal.EditorLevelLibrary.get_editor_world())
                        unreal.log("使用EditorUtilityLibrary保存关卡成功")
                    except Exception as e2:
                        unreal.log_error(f"所有保存方法都失败: {str(e2)}")
            
            # 使用菜单执行保存所有操作
            try:
                unreal.log("尝试执行保存所有操作...")
                command_result = unreal.PythonBridge.exec_py_command("import unreal; unreal.EditorLevelLibrary.save_all_dirty_levels()")
                if command_result:
                    unreal.log("保存所有已修改关卡成功")
            except Exception as e:
                unreal.log_warning(f"保存所有操作失败: {str(e)}")
            
            unreal.log("*** 重要提示：请在编辑器中手动保存关卡 (Ctrl+S) 以确保所有更改都已保存 ***")
        except Exception as e:
            unreal.log_error(f"保存过程中出错: {str(e)}")
            unreal.log("*** 请在编辑器中手动保存关卡 (Ctrl+S) ***")
    
    # 强调需要手动保存
    unreal.log("\n*** 重要提示 ***")
    unreal.log("由于自动保存可能不可靠，请在编辑器中使用Ctrl+S手动保存关卡，确保所有更改都被保存")
    
    # 刷新视口以显示更改
    try:
        if hasattr(unreal.EditorLevelLibrary, "refresh_all_browsers"):
            unreal.EditorLevelLibrary.refresh_all_browsers()
        else:
            # 尝试其他方法刷新
            try:
                unreal.PythonBridge.exec_py_command("import unreal; unreal.EditorLevelLibrary.refresh_all_browsers()")
            except:
                pass
    except Exception as e:
        unreal.log_warning(f"刷新视口时出错: {str(e)}")
    
    unreal.log(f">>> 完成! 成功在 {replacement_count} 个Actor上替换了 {total_ref_count} 处材质引用")
    if save_changes and total_ref_count > 0:
        unreal.log("尝试自动保存更改，但请确保手动保存关卡 (Ctrl+S)")
    elif total_ref_count == 0:
        unreal.log("未找到任何需要替换的材质引用")
    else:
        unreal.log("!!!警告!!! 更改尚未保存。要保存更改，请使用Ctrl+S手动保存关卡")
    
    return replacement_pairs

def main():
    unreal.log(">>> 开始查找以_origin结尾的材质和对应的替换材质...")
    replacement_pairs = find_origin_materials_and_replacements()
    
    # 提示用户如何执行替换操作
    if len(replacement_pairs) > 0:
        unreal.log("\n要执行替换，请在Python控制台中运行:")
        unreal.log("import test")
        unreal.log("test.replace_origin_materials(save_changes=True)")
        unreal.log("\n如需强制替换模式，请运行:")
        unreal.log("test.replace_origin_materials(save_changes=True, force_replace=True)")
        unreal.log("\n如需检查场景中的所有材质引用，请运行:")
        unreal.log("test.check_scene_materials()")
        unreal.log("\n注意：执行替换后，请务必在编辑器中手动保存关卡 (Ctrl+S)")
    
    # 如果想直接执行替换，取消下面这行的注释
    replace_origin_materials(replacement_pairs, save_changes=True)

if __name__ == "__main__":
    main()

unreal.log("完成")