import os
import time
import traceback

import bpy

from .constants import MAX_CONSECUTIVE_FAILURES, TIMER_INTERVAL, TMP_COLLECTION_NAME
from .utils import (
    clean_scene,
    deselect_all_objects,
    export_pmx,
    get_collection,
    import_pmx,
    recursive_search,
    select_and_activate,
    translate,
)


# 批处理进度：放在模块级变量中，避免“处理中”状态被写进 .blend
_BATCH_PROGRESS = {}


def get_batch_progress(task):
    """获取指定任务的批处理进度；面板绘制时使用"""
    return _BATCH_PROGRESS.setdefault(task, {
        "active": False, "factor": 0.0, "text": "", "current": 0, "total": 0,
    })


def set_batch_progress(task, active, factor=0.0, text="", current=0, total=0):
    """更新批处理进度；active=False 表示结束，面板不再绘制进度条"""
    state = get_batch_progress(task)
    state["active"] = bool(active)
    state["factor"] = min(max(float(factor), 0.0), 1.0)
    state["text"] = text
    state["current"] = current
    state["total"] = total


def tag_redraw(context):
    """标记 3D 视图重画，让侧边栏中的进度条及时刷新"""
    window = getattr(context, "window", None)
    if window is None or window.screen is None:
        return
    for area in window.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


class BatchProcessRunner:
    """可复用的批处理执行器：同步循环或由 modal 逐文件调用"""

    def __init__(self, func, props, f_flag=False, task=None):
        self.func = func
        self.props = props
        self.f_flag = f_flag
        self.task = task

        batch = props.batch
        self.abs_path = bpy.path.abspath(batch.directory)
        self.suffix = batch.suffix
        self.file_list = self.search_files()
        self.file_count = len(self.file_list)
        self.file_index = 0
        self.failed_files = []
        self.consecutive_failures = 0
        self.aborted = False
        self.start_time = time.time()

    def search_files(self):
        """获取待处理文件列表；子类可覆盖以支持不同的文件类型"""
        batch = self.props.batch
        return recursive_search(
            self.abs_path,
            batch.suffix,
            batch.threshold,
            batch.search_strategy,
            batch.conflict_strategy,
        )

    def process_file(self, filepath):
        """处理单个文件；子类可覆盖以支持不同的处理流程"""
        ext = os.path.splitext(filepath)[1].lower()
        if ".pmd" == ext:
            ext = ".pmx"  # 再导出的时候是pmx格式的，如果依然以pmd为后缀，导入PE会报错

        # 如果新文件名已经包含指定后缀，则对原文件进行覆盖
        if os.path.splitext(filepath)[0].endswith(self.suffix):
            new_filepath = os.path.splitext(filepath)[0] + ext
        else:
            new_filepath = os.path.splitext(filepath)[0] + self.suffix + ext

        import_pmx(filepath)
        pmx_root = bpy.context.active_object
        if self.f_flag:
            self.func(pmx_root, self.props, filepath)
        else:
            self.func(pmx_root, self.props)

        deselect_all_objects()
        select_and_activate(pmx_root)
        export_pmx(new_filepath)

    def completed(self):
        return self.aborted or self.file_index >= self.file_count

    def update_progress(self):
        if not self.task:
            return

        total = self.file_count
        if self.file_index < total:
            file_name = os.path.basename(self.file_list[self.file_index])
            current = self.file_index + 1
            text = translate("正在处理：{}").format(file_name)
            factor = current / total
        else:
            current = total
            text = translate("正在完成处理")
            factor = 1.0

        set_batch_progress(self.task, True, factor, text, current, total)
        tag_redraw(bpy.context)

    def step(self):
        """处理一个文件；返回 True 表示全部完成"""
        if self.completed():
            return True

        index = self.file_index
        filepath = self.file_list[index]
        file_base_name = os.path.basename(filepath)

        curr_time = time.time()
        try:
            get_collection(TMP_COLLECTION_NAME)
            self.process_file(filepath)
        except Exception as e:
            # 单个文件失败不影响后续文件，继续处理
            self.failed_files.append(file_base_name)
            self.consecutive_failures += 1
            msg = bpy.app.translations.pgettext_iface(
                "文件 \"{}\" 处理失败，进度 {}/{}：{}").format(
                file_base_name, index + 1, self.file_count, str(e).replace("\n", " ")[:120]
            )
            print(msg)
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                self.aborted = True
        else:
            self.consecutive_failures = 0
            current_time = time.time() - curr_time
            total_time = time.time() - self.start_time
            msg = bpy.app.translations.pgettext_iface(
                "File \"{}\" processing completed, progress {}/{} (elapsed {} seconds, total {} seconds)"
            ).format(
                file_base_name, index + 1, self.file_count,
                f"{current_time:.2f}", f"{total_time:.2f}"
            )
            print(msg)
        finally:
            clean_scene()
            self.file_index += 1
            self.update_progress()

        return self.completed()

    def finish(self):
        total_time = time.time() - self.start_time
        processed_count = self.file_index

        if self.failed_files:
            if len(self.failed_files) >= self.file_count:
                msg = bpy.app.translations.pgettext_iface(
                    "处理结束，用时 {} 秒。{} 个模型全部处理失败。"
                    "可能是模型文件本身的问题，也可能是 mmd_tools 版本不兼容，请检查后重试。"
                ).format(f"{total_time:.2f}", self.file_count)
            elif self.aborted:
                msg = bpy.app.translations.pgettext_iface(
                    "处理结束，用时 {} 秒。已处理 {}/{}，失败 {} 个。连续 {} 个模型处理失败，已停止处理。"
                    "可能是模型文件本身的问题，也可能是 mmd_tools 版本不兼容，请检查后重试。"
                ).format(f"{total_time:.2f}", processed_count, self.file_count,
                         len(self.failed_files), MAX_CONSECUTIVE_FAILURES)
            else:
                msg = bpy.app.translations.pgettext_iface(
                    "处理结束，用时 {} 秒。失败 {}/{}。个别失败通常是模型文件本身的问题，请单独检查这些文件。"
                ).format(f"{total_time:.2f}", len(self.failed_files), self.file_count)
            print(msg)
            # 逐个换行输出失败的模型文件
            for name in self.failed_files:
                print(name)
        else:
            msg = bpy.app.translations.pgettext_iface(
                "Directory \"{}\" processing completed (total {} seconds)"
            ).format(self.abs_path, f"{total_time:.2f}")
            print(msg)

        if self.task:
            set_batch_progress(self.task, False)
            tag_redraw(bpy.context)
        return {'FINISHED'}

    def run_sync(self):
        while not self.step():
            pass
        return self.finish()


class BatchProcessOperatorMixin:
    """让算子以 modal 方式驱动 BatchProcessRunner，并在侧边栏显示进度"""
    batch_task = ""
    batch_f_flag = False
    batch_runner_class = BatchProcessRunner

    def start_batch_process(self, context, props, func):
        self.batch_runner = self.batch_runner_class(func, props, self.batch_f_flag, self.batch_task)
        self.batch_runner.update_progress()

        # 后台模式没有事件循环，直接同步跑完
        if bpy.app.background or self.batch_runner.file_count == 0:
            return self.batch_runner.run_sync()

        self.batch_timer = context.window_manager.event_timer_add(
            TIMER_INTERVAL, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.batch_flush_count = 0
        return {'RUNNING_MODAL'}

    def _end_batch(self, context):
        if getattr(self, "batch_timer", None) is not None:
            context.window_manager.event_timer_remove(self.batch_timer)
            self.batch_timer = None
        if self.batch_task:
            set_batch_progress(self.batch_task, False)
            tag_redraw(context)

    def modal(self, context, event):
        if event.type == 'ESC':
            self._end_batch(context)
            self.report({'INFO'}, translate("已取消处理"))
            return {'CANCELLED'}

        if event.type != 'TIMER':
            return {'RUNNING_MODAL'}

        # 进度条所在面板首次展开需要重新布局，先跳过若干次并主动重绘
        if self.batch_flush_count < 20:
            self.batch_flush_count += 1
            tag_redraw(context)
            return {'RUNNING_MODAL'}

        try:
            if self.batch_runner.step():
                self._end_batch(context)
                return self.batch_runner.finish()
        except Exception as e:
            self._end_batch(context)
            traceback.print_exc()
            self.report({'ERROR'}, translate("批量处理发生异常：{}").format(e))
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


def batch_process(func, props, f_flag=False, task=None):
    """同步批处理入口，保留供非 modal 场景复用"""
    return BatchProcessRunner(func, props, f_flag, task).run_sync()
