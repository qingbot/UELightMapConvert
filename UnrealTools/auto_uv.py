import unreal

# 半自动重设unreal的uv1的脚本，将static_mesh的generate_lightmap_uv设置为false
# 然后就可以手点，一个个去重新生成uv1了

def update_static_mesh_lightmap_uv(folder_path):
    asset_paths = unreal.EditorAssetLibrary.list_assets(folder_path, recursive=True)
    
    # 获取StaticMeshEditorSubsystem实例
    static_mesh_editor_subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    
    for asset_path in asset_paths:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        # 只处理 StaticMesh 类型资源
        if isinstance(asset, unreal.StaticMesh):
            try:
                if True:
                    # 如果为 True，则设置为 False
                    static_mesh_editor_subsystem.set_generate_lightmap_uv(asset, False)
                    asset.post_edit_change()  # 通知编辑器属性已更改
                    asset.mark_package_dirty()  # 标记资源已修改
                    # 保存修改后的资源
                    unreal.EditorAssetLibrary.save_asset(asset_path)
                    unreal.log("已更新: " + asset_path)
            except Exception as e:
                unreal.log_warning("无法更新 {}: {}".format(asset_path, e))
    unreal.log("所有 StaticMesh 已处理。")

if __name__ == '__main__':
    # 将此处的路径替换为实际的资源文件夹路径（例如："/Game/MyStaticMeshes"）
    folder = "/Game/Carcassonne_Remake"
    # 列举所有子系统
    
    # 更新StaticMesh的LightmapUV设置
    update_static_mesh_lightmap_uv(folder)
    
