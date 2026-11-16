import re

from collections import OrderedDict

# -------------------------------------------------------------
# 正则校验
# -------------------------------------------------------------
ABC_NAME_PATTERN = re.compile(r'xform_(\d+)_material_(\d+)')
PMX_NAME_PATTERN = re.compile(r'(?P<prefix>[0-9A-Z]{3}_)(?P<name>.*?)(?P<suffix>\.\d{3})?$')
RIGID_BODY_PREFIX_REGEXP = re.compile(r'(?P<prefix>[0-9A-Z]{3}_)(?P<name>.*)')
CONVERT_NAME_TO_L_REGEXP = re.compile('^(.*)左(.*)$')
CONVERT_NAME_TO_R_REGEXP = re.compile('^(.*)右(.*)$')
# 导入pmx生成的txt文件pattern
TXT_INFO_PATTERN = re.compile(r'(.*)(_e(\.\d{3})?)$')

# -------------------------------------------------------------
# 文件导入导出
# -------------------------------------------------------------
# 文件名非法字符
INVALID_CHARS = '<>:"/\\|?*'
# 最大重试次数
MAX_RETRIES = 5
# 批量处理时连续失败达到该数量即停止，并提示可能是模型或 mmd_tools 版本问题
MAX_CONSECUTIVE_FAILURES = 3
# 批处理 modal 定时器间隔（秒）
TIMER_INTERVAL = 0.01
# 批处理任务标识，供面板读取对应进度
BATCH_TASK_PRE_POST_PROCESSING = "pre_post_processing"
BATCH_TASK_RENDER_PREVIEW = "render_preview"
BATCH_TASK_RENDER_THREE_VIEW = "render_three_view"
# 临时集合名称
TMP_COLLECTION_NAME = "KAFEI临时集合"
# 默认精度
PRECISION = 0.0001
# 预设传递配对误差：顶点数相对差与 27 邻域命中率阈值（仅 PMX → PMX 使用，不对外提供）
PAIRING_TOLERANCE = 0.2
# 预设传递：Blender 重名后缀（.001 等）与 ID 名称最大字节数
DUPLICATE_SUFFIX_PATTERN = re.compile(r'^(?P<base>.+)\.(\d{3,})$')
MAX_ID_NAME_LENGTH = 63
# PMX(MMD) 与 Blender 的单位换算倍数：导入按 0.08 缩放，导出按 1/0.08 缩放
PMX_IMPORT_SCALE = 0.08
PMX_EXPORT_SCALE = 1 / PMX_IMPORT_SCALE
# 不在预设排序表中的元素统一排到最后
UNKNOWN_ORDER = float("inf")
# 三点照明的角度（度）与面光源尺寸
KEY_LIGHT_ANGLE = 30
FILL_LIGHT_ANGLE = 60
LIGHT_ROTATION_X = 75
LIGHT_HEIGHT_ANGLE = 15
LIGHT_SIZE = 1
# 插件生成灯光的标识、记录的模型 root 属性与三盏灯的角色标识
LIGHT_MARKER = "Tri-Lighting"
LIGHT_ROOT_PROPERTY = "mmd_kafei_tools_light_root"
LIGHT_ROLES = ("KeyLight", "FillLight", "BackLight")
# 兼容旧版本的灯光角色标识
LIGHT_ROLE_ALIASES = {"MainLight": "KeyLight"}
# 灯光控制器标识与灯光链接排除集合名称
LIGHT_CONTROLLER_ATTR = "LightRoot"
LIGHT_EXCLUDE_COLLECTION = "灯光排除"
# 三点照明颜色预设：#RRGGBB（主光, 辅光, 背光）
LIGHT_COLOR_PRESETS = {
    "DEFAULT": ("#FFD1BC", "#DAEAFF", "#BCDAFF"),
    "RED_BLUE": ("#FF5959", "#BCC4FF", "#5979FF"),
    "BLUE_PURPLE": ("#5979FF", "#E1BCFF", "#C459FF"),
}

# 相机 Z 位移系数：按角色高度约 1 的假设，相机跟随的升降量取骨骼 Z 位移的一半
CAMERA_Z_FACTOR = 0.5
# 文件类型与扩展名的map，value相同可能会造成一些问题但几率太低这里不考虑
IMG_TYPE_EXT_MAP = {
    "BMP": ".bmp",
    "IRIS": ".rgb",
    "PNG": ".png",
    "JPEG": ".jpg",
    "JPEG2000": ".jp2",
    "TARGA": ".tga",
    "TARGA_RAW": ".tga",
    "CINEON": ".cin",
    "DPX": ".dpx",
    "OPEN_EXR_MULTILAYER": ".exr",
    "OPEN_EXR": ".exr",
    "HDR": ".hdr",
    "TIFF": ".tif",
    "WEBP": ".webp"
}

# -------------------------------------------------------------
# 输出分辨率预设
# -------------------------------------------------------------
# 标识 -> (界面显示名, 宽, 高)，字典顺序即界面展示顺序
RESOLUTION_PRESETS = OrderedDict({
    "1080P": ("1080p", 1920, 1080),
    "2K": ("2K", 2560, 1440),
    "4K": ("4K", 3840, 2160),
    "360P": ("360p", 640, 360),
    "480P": ("480p", 854, 480),
    "540P": ("540p", 960, 540),
    "720P": ("720p", 1280, 720),
    "8K": ("8K", 7680, 4320),
    "720_4_3": ("960×720(4:3)", 960, 720),
    "1080_4_3": ("1440×1080(4:3)", 1440, 1080),
    "1440_4_3": ("1920×1440(4:3)", 1920, 1440),
    "2160_4_3": ("2880×2160(4:3)", 2880, 2160),
})

# -------------------------------------------------------------
# 追加次标准骨骼 骨骼面板顺序预设
# -------------------------------------------------------------
# 次标准骨骼名称，共41个
SSB_NAMES = [
    '右腕捩', '右腕捩1', '右腕捩2', '右腕捩3', '左腕捩', '左腕捩1', '左腕捩2', '左腕捩3',
    '右手捩', '右手捩1', '右手捩2', '右手捩3', '左手捩', '左手捩1', '左手捩2', '左手捩3',
    '上半身2',
    '腰', '腰キャンセル右', '腰キャンセル左',
    '右足IK親', '左足IK親',
    '右ダミー', '左ダミー',
    '右肩P', '右肩C', '左肩P', '左肩C',
    '右親指０', '左親指０',
    '操作中心', '全ての親', 'グルーブ',
    '右足D', '右ひざD', '右足首D', '右足先EX', '左足D', '左ひざD', '左足首D', '左足先EX'
]
# 次标准骨骼名称（不含额外创建内容）
SSB_BASE_NAMES = [
    '右腕捩', '左腕捩', '右手捩', '左手捩',
    '上半身2', '腰',
    '右足IK親', '左足IK親',
    '右ダミー', '左ダミー',
    '右肩P', '左肩P',
    '右親指０', '左親指０',
    '操作中心', '全ての親', 'グルーブ',
    '右足先EX', '左足先EX'
]
# ssb实际创建顺序（首部）（非用户界面展示顺序）
SSB_ORDER_TOP_LIST = ["操作中心", "全ての親", "センター", "グルーブ", "腰"]
# ssb实际创建顺序（中部）（非用户界面展示顺序）
SSB_ORDER_MAP = OrderedDict({
    "右腕": ("右腕", "右腕捩", "右腕捩1", "右腕捩2", "右腕捩3"),
    "左腕": ("左腕", "左腕捩", "左腕捩1", "左腕捩2", "左腕捩3"),
    "右ひじ": ("右ひじ", "右手捩", "右手捩1", "右手捩2", "右手捩3"),
    "左ひじ": ("左ひじ", "左手捩", "左手捩1", "左手捩2", "左手捩3"),
    "上半身": ("上半身", "上半身2"),
    "右足": ("腰キャンセル右", "右足"),
    "左足": ("腰キャンセル左", "左足"),
    "右足ＩＫ": ("右足IK親", "右足ＩＫ"),
    "左足ＩＫ": ("左足IK親", "左足ＩＫ"),
    "右手首": ("右手首", "右ダミー"),
    "左手首": ("左手首", "左ダミー"),
    "右肩": ("右肩P", "右肩", "右肩C"),
    "左肩": ("左肩P", "左肩", "左肩C"),
    "右親指１": ("右親指０", "右親指１"),
    "左親指１": ("左親指０", "左親指１")
})
# ssb实际创建顺序（尾部）（非用户界面展示顺序）
SSB_ORDER_BOTTOM_LIST = ["右足D", "右ひざD", "右足首D", "右足先EX", "左足D", "左ひざD", "左足首D", "左足先EX"]
# 需隐藏的ssb名称
SSB_HIDE_LIST = ["右腕捩1", "右腕捩2", "右腕捩3", "左腕捩1", "左腕捩2", "左腕捩3",
                 "右手捩1", "右手捩2", "右手捩3", "左手捩1", "左手捩2", "左手捩3",
                 "腰キャンセル右", "腰キャンセル左",
                 "右肩C", "左肩C",
                 "右足D", "右ひざD", "右足首D", "左足D", "左ひざD", "左足首D"]
# 临时骨骼名称
KAFEI_TMP_BONE_NAME = "KAFEI_TMP_BONE"

# -------------------------------------------------------------
# 整理面板
# -------------------------------------------------------------
# 骨骼面板元素顺序
BONE_PANEL_ORDERS = [

    '操作中心', '全ての親', 'センター', 'グルーブ',
    '腰', '下半身', '左足IK親', '左足ＩＫ', '左つま先ＩＫ', '右足IK親', '右足ＩＫ', '右つま先ＩＫ',
    '上半身', '上半身2', '首', '頭', '舌１', '舌２', '舌３', '齿上', '齿下',
    '両目', '左目', '左目先', '左目戻', '右目', '右目先', '右目戻',
    'おっぱい調整', '左胸上', '左胸上2', '左胸先', '左胸下', '左胸下先', '右胸上', '右胸上2', '右胸先', '右胸下',
    '右胸下先',
    '左肩P', '左肩', '左肩C', '左腕', '左腕捩', '左腕捩1', '左腕捩2', '左腕捩3', '左ひじ',
    '左ひじ補助', '+左ひじ補助', '左手捩', '左手捩1', '左手捩2', '左手捩3', '左手首', '左ダミー', '左手先',
    '左親指０', '左親指１', '左親指２', '左親指先',
    '左人指１', '左人指２', '左人指３', '左人指先',
    '左中指１', '左中指２', '左中指３', '左中指先',
    '左薬指１', '左薬指２', '左薬指３', '左薬指先',
    '左小指１', '左小指２', '左小指３', '左小指先',
    '右肩P', '右肩', '右肩C', '右腕', '右腕捩', '右腕捩1', '右腕捩2', '右腕捩3', '右ひじ',
    '右ひじ補助', '+右ひじ補助', '右手捩', '右手捩1', '右手捩2', '右手捩3', '右手首', '右ダミー', '右手先',
    '右親指０', '右親指１', '右親指２', '右親指先',
    '右人指１', '右人指２', '右人指３', '右人指先',
    '右中指１', '右中指２', '右中指３', '右中指先',
    '右薬指１', '右薬指２', '右薬指３', '右薬指先',
    '右小指１', '右小指２', '右小指３', '右小指先',

    '腰キャンセル左', '左足', '左ひざ', '左足首', '左つま先',
    '腰キャンセル右', '右足', '右ひざ', '右足首', '右つま先',
    '左足D', '左ひざD', '左足首D', '左足先EX',
    '右足D', '右ひざD', '右足首D', '右足先EX',
    '足_親指1.L', '足_親指2.L', '足_人差指1.L', '足_人差指2.L', '足_中指1.L', '足_中指2.L',
    '足_薬指1.L', '足_薬指2.L', '足_小指1.L', '足_小指2.L',
    '足_親指1.R', '足_親指2.R', '足_人差指1.R', '足_人差指2.R', '足_中指1.R', '足_中指2.R',
    '足_薬指1.R', '足_薬指2.R', '足_小指1.R', '足_小指2.R'
]


class Item:
    def __init__(self, jp_name, eng_name, display_panel):
        self.jp_name = jp_name
        self.eng_name = eng_name
        self.display_panel = display_panel


def get_common_items():
    # 常用的骨骼（不限类型）按照预设分组 参考 https://note.com/mamepika/n/n9b8a6d55f0bb
    # 剩余的受物理影响的骨骼自动放到"物理"显示枠中
    # 剩余的其它的骨骼自动移动到"その他"中
    # 这里的英文名称遵循驼峰式命名规范。为了确保能够在MMD的左侧栏中显示得下，尽量使用简写。
    # todo 暂时采用硬编码的方式，之后考虑如何让用户方便的修改预设值
    return [
        Item("操作中心", "ViewCnt", 'Root'),

        Item("全ての親", "Root", 'センター'),
        Item("センター", "Center", "センター"),
        Item("グルーブ", "Groove", 'センター'),

        Item("左足IK親", "LegIKP.L", 'ＩＫ'),
        Item("左足ＩＫ", "LegIK.L", "ＩＫ"),
        Item("左つま先ＩＫ", "ToeIK.L", "ＩＫ"),
        Item("左足先ＩＫ", "Toe2IK.L", "ＩＫ"),
        Item("右足IK親", "LegIKP.R", 'ＩＫ'),
        Item("右足ＩＫ", "LegIK.R", 'ＩＫ'),
        Item("右つま先ＩＫ", "ToeIK.R", "ＩＫ"),
        Item("右足先ＩＫ", "Toe2IK.R", "ＩＫ"),

        Item("上半身", "UpperBody", "体(上)"),
        Item("上半身3", "UpperBody3", "体(上)"),
        Item("上半身2", "UpperBody2", "体(上)"),
        Item("首", "Neck", "体(上)"),
        Item("頭", "Head", "体(上)"),
        Item("左目", "Eye.L", "体(上)"),
        Item("右目", "Eye.R", "体(上)"),
        Item("両目", "Eyes", "体(上)"),

        Item("左肩P", "ShoulderP.L", "腕"),
        Item("左肩", "Shoulder.L", "腕"),
        Item("左腕", "Arm.L", "腕"),
        Item("左腕捩", "ArmTwist.L", "腕"),
        Item("左ひじ", "Elbow.L", "腕"),
        Item("左手捩", "WristTwist.L", "腕"),
        Item("左手首", "Wrist.L", "腕"),
        Item("左ダミー", "Dummy.L", "腕"),
        Item("右肩P", "ShoulderP.R", "腕"),
        Item("右肩", "Shoulder.R", "腕"),
        Item("右腕", "Arm.R", "腕"),
        Item("右腕捩", "ArmTwist.R", "腕"),
        Item("右ひじ", "Elbow.R", "腕"),
        Item("右手捩", "WristTwist.R", "腕"),
        Item("右手首", "Wrist.R", "腕"),
        Item("右ダミー", "Dummy.R", "腕"),

        Item("調整ボーン親", "", ".調整ボーン"),
        Item("センター調整", "", ".調整ボーン"),
        Item("グルーブ調整", "", ".調整ボーン"),
        Item("下半身調整", "", ".調整ボーン"),
        Item("上半身調整", "", ".調整ボーン"),
        Item("上半身2調整", "", ".調整ボーン"),
        Item("首調整", "", ".調整ボーン"),
        Item("頭調整", "", ".調整ボーン"),
        Item("両目調整", "", ".調整ボーン"),
        Item("左肩調整", "", ".調整ボーン"),
        Item("左腕調整", "", ".調整ボーン"),
        Item("左腕捩調整", "", ".調整ボーン"),
        Item("左ひじ調整", "", ".調整ボーン"),
        Item("左手捩調整", "", ".調整ボーン"),
        Item("左手首調整", "", ".調整ボーン"),
        Item("右肩調整", "", ".調整ボーン"),
        Item("右腕調整", "", ".調整ボーン"),
        Item("右腕捩調整", "", ".調整ボーン"),
        Item("右ひじ調整", "", ".調整ボーン"),
        Item("右手捩調整", "", ".調整ボーン"),
        Item("右手首調整", "", ".調整ボーン"),
        Item("左足ＩＫ調整", "", ".調整ボーン"),
        Item("左つま先ＩＫ調整", "", ".調整ボーン"),
        Item("右足ＩＫ調整", "", ".調整ボーン"),
        Item("右つま先ＩＫ調整", "", ".調整ボーン"),

        Item("左親指０", "Thumb0.L", "指"),
        Item("左親指１", "Thumb1.L", "指"),
        Item("左親指２", "Thumb2.L", "指"),
        Item("左人指１", "Index1.L", "指"),
        Item("左人指２", "Index2.L", "指"),
        Item("左人指３", "Index3.L", "指"),
        Item("左中指１", "Middle1.L", "指"),
        Item("左中指２", "Middle2.L", "指"),
        Item("左中指３", "Middle3.L", "指"),
        Item("左薬指１", "Ring1.L", "指"),
        Item("左薬指２", "Ring2.L", "指"),
        Item("左薬指３", "Ring3.L", "指"),
        Item("左小指１", "Little1.L", "指"),
        Item("左小指２", "Little2.L", "指"),
        Item("左小指３", "Little3.L", "指"),
        Item("右親指０", "Thumb0.R", "指"),
        Item("右親指１", "Thumb1.R", "指"),
        Item("右親指２", "Thumb2.R", "指"),
        Item("右人指１", "Index1.R", "指"),
        Item("右人指２", "Index2.R", "指"),
        Item("右人指３", "Index3.R", "指"),
        Item("右中指１", "Middle1.R", "指"),
        Item("右中指２", "Middle2.R", "指"),
        Item("右中指３", "Middle3.R", "指"),
        Item("右薬指１", "Ring1.R", "指"),
        Item("右薬指２", "Ring2.R", "指"),
        Item("右薬指３", "Ring3.R", "指"),
        Item("右小指１", "Little1.R", "指"),
        Item("右小指２", "Little2.R", "指"),
        Item("右小指３", "Little3.R", "指"),

        Item("腰", "Waist", '体(下)'),
        Item("下半身", "LowerBody", "体(下)"),

        Item("左足", "Leg.L", "足"),
        Item("左ひざ", "Knee.L", "足"),
        Item("左足首", "Ankle.L", "足"),
        Item("左足先", "Toe2.L", "足"),
        Item("左つま先", "", "足"),
        Item("右足", "Leg.R", "足"),
        Item("右ひざ", "Knee.R", "足"),
        Item("右足首", "Ankle.R", "足"),
        Item("右足先", "Toe2.R", "足"),
        Item("右つま先", "", "足"),
        Item("左足D", "LegD.L", "足"),
        Item("左ひざD", "KneeD.L", "足"),
        Item("左足首D", "AnkleD.L", "足"),
        Item("左足先EX", "ToeEX.L", "足"),
        Item("右足D", "LegD.R", "足"),
        Item("右ひざD", "KneeD.R", "足"),
        Item("右足首D", "AnkleD.R", "足"),
        Item("右足先EX", "ToeEX.R", "足"),

        Item("足.親指1.L", "BigToe1.L", "足指"),
        Item("足.親指2.L", "BigToe2.L", "足指"),
        Item("足.人差指1.L", "SecondToe1.L", "足指"),
        Item("足.人差指2.L", "SecondToe2.L", "足指"),
        Item("足.中指1.L", "ThirdToe1.L", "足指"),
        Item("足.中指2.L", "ThirdToe2.L", "足指"),
        Item("足.薬指1.L", "FourthToe1.L", "足指"),
        Item("足.薬指2.L", "FourthToe2.L", "足指"),
        Item("足.小指1.L", "LittleToe1.L", "足指"),
        Item("足.小指2.L", "LittleToe2.L", "足指"),
        Item("足.親指1.R", "BigToe1.R", "足指"),
        Item("足.親指2.R", "BigToe2.R", "足指"),
        Item("足.人差指1.R", "SecondToe1.R", "足指"),
        Item("足.人差指2.R", "SecondToe2.R", "足指"),
        Item("足.中指1.R", "ThirdToe1.R", "足指"),
        Item("足.中指2.R", "ThirdToe2.R", "足指"),
        Item("足.薬指1.R", "FourthToe1.R", "足指"),
        Item("足.薬指2.R", "FourthToe2.R", "足指"),
        Item("足.小指1.R", "LittleToe1.R", "足指"),
        Item("足.小指2.R", "LittleToe2.R", "足指"),
    ]


def get_common_frame_names():
    return {
        "センター": "Center",
        "ＩＫ": "IK",
        "体(上)": "Upper Body",
        "腕": "Arm",
        "_調整ボーン": "",
        "指": "Finger",
        "体(下)": "Lower Body",
        "足": "Leg",
        "足指": "Toe",
        "物理": "Physics",
        "その他": "Others",
    }


# -------------------------------------------------------------
# 特定用途骨骼
# -------------------------------------------------------------
# 用于烘焙VMD动作的MMD骨骼
# 名称取自MMR preset.json文件（上半身3并非MMD标准骨或次标准骨，但在预设文件中存在）
PMX_BAKE_BONES = ['全ての親', 'センター',
                  '左足ＩＫ', '左つま先ＩＫ', '右足ＩＫ', '右つま先ＩＫ',
                  '上半身', '上半身3', '上半身2', '首', '頭', '左目', '右目',
                  '左肩', '左腕', '左腕捩', '左ひじ', '左手捩', '左手首',
                  '右肩', '右腕', '右腕捩', '右ひじ', '右手捩', '右手首',
                  '左親指０', '左親指１', '左親指２', '左人指１', '左人指２', '左人指３', '左中指１', '左中指２', '左中指３',
                  '左薬指１', '左薬指２', '左薬指３', '左小指１', '左小指２', '左小指３',
                  '右親指０', '右親指１', '右親指２', '右人指１', '右人指２', '右人指３', '右中指１', '右中指２', '右中指３',
                  '右薬指１', '右薬指２', '右薬指３', '右小指１', '右小指２', '右小指３',
                  '下半身',
                  '左足', '左ひざ', '左足首', '左足先EX', '右足', '右ひざ', '右足首', '右足先EX']

# -------------------------------------------------------------
# 翻译配对
# -------------------------------------------------------------
# 表情名称
morph_name_map = {
    # Mouth
    'あ': 'Ah',
    'い': 'I',
    'う': 'U',
    'え': 'E',
    'お': 'O',
    'ワ': 'Wa',
    'ん': 'Hmm',
    '~': '~',
    'ω': '(w)',
    '∧': '^',
    '∨': 'v',
    '▲': 'Triangle',
    '▼': 'InvTriangle',
    'にやり': "Smirk",
    'にっこり': "SmileV",
    'ぺろっ': "TongueOut",
    'てへぺろ': "Tehepero",
    # Brow
    '真面目': 'Serious',
    '困る': 'Troubled',
    'にこり': 'Cheerful',
    '怒り': 'Angry',
    '恥ずかしい': 'Shy',
    '悲しむ': 'Sad',
    '悲しい': 'Sad',
    # Eyes
    'まばたき': 'Blink',
    '笑い': 'Happy',
    'ウィンク': 'Wink',
    'なごみ': '-_-',
    'はぅ': '>_<',
    'びっくり': 'Surprise',
    'じと目': 'Doubt',
    'キリッ': 'Sharp',
    'ハイライト': 'EyeLight',
    '映り込み': 'Reflections',
    '恐ろしい子!': 'Pupils-',
    'はちゅ目': 'O_O',
    '星目': 'Sparkle',
    'ハート': 'Heart',
    'はぁと': 'Heart',
    # Other
    'ガーン': 'Gloom',
    'メガネ': 'Eyeglasses',
    '青ざめ': 'Pale',
    '青ざめる': 'Pale',
    '髪影': 'HairShadow',
    '照れ': 'Blush',
    '脸红': 'Blush',
    'ねこみみ': 'CatEar',
    # 常见名词（通常与其他词组合出现）
    "口角": "Lip",
    "口": "Mouth",
    "舌": "Tongue",
    '眼角': 'EyeCorner',
    '眼': 'Eye',
    '目': 'Eye',
    '眉': 'Eyebrow',
    '涙': 'Tears',
    '歯': 'Teeth',
    '汗': 'Sweat',
    '胸': 'Breast',
    '乳': 'Boob',
    'おっぱい': 'Tits',
    '腹': 'Belly',
    '袖': 'Sleeve',
    '服': 'Cloth',
    '羽': 'Wing',
    '尾': 'Tail',
    '尻': 'Butt',
    '瞳孔': 'Pupil',
    '瞳': 'Pupil',
    '光': 'EyeLight',
    'モデル': 'Model',
    'スフィア': 'Spa',
    # 组合词（非前后缀）
    '上左': 'Up.L',
    '上右': 'Up.R',
    '下左': 'Down.L',
    '下右': 'Down.R',
    '前左': 'Front.L',
    '前右': 'Front.R',
    '后左': 'Back.L',
    '后右': 'Back.R',
    # PE自动生成词
    'モーフ': 'Morph',
    'ボーン': 'Bone',
    '材質': 'Material',
}

# 通用前缀后缀
morph_affixation_map = OrderedDict({
    "縦潰れ": "CollapsedV",
    "横潰れ": "CollapsedH",
    "横広げ": "Wide",
    "横狭め": "Narrow",
    "横缩げ": "Narrow",
    "広げ": "Wide",
    "狭め": "Narrow",
    "OFF": "-",
    "off": "-",
    "Off": "-",
    "ON": "+",
    "on": "+",
    "On": "+",

    '後ろ': 'Behind',
    '上げ': 'Up',
    '下げ': 'Down',
    '消し': '-',
    "無し": "-",
    "出し": "Out",

    '右': 'Right',
    '左': 'Left',
    '前': 'Front',
    '後': 'Back',
    '横': 'Side',
    '中': 'Middle',
    '上': 'Upper',
    '下': 'Lower',
    "消": "-",
    "無": "-",
    "大": "Big",
    '小': 'Small',
    '新規': 'New',
})

# 前缀
morph_prefix_map = morph_affixation_map
# 后缀
morph_suffix_map = OrderedDict()
morph_suffix_map.update(morph_affixation_map)
morph_suffix_map.update({
    '上': 'Up',
    '下': 'Down',
})

# -------------------------------------------------------------
# 渲染预览图 - 三视图
# -------------------------------------------------------------
# 临时集合名称与临时对象标记（写入对象自定义属性）
THREE_VIEW_COLLECTION_NAME = "三视图临时集合"
THREE_VIEW_TEMP_FLAG = "three_view_temp"
THREE_VIEW_TEMP_SOURCE = "three_view_source_root"
THREE_VIEW_CLIP_CUBE_NAME = "CLIP_CUBE"
THREE_VIEW_CLIP_MODIFIER_NAME = "CLIP"
THREE_VIEW_CAMERA_NAME = "三视图相机"
# 三视图副本对象名称后缀，最终形如“原名称 副本.001”
THREE_VIEW_COPY_SUFFIX = " 副本"
# Blender 对象名称的字节上限（UTF-8），超出会被截断
OBJECT_NAME_MAX_BYTES = 63
# 渲染预览图取景用的临时包围盒对象（仅“仅可见网格”开启时创建）
PREVIEW_BOUNDS_PROXY_NAME = "PREVIEW_BOUNDS_PROXY"
# 材质 Alpha 判定为“不可见”的阈值
MATERIAL_ALPHA_EPSILON = 1e-6

# 其它不参与身体判断的顶点组
ARM_EXCLUDED_GROUP_NAMES = {'mmd_edge_scale', 'mmd_vertex_order', 'FACE_VERTEX_3'}

# 手臂角度自动求解：粗搜索步长与角度上限（度）
ARM_ANGLE_STEP = 10
ARM_ANGLE_LIMIT = 90

# 横向居中使用的分位中心百分比（去掉两端的稀疏离群几何）
THREE_VIEW_CENTER_PERCENTILE = 2.0
# 特写裁剪立方体的深度余量
THREE_VIEW_CLIP_DEPTH_MARGIN = 1.1
# 相机：布局相机在角色前方的额外距离与裁剪范围余量
THREE_VIEW_CAMERA_DISTANCE_MARGIN = 5.0
THREE_VIEW_CAMERA_CLIP_MARGIN = 10.0
# 无「頭」顶点组时，按模型高度估算的头部高度比例
THREE_VIEW_HEAD_FALLBACK_RATIO = 1 / 6
# 仅特写时原模型右移出相机视野的额外间距（相对画面宽度）
THREE_VIEW_OFFSCREEN_GAP = 0.1
