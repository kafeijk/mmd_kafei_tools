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
# 临时集合名称
TMP_COLLECTION_NAME = "KAFEI临时集合"
# 默认精度
PRECISION = 0.0001
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
    # todo 暂时采用硬编码的方式，之后考虑如何让用户方便的修改预设值
    return [
        Item("操作中心", "view cnt", 'Root'),

        Item("全ての親", "root", 'センター'),
        Item("センター", "center", "センター"),
        Item("グルーブ", "groove", 'センター'),

        Item("左足IK親", "leg IKP_L", 'ＩＫ'),
        Item("左足ＩＫ", "leg IK_L", "ＩＫ"),
        Item("左つま先ＩＫ", "toe IK_L", "ＩＫ"),
        Item("左足先ＩＫ", "toe2 IK_L", "ＩＫ"),
        Item("右足IK親", "leg IKP_R", 'ＩＫ'),
        Item("右足ＩＫ", "leg IK_R", 'ＩＫ'),
        Item("右つま先ＩＫ", "toe IK_R", "ＩＫ"),
        Item("右足先ＩＫ", "toe2 IK_R", "ＩＫ"),

        Item("上半身", "upper body", "体(上)"),
        Item("上半身3", "upper body", "体(上)"),
        Item("上半身2", "upper body", "体(上)"),
        Item("首", "neck", "体(上)"),
        Item("頭", "head", "体(上)"),
        Item("左目", "eye_L", "体(上)"),
        Item("右目", "eye_R", "体(上)"),
        Item("両目", "eyes", "体(上)"),

        Item("左肩P", "shoulderP_L", "腕"),
        Item("左肩", "shoulder_L", "腕"),
        Item("左腕", "arm_L", "腕"),
        Item("左腕捩", "arm twist_L", "腕"),
        Item("左ひじ", "elbow_L", "腕"),
        Item("左手捩", "wrist twist_L", "腕"),
        Item("左手首", "wrist_L", "腕"),
        Item("左ダミー", "dummy_L", "腕"),
        Item("右肩P", "shoulderP_R", "腕"),
        Item("右肩", "shoulder_R", "腕"),
        Item("右腕", "arm_R", "腕"),
        Item("右腕捩", "arm twist_R", "腕"),
        Item("右ひじ", "elbow_R", "腕"),
        Item("右手捩", "wrist twist_R", "腕"),
        Item("右手首", "wrist_R", "腕"),
        Item("右ダミー", "dummy_R", "腕"),

        Item("調整ボーン親", "", "_調整ボーン"),
        Item("センター調整", "", "_調整ボーン"),
        Item("グルーブ調整", "", "_調整ボーン"),
        Item("下半身調整", "", "_調整ボーン"),
        Item("上半身調整", "", "_調整ボーン"),
        Item("上半身2調整", "", "_調整ボーン"),
        Item("首調整", "", "_調整ボーン"),
        Item("頭調整", "", "_調整ボーン"),
        Item("両目調整", "", "_調整ボーン"),
        Item("左肩調整", "", "_調整ボーン"),
        Item("左腕調整", "", "_調整ボーン"),
        Item("左腕捩調整", "", "_調整ボーン"),
        Item("左ひじ調整", "", "_調整ボーン"),
        Item("左手捩調整", "", "_調整ボーン"),
        Item("左手首調整", "", "_調整ボーン"),
        Item("右肩調整", "", "_調整ボーン"),
        Item("右腕調整", "", "_調整ボーン"),
        Item("右腕捩調整", "", "_調整ボーン"),
        Item("右ひじ調整", "", "_調整ボーン"),
        Item("右手捩調整", "", "_調整ボーン"),
        Item("右手首調整", "", "_調整ボーン"),
        Item("左足ＩＫ調整", "", "_調整ボーン"),
        Item("左つま先ＩＫ調整", "", "_調整ボーン"),
        Item("右足ＩＫ調整", "", "_調整ボーン"),
        Item("右つま先ＩＫ調整", "", "_調整ボーン"),

        Item("左親指０", "", "指"),
        Item("左親指１", "thumb1_L", "指"),
        Item("左親指２", "thumb2_L", "指"),
        Item("左人指１", "fore1_L", "指"),
        Item("左人指２", "fore2_L", "指"),
        Item("左人指３", "fore3_L", "指"),
        Item("左中指１", "middle1_L", "指"),
        Item("左中指２", "middle2_L", "指"),
        Item("左中指３", "middle3_L", "指"),
        Item("左薬指１", "third1_L", "指"),
        Item("左薬指２", "third2_L", "指"),
        Item("左薬指３", "third3_L", "指"),
        Item("左小指１", "little1_L", "指"),
        Item("左小指２", "little2_L", "指"),
        Item("左小指３", "little3_L", "指"),
        Item("右親指０", "", "指"),
        Item("右親指１", "thumb1_R", "指"),
        Item("右親指２", "thumb2_R", "指"),
        Item("右人指１", "fore1_R", "指"),
        Item("右人指２", "fore2_R", "指"),
        Item("右人指３", "fore3_R", "指"),
        Item("右中指１", "middle1_R", "指"),
        Item("右中指２", "middle2_R", "指"),
        Item("右中指３", "middle3_R", "指"),
        Item("右薬指１", "third1_R", "指"),
        Item("右薬指２", "third2_R", "指"),
        Item("右薬指３", "third3_R", "指"),
        Item("右小指１", "little1_R", "指"),
        Item("右小指２", "little2_R", "指"),
        Item("右小指３", "little3_R", "指"),

        Item("腰", "waist", '体(下)'),
        Item("下半身", "lower body", "体(下)"),

        Item("左足", "leg_L", "足"),
        Item("左ひざ", "knee_L", "足"),
        Item("左足首", "ankle_L", "足"),
        Item("左足先", "toe2_L", "足"),
        Item("左つま先", "", "足"),
        Item("右足", "leg_R", "足"),
        Item("右ひざ", "knee_R", "足"),
        Item("右足首", "ankle_R", "足"),
        Item("右足先", "toe2_R", "足"),
        Item("右つま先", "", "足"),
        Item("左足D", "", "足"),
        Item("左ひざD", "", "足"),
        Item("左足首D", "", "足"),
        Item("左足先EX", "", "足"),
        Item("右足D", "", "足"),
        Item("右ひざD", "", "足"),
        Item("右足首D", "", "足"),
        Item("右足先EX", "", "足"),

        Item("足_親指1.L", "Toe_Thumb1.L", "足指"),
        Item("足_親指2.L", "Toe_Thumb2.L", "足指"),
        Item("足_人差指1.L", "Toe_IndexFinger1.L", "足指"),
        Item("足_人差指2.L", "Toe_IndexFinger2.L", "足指"),
        Item("足_中指1.L", "Toe_MiddleFinger1.L", "足指"),
        Item("足_中指2.L", "Toe_MiddleFinger2.L", "足指"),
        Item("足_薬指1.L", "Toe_RingFinger1.L", "足指"),
        Item("足_薬指2.L", "Toe_RingFinger2.L", "足指"),
        Item("足_小指1.L", "Toe_LittleFinger1.L", "足指"),
        Item("足_小指2.L", "Toe_LittleFinger2.L", "足指"),
        Item("足_親指1.R", "Toe_Thumb1.R", "足指"),
        Item("足_親指2.R", "Toe_Thumb2.R", "足指"),
        Item("足_人差指1.R", "Toe_IndexFinger1.R", "足指"),
        Item("足_人差指2.R", "Toe_IndexFinger2.R", "足指"),
        Item("足_中指1.R", "Toe_MiddleFinger1.R", "足指"),
        Item("足_中指2.R", "Toe_MiddleFinger2.R", "足指"),
        Item("足_薬指1.R", "Toe_RingFinger1.R", "足指"),
        Item("足_薬指2.R", "Toe_RingFinger2.R", "足指"),
        Item("足_小指1.R", "Toe_LittleFinger1.R", "足指"),
        Item("足_小指2.R", "Toe_LittleFinger2.R", "足指"),
    ]


def get_common_frame_names():
    return ["センター", "ＩＫ", "体(上)", "腕", "_調整ボーン", "指", "体(下)", "足", "足指", "物理", "その他"]


# -------------------------------------------------------------
# 特定用途骨骼
# -------------------------------------------------------------
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
                  # 足骨 -> 足D骨
                  '左足D', '左ひざD', '左足首D', '左足先EX', '右足D', '右ひざD', '右足首D', '右足先EX']