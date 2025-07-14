# 混合架构灯光贴图打包工具 (NSH版本)

## 新增功能

### 自动备份检查
- 在执行 `--process-terrain` 或 `--process-staticmesh` 之前，系统会自动检查备份文件是否存在
- 如果没有备份文件，系统会自动创建一个备份文件，确保数据安全

### 统一的备份文件名参数
- `--create-backup` 参数支持直接指定备份文件名：`--create-backup my_backup.json`
- `--use-backup` 参数支持直接指定要使用的备份文件名：`--use-backup my_backup.json`
- 如果不指定文件名，两个参数都会使用默认的备份文件名（原始文件名）

## 使用方法

### 基本用法
```bash
# 处理静态网格物体（会自动检查和创建备份）
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-staticmesh

# 处理地形（会自动检查和创建备份）
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-terrain

# 同时处理静态网格和地形
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-staticmesh --process-terrain
```

### 备份管理
```bash
# 创建默认备份文件（使用原始文件名）
python hybrid_lightmap_packer_nsh.py --scene basic_level --create-backup

# 创建自定义名称的备份文件
python hybrid_lightmap_packer_nsh.py --scene basic_level --create-backup my_custom_backup.json

# 从默认备份文件恢复并处理
python hybrid_lightmap_packer_nsh.py --scene basic_level --use-backup --process-staticmesh

# 从指定备份文件恢复并处理
python hybrid_lightmap_packer_nsh.py --scene basic_level --use-backup my_custom_backup.json --process-staticmesh
```

## 安全机制

1. **自动备份检查**: 在进行任何处理操作前，系统会自动检查备份文件是否存在
2. **自动创建备份**: 如果没有备份文件，系统会自动创建一个（使用默认文件名）
3. **参数一致性**: `--create-backup` 和 `--use-backup` 都采用相同的参数格式，可以直接指定文件名
4. **冲突检查**: 防止同时使用 `--use-backup` 和 `--create-backup` 参数

## 示例场景

### 场景1: 首次处理（推荐）
```bash
# 系统会自动检查并创建备份，然后处理
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-staticmesh --process-terrain
```

### 场景2: 手动管理备份
```bash
# 先创建命名备份
python hybrid_lightmap_packer_nsh.py --scene basic_level --create-backup before_processing.json

# 然后处理（会检测到备份文件存在）
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-staticmesh --process-terrain
```

### 场景3: 从备份恢复
```bash
# 从默认备份文件恢复并重新处理
python hybrid_lightmap_packer_nsh.py --scene basic_level --use-backup --process-staticmesh --process-terrain

# 从指定备份文件恢复并重新处理
python hybrid_lightmap_packer_nsh.py --scene basic_level --use-backup before_processing.json --process-staticmesh --process-terrain
```

### 场景4: 完整的备份管理工作流
```bash
# 步骤1: 创建命名备份
python hybrid_lightmap_packer_nsh.py --scene basic_level --create-backup original_data.json

# 步骤2: 正常处理（会自动检测到备份文件存在）
python hybrid_lightmap_packer_nsh.py --scene basic_level --process-staticmesh --process-terrain

# 步骤3: 如果需要回滚，从指定备份恢复
python hybrid_lightmap_packer_nsh.py --scene basic_level --use-backup original_data.json --process-staticmesh --process-terrain
```

## 输出信息

系统会提供清晰的状态信息：

### 备份创建相关
- ✅ 发现已存在备份文件
- ⚠️ 检测到没有备份文件，正在自动创建备份
- ✓ 自动备份创建成功
- ❌ 无法创建备份文件，为了安全起见，停止处理
- 创建默认备份文件
- 创建指定备份文件: my_backup.json
- 使用自定义备份文件名: my_backup.json
- 使用默认备份文件名: test_scene.json

### 备份使用相关
- 使用默认备份文件: test_scene.json
- 使用指定备份文件: my_backup.json
- 从备份读取JSON: /path/to/backup/my_backup.json
- 错误: 指定的备份文件不存在: /path/to/backup/missing_file.json
