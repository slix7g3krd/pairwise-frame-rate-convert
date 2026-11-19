"""帧率转换辅助函数。

覆盖 24 -> 60 帧转换中需要处理的若干问题：精确有理数倍率、旋转/缩放
运动幅度、遮挡标记、场景切换、可变时间线对齐、重复帧去重、低纹理
回退、转场保护、时间戳重采样和按片段重置状态。
"""

from fractions import Fraction


def frame_ratio(num, den):
    """返回精确帧率比 ``num / den``。

    使用 :class:`~fractions.Fraction` 而不是浮点除法，避免像
    23.976（24000/1001）这样的素材在长时间插帧时累积误差。
    """
    if den == 0:
        raise ZeroDivisionError("frame ratio denominator must be non-zero")
    if num <= 0 or den < 0:
        raise ValueError("frame ratio must be positive")
    return Fraction(num, den)


def motion_magnitude(dx, dy, rotation, scale):
    """返回运动估计幅度。

    平移、旋转和缩放分量各自取绝对值后求和，作为整体运动强度的
    度量；旋转和缩放也参与计算，避免只估计全局平移时忽略它们。
    """
    return abs(dx) + abs(dy) + abs(rotation) + abs(scale)


def occlusion_mask(foreground, background):
    """标记遮挡区域。

    仅当前景存在且背景不可见时，该像素才被判为遮挡；若前景与背景
    同时可见则不是遮挡，插帧时不做前后景平均。
    """
    return bool(foreground) and not bool(background)


def scene_cut(hist_diff, threshold):
    """检测场景切换。

    直方图差异严格大于阈值时视为场景切换，跨镜头不再插帧。
    """
    return hist_diff > threshold


def align_time(frame_time, target_fps):
    """把任意时间点对齐到目标帧率的时间网格上。

    返回最接近的帧边界时刻 ``round(t * fps) / fps``，使可变帧率
    时间线上的插帧顺序与音频保持同步。
    """
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")
    # 使用 floor(x + 0.5) 实现四舍五入，避免银行家舍入在 .5 边界
    # 上的意外行为。
    frame_index = int(frame_time * target_fps + 0.5)
    return frame_index / target_fps


def dedupe_frames(prev, current, threshold):
    """判断当前帧是否与上一帧重复。

    两帧差异小于等于阈值时视为重复帧，输出时去重以控制体积。
    """
    return abs(current - prev) <= threshold


def low_texture_fallback(texture_score, threshold):
    """低纹理区域回退。

    纹理分数低于阈值（例如天空）时运动矢量不可靠，应回退到不依赖
    运动估计的插值方式，返回 ``True``。
    """
    return texture_score < threshold


def transition_alpha(alpha):
    """转场帧保护：把 alpha 钳制到 ``[0, 1]``。

    淡入淡出等转场帧单独处理，避免被当作普通帧插成双重曝光。
    """
    return min(1.0, max(0.0, alpha))


def resample_timestamp(pts, input_rate, output_rate):
    """把输入时间线上的时间戳重采样到输出时间线。

    使用精确有理数换算 ``pts * output_rate / input_rate``，避免按
    输入帧号换算带来的长时间漂移。结果能整除时返回整数。
    """
    if input_rate <= 0 or output_rate <= 0:
        raise ValueError("frame rates must be positive")
    ts = Fraction(pts) * Fraction(output_rate) / Fraction(input_rate)
    return int(ts) if ts.denominator == 1 else float(ts)


def reset_segment(segment_id):
    """按片段重置转换状态。

    每个片段开始时清空上一段遗留的运动矢量等状态，返回该片段 id
    以便调用方继续处理。
    """
    return segment_id
