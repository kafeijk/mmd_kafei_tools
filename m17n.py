# -*- coding: utf-8 -*-

# 多语言翻译字典
# 考虑到源码改动程度及翻译准确程度，暂且将英文放置于Value位置
translation_dict = {
    "zh_CN": {
        # General Prompt
        ("*", "Select MMD model!"): "请选择MMD模型！",
        ("*", "Select MMD armature!"): "请选择MMD骨架！",
        ("*", "Select at least one object!"): "请选择至少一个物体！",

        # bone_operators
        ("*", "No bones selected!"): "请至少选择一根骨骼！",
        ("*", "Select bones on one side!"): "请选择单侧骨骼！",

        # change_rest_pose_operators
        ("*", "Multiple MMD models detected!"): "检测到多个MMD模型！",

        # change_tex_loc_operators
        ("*", "Texture folder name required!"): "请填写贴图文件夹名称！",
        ("*", "Invalid texture folder name!"): "贴图文件夹名称无效！",

        # organize_panel_operators
        ("*", "Armature not found!"): "未找到模型骨架！",
        ("*", "Mesh not found!"): "模型网格对象不存在！",

        # render_preview_operators
        ("*", "Color management error!"): "色彩管理参数设置时出现异常，请手动调整",
        ("*", "HDRI Map not found. Add manually. Path: {}"): "未找到环境贴图，请自行添加！参考路径：{}",
        ("*", "Unsupported output format! Use image format instead."): "输出文件格式不正确，请更改为图像类型格式！",

        # small_feature_operators
        ("*", "Affected materials: {}"): "受影响材质：{}",
        ("*", "Shader to RGB node detected! Results may be unpredictable. Click to view affected materials ↑↑↑"): "检测到Shader To RGB节点，修改结果不可预期，点击查看受影响材质↑↑↑",

        # transfer_preset_operators
        ("*", "Source model required!"): "请输入源模型！",
        ("*", "Target model required!"): "请输入目标模型！",
        ("*", "Source is not a PMX model!"): "源模型不是PMX模型！",
        ("*", "Target is not a PMX model!"): "目标模型不是PMX模型！",
        ("*", "Source and target are identical!"): "源模型与目标模型相同！",
        ("*", "ABC mesh not found!"): "未找到ABC网格对象！",
        ("*", "Face locator required!"): "请输入面部定位器对象！",
        ("*", "Face locator not parented to bone!"): "面部定位器未绑定到父级骨骼！",
        ("*", "Face object required!"): "请输入面部对象！",
        ("*", "Face vertex group required!"): "请输入面部顶点组！",
        ("*", "Cache file path required!"): "请输入缓存文件地址！",
        ("*", "Cache file not found!"): "缓存文件地址不存在！",
        ("*", "ABC cache file path required!"): "请输入ABC缓存文件地址！",
        ("*", "Armature not found in {}!"): "在{}中未找到模型骨架！",
        ("*", "Mesh not found in {}!"): "在{}中未找到网格对象！",
        ("*", "Invalid parent type for face locator! Required: Bone, Found: {}"): "面部定位器的父级类型不受支持！支持类型：骨骼（BONE），当前类型：{}",
        ("*", "UV transfer failed! Source: {} (loops:{}, faces:{}) → Target: {} (loops:{}, faces:{}). Check mesh topology."): "UV传递失败！源物体：{} (loops：{}，面数：{}) → 目标物体：{} (loops：{}，面数：{})。请检查网格拓扑。",
        ("*", "Multiple material slots transfer incomplete! Verify mesh topology & rest pose. Source: {} (faces:{}), Target: {} (faces:{}), Matched: {}"): "未能完整传递多材质，请检查网格拓扑与初始姿态。源物体：{}，面数：{}。目标物体：{}，面数：{}，匹配成功面数：{}",
        ("*", "UV copy failed during transfer! Target: {} (UV channels:{}), Source UV:{}"): "传递材质时UV复制失败！目标物体：{} (UV通道数：{})，源物体UV名称：{}",

        # transfer_vg_weight_operators
        ("*", "Select at least one mesh!"): "请选择至少一个网格物体！",
        ("*", "Source vertex group required!"): "请输入源顶点组名称！",
        ("*", "Target vertex group required!"): "请输入目标顶点组名称！",
        ("*", "Source and target vertex groups have same name!"): "源顶点组与目标顶点组名称相同！",

        # utils
        ("*", "MMD Tools plugin not enabled!"): "未启用mmd_tools插件",
        ("*", "Model directory not found!"): "模型目录不存在！",
        ("*", "Invalid root directory! Change to subfolder."): "模型目录为盘符根目录，请更换为其它目录！",
        ("*", "Invalid name suffix!"): "名称后缀不合法！"
    },
    "en_US": {
        ("Operator", "传递"): "Execute",
        ("Operator", "修改"): "Execute",
        ("Operator", "执行"): "Execute",

        # General Preset Processing panel / parameter
        ("*", "通用预设处理"): "General Preset Processing",
        ("*", "源模型"): "Source Model",
        ("*", "目标模型"): "Target Model",
        ("*", "传递方向"): "Transfer Direction",
        ("*", "材质"): "Materials",
        ("*", "UV贴图"): "UV Maps",
        ("*", "顶点组"): "Vertex Groups",
        ("*", "修改器"): "Modifiers",
        ("*", "法向"): "Normals",
        ("*", "三渲二"): "Toon Shading",
        ("*", "面部定位器"): "Face Locator",
        ("*", "自动面部识别"): "Auto Face Detection",
        ("*", "面部对象"): "Face Object",
        ("*", "面部顶点组"): "Face Vertex Group",
        ("*", "缓存文件"): "Cache File",
        ("*", "仅选中"): "Selected Only",
        ("*", "误差"): "Tolerance",
        # General Preset Processing description
        ("*", "提供预设的模型"): "Provide preset model",
        ("*", "接受预设的模型"): "Accept preset model",
        ("*", "预设传递方向"): "Preset transfer direction",
        ("*", "将PMX模型的预设传递到ABC模型上"): "Transfer the preset from a PMX model to an ABC model",
        ("*", "将PMX模型的预设传递到PMX模型上"): "Transfer the preset from a PMX model to a PMX model",
        ("*", "根据缓存文件重新设定网格序列缓存修改器参数"): "Configure Mesh Sequence Cache modifiers according to cache files",
        ("*", "关联材质，支持多材质槽"): "Link materials, supporting the linking of multiple material slots",
        ("*", "复制UV贴图"): "Copy UV Maps",
        ("*", "传递自定义顶点组及对应权重"): "Transfer custom vertex groups and corresponding weights",
        ("*", "复制修改器"): "Copy modifiers",
        ("*", "传递自定义拆边法向数据"): "Transfer custom split normals data",
        ("*", "编辑三渲二预设中的相关参数设置"): "Edit the parameter settings of the toon shading preset",
        ("*", "源物体中父级类型为骨骼的对象（该骨骼通常为“頭”），用于定位面部。默认情况下，该值会自动填充"): "An object in the source with a parent type of bone (typically '頭'), used to locate the face. By default, this value is automatically filled",
        ("*", "根据面部定位器识别面部顶点"): "Identify face vertices based on the face locator",
        ("*", "面部对象的顶点组"): "Vertex group of face object",
        ("*", "缓存文件地址"): "File path of the cache file",
        ("*", "影响范围为选中物体"): "Limit the effect to selected objects",
        ("*", "匹配过程中，顶点数、顶点位置的误差百分比。"): "Percentage of tolerance in vertex count and position during matching",

        # Tools panel
        ("*", "工具"): "Tools",
        # Color Space Change panel / parameter
        ("*", "色彩空间调整"): "Color Space Change",
        ("*", "源色彩空间"): "Source Color Space",
        ("*", "目标色彩空间"): "Target Color Space",
        ("*", "关键词"): "Keywords",
        ("*", "线性"): "Linear",
        ("*", "非彩色"): "Non-Color",
        # Color Space Change description
        ("*", "贴图名称关键词，用于搜索贴图。忽略大小写，可用英文逗号分隔开。若启用关键词搜索，则源色彩空间参数将被忽略"): "Texture name keywords for searching textures. Case insensitive, can be separated by commas. If keyword search is enabled, the source color space parameters will be ignored",
        # Object operations panel / parameter
        ("*", "物体操作"): "Object Operations",
        ("*", "内容"): "Operation",
        ("*", "名称"): "Name",
        ("*", "孤岛比例平均化"): "Average Islands Scale",
        ("*", "颜色"): "Color",
        ("*", "新建默认材质"): "Create Default Material",
        ("*", "保留首位"): "Keep First",
        ("*", "保留锁定组"): "Keep Locked Vertex Group",
        ("*", "保留当前形态"): "Keep Current Shape",
        ("*", "添加UV贴图"): "Add UV Map",
        ("*", "添加颜色属性"): "Add Color Attribute",
        ("*", "移除UV贴图"): "Remove UV Maps",
        ("*", "移除颜色属性"): "Remove Color Attributes",
        ("*", "移除材质"): "Remove Materials",
        ("*", "移除修改器"): "Remove Modifiers",
        ("*", "移除顶点组"): "Remove Vertex Groups",
        ("*", "移除形态键"): "Remove Shape Keys",
        # Object operations description
        ("*", "操作内容"): "Operation",
        ("*", "UV贴图名称"): "UV Map name",
        ("*", "颜色属性名称"): "Color attribute name",
        ("*", "移除材质后，新建默认材质"): "Create a default material after removing the material",
        ("*", "移除时，保留位于首位的内容"): "Keep the item in the first position when removing",
        ("*", "移除时，保留锁定组"): "Keep the locked vertex group when removing",
        ("*", "移除形态键时，保留当前形态，否则保留默认形态"): "Keep the current shape when removing shape keys, otherwise keep the default shape",
        # Small Features panel / parameter
        ("*", "小功能"): "Small Features",
        ("*", "用途"): "Operation",
        ("*", "创建场景控制器"): "Create Scene Controller",
        ("*", "修复Eevee显示泛蓝"): "Fix Eevee Blue Tint Display Issue",
        ("*", "修复Cycles显示模糊"): "Fix Cycles Blurry Display Issue",
        # Small Features description
        ("*", "创建一个空物体，以实现对整个场景的统一控制"): "Create an empty object to manage the entire scene",
        ("*", "将原理化BSDF节点的次表面值归零"): "Reset the subsurface value of Principled BSDF nodes to zero",

        # Model Editing panel
        ("*", "模型修改"): "Model Editing",
        # Initial Pose Adjustment panel / parameter / operation
        ("*", "初始姿态调整"): "Initial Pose Adjustment",
        ("*", "横Joint变换策略"): "Horizontal Joint Strategy",
        ("*", "强制应用修改器"): "Force Apply",
        ("*", "平均"): "Centroid",
        ("*", "跟随刚体A"): "Follow Rigid Body A",
        ("Operator", "绑定"): "Bind",
        ("Operator", "应用绑定"): "Apply Bind",
        ("Operator", "应用姿态"): "Apply Pose",
        # Initial Pose Adjustment description
        ("*", "用何种方式重新设定横Joint的变换"): "Which method to use for resetting horizontal joint transformations",
        ("*", "根据连接的刚体A与刚体B计算平均值"): "Calculate the average based on the connected Rigid Body A and Rigid Body B",
        ("*", "绑定刚体Joint，调整姿态时将会同步影响刚体Joint"): "Bind rigid body and joints. Adjusting the pose will simultaneously affect the rigid body and joints",
        ("*", "应用刚体Joint的变换并解除绑定"): "Apply the rigid body and joint transformation and unbind",
        ("*", "应用当前姿态对网格和骨架的影响"): "Apply the current pose",
        # Bone operations panel / operator
        ("*", "骨骼操作"): "Bone Operations",
        ("Operator", "物理骨骼"): "Physical Bone",
        ("Operator", "K帧骨骼"): "Keyframed Bone",
        ("Operator", "关联骨骼"): "Linked Bone",
        ("Operator", "并排骨骼"): "Ring-shaped Bone",
        ("Operator", "镜像骨骼"): "Mirror Bone",
        ("Operator", "翻转姿态"): "Flip Bone",
        ("Operator", "拓展选区"): "More",
        ("Operator", "缩减选区"): "Less",
        ("Operator", "父 +"): "Parent +",
        ("Operator", "子 +"): "Child +",
        ("Operator", "父 -"): "Parent -",
        ("Operator", "子 -"): "Child -",
        ("Operator", "清理无效刚体Joint"): "Clean Invalid Rigid Body And Joints",
        # Initial Pose Adjustment description
        ("*", "选择受物理影响的MMD骨骼"): "Select MMD bones influenced by physics",
        ("*", "选择用于K帧的MMD骨骼"): "Select MMD bones for keyframing",
        ("*", "选择以父/子关系关联到当前选中项的所有骨骼"): "Select all bones linked by parent/child connections to the current selection",
        ("*", "根据骨骼名称，选择当前选中项的环绕骨骼，例如选择裙子骨骼的一周"): "Select bones forming a ring based on the current selection and name pattern, such as a skirt bone loop",
        ("*", "翻转姿态"): "Flip bone",
        ("*", "拓展选择当前选中项的父子骨骼"): "Select those bones connected to the initial selection",
        ("*", "缩减选择当前选中项的父子骨骼"): "Deselect those bones at the boundary of each selection region",
        ("*", "拓展选择当前选中项的父骨骼"): "Select immediate parent of selected bones",
        ("*", "拓展选择当前选中项的子骨骼"): "Select immediate children of selected bones",
        ("*", "从当前选中项的父级开始缩减选择"): "Reduce selection from parent bones",
        ("*", "从当前选中项的子级开始缩减选择"): "Reduce selection from child bones",
        ("*", "清理无效的刚体和关节。如果刚体所关联的骨骼不存在，则删除该刚体及与之关联的关节；如果刚体没有关联的骨骼，则不处理"): "Clean invalid rigid body and joints. Delete the rigid body and its joint if the associated bone is missing; do nothing if there is no associated bone",
        # Weight Transfer panel / parameter
        ("*", "权重转移"): "Weight Transfer",
        ("*", "源顶点组"): "Source Vertex Group",
        ("*", "目标顶点组"): "Target Vertex Group",
        ("*", "仅选中顶点"): "Selected Vertices Only",
        # Weight Transfer description
        ("*", "源顶点组名称，必填项，如果不存在，则跳过处理"): "Source vertex group name (required). If it does not exist, skip processing",
        ("*", "目标顶点组名称，必填项，如果不存在，则会自动创建一个新的顶点组"): "Target vertex group name (required). If it does not exist, a new vertex group will be created automatically",
        ("*", "权重转移时，影响范围为编辑模式下被选中的顶点"): "During weight transfer, the affected range consists of vertices selected in Edit Mode",

        # Preprocessing and Postprocessing panel
        ("*", "预处理 / 后处理"): "Preprocessing & Postprocessing",
        # Change Texture Path panel / parameters
        ("*", "修改贴图路径"): "Texture Path Change",
        ("*", "贴图文件夹名称"): "Folder Name",
        ("*", "删除空文件夹"): "Delete Empty Folder",
        # Change Texture Path description
        ("*", "新贴图文件夹名称，区分大小写，忽略首尾空格"): "New Texture Folder Name, case-sensitive and ignoring leading/trailing spaces",
        ("*", "贴图路径修改后，是否删除模型目录下空文件夹"): "After changing the texture path, should empty folders in the model directory be deleted",
        # Remove Redundant UV Maps panel
        ("*", "移除冗余UV"): "Remove Redundant UV Maps",
        # Organize Panel panel / parameter
        ("*", "面板整理"): "Organize Panel",
        ("*", "骨骼面板"): "Bone Panel",
        ("*", "表情面板"): "Morph Panel",
        ("*", "刚体面板"): "Rigid Body Panel",
        ("*", "显示枠面板"): "Display Panel",
        ("*", "骨骼名称修复"): "Fix Bone Names",
        ("*", "表情名称修复"): "Fix Morph Names",
        ("*", "面板翻译"): "Translation",
        ("*", "覆盖"): "Overwrite",
        # Organize Panel description
        ("*", "整理骨骼面板"): "Organize bone panel",
        ("*", "优化骨骼日文名称，避免使用时出现乱码"): "Optimize the bone's Japanese name to avoid garbled characters when used",
        ("*", "整理表情面板"): "Organize morph panel",
        ("*", "整理刚体面板"): "Organize rigid body panel",
        ("*", "整理显示枠面板"): "Organize display panel",
        ("*", "为面板中的项目（骨骼、表情、显示枠）设置有限且紧凑的英文名称，以增强在MMD本体英文模式中模型操作的能力"): "Set concise and limited English names for the items in the panel (bone, morph, display) to enhance the model's operability in the English mode of MikuMikuDance",
        ("*", "如果面板项目已经存在英文名称，则覆盖原有名称"): "If the panel items already have English names, overwrite the existing names",
        # Preview Rendering panel / parameter / operator
        ("*", "渲染预览图"): "Preview Rendering",
        ("*", "类型"): "Type",
        ("*", "透视"): "Perspective",
        ("*", "正交"): "Orthographic",
        ("*", "边距"): "Margin",
        ("*", "旋转 X"): "Rotation X",
        ("*", "自动"): "Auto Follow",
        ("*", "强制居中"): "Force Center",
        ("*", "对齐角色"): "Alignment",
        ("Operator", "加载渲染预设"): "Load Render Preset",
        ("Operator", "预览"): "Preview",
        ("Operator", "渲染"): "Render",
        # Preview Rendering description
        ("*", "欧拉旋转"): "Rotation in Eulers",
        ("*", "相机旋转值跟随活动相机视角"): "Camera rotation values follow the active camera's view",
        ("*", "受隐藏部位的影响，某些角色渲染的结果可能不会居中。此选项可使角色强制居中，但会花费更多的时间"): "Due to hidden parts, the rendered result of some characters may not be centered. This option forces the character to be centered, but it may take more time",
        ("*", "尽可能使角色处于画面中心。\n（重要）该参数在角色处于初始状态时效果良好，如果出现意料外的情况请手动关闭\n开启时Y轴旋转失效，不适用于多角色共同被选择的情况"): "Attempt to keep the character at the center of the screen.\n(Important) This parameter works well when the character is in its initial state. If unexpected issues occur, please disable it manually.\nWhen enabled, Y-axis rotation will not function and it is not suitable for situations where multiple characters are selected together",
        # Batch parameter
        ("*", "批量"): "Batch",
        ("*", "模型目录"): "Model Directory",
        ("*", "阈值"): "Threshold",
        ("*", "名称后缀"): "Name Suffix",
        ("*", "检索模式"): "Search Strategy",
        ("*", "冲突时"): "Conflict Strategy",
        ("*", "最新"): "Latest",
        ("*", "全部"): "All",
        ("*", "不处理"): "Skip",
        ("*", "覆盖"): "Overwrite",
        # Batch parameter
        ("*", "是否执行批量操作"): "Whether or not to execute the batch operation",
        ("*", "模型文件所在目录（可跨越层级）"): "Directory of the model file (can span across levels)",
        ("*", "需要排除的文件大小（单位kb），忽略体积小于该值的文件"): "File size to exclude (in KB), ignore files smaller than this size",
        ("*", "在源文件名的基础上，为输出文件添加的名称后缀"): "Suffix to add to the output file name based on the source file name",
        ("*", "如果检索到多个符合条件的文件，应该如何处理"): "How to handle if multiple files matching the criteria are found",
        ("*", "获取修改日期最新的文件"): "Get the file with the latest modification date",
        ("*", "获取所有文件"): "Get all files",
        ("*", "如果目录中已存在具有指定名称后缀的同名文件，应该如何处理"): "How to handle if a file with the same name and specified suffix already exists in the directory",
        ("*", "跳过对这些文件的后续处理"): "Skip further processing of these files",
        ("*", "继续对这些文件进行后续处理，产生的新文件会覆盖原文件"): "Continue processing these files, and the new files will overwrite the original ones",

        # Other
        ("Operator", "用户文档"): "Documentation",
        ("Operator", "开源地址"): "Repository",
    },

}

translation_dict["zh_HANS"] = translation_dict["zh_CN"]
translation_dict["en_GB"] = translation_dict["en_US"]
