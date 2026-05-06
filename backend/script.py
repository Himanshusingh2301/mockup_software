
import json
import os

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import label

# ===== CONFIG =====
# api.py sets these via env when running per-workspace users; defaults keep CLI/local runs working.
INPUT_FOLDER = os.environ.get("MOCKGENERATOR_INPUT_FOLDER") or "input_images"
OUTPUT_FOLDER = os.environ.get("MOCKGENERATOR_OUTPUT_FOLDER") or "output"
MOCKUPS_FOLDER = os.environ.get("MOCKGENERATOR_MOCKUPS_FOLDER") or "mockups"
TEMPLATE_CONFIG_PATH = os.environ.get("MOCKGENERATOR_TEMPLATE_CONFIG") or "template_config.json"
INTERNAL_RENDER_SCALE = 2

# --- Template model (preferred) ---
#   mode: "simple"   — clean placeholder only; composite with quad polygon (no paper-mask alpha).
#   mode: "overlay" — hands / occlusion on paper; composite with detected white-paper mask + optional
#                    paper_edge_blend (anti-grey fringe; only affects mask-edge blend, not inner art).
#   card_geometry: "quad"       — perspective warp using minAreaRect corners (flat or tilted).
#   card_geometry: "axis_rect" — axis-aligned bbox only (good for flat, front-on mockups; faster).
#   fit: "contain" | "cover"   — letterbox vs fill (cover crops; use cover_anchor top/center/bottom).
#   cover_anchor: "top" | "center" | "bottom" — only for fit=cover (where to crop).
#
# White detection: defaults match the original strict pass. When that finds nothing, the detector
# automatically retries with relaxed rules (rounded tablets, fragmented screens, edge-touching cards).
# Disable auto-retries with white_detection_auto_relax: false and set min_* explicitly (expert mode).
# Optional overrides still tune the *first* attempt: white_threshold, min_rectangularity, min_area_frac,
# white_close_iters, allow_touch_border, aspect_ratio_* .

# Legacy `use_case` is still accepted and mapped here:
#   contain_rect -> simple + axis_rect
#   quad_white_mask -> overlay + quad
#   cover_quad_top / anything else -> simple + quad (cover_quad_top also forces fit=cover, anchor=top
#   unless you set mode/card_geometry/fit explicitly).

# If template_config.json exists, it overrides this list.

# {
#   "id": "overlay_hands_example",
#   "template_path": "mockups/01.png",
#   "mode": "overlay",
#   "card_geometry": "quad",
#   "fit": "cover",
#   "cover_anchor": "center",
#   "white_threshold": 240,
#   "mask_expand_px": 2,
#   "mask_feather_px": 0.8,
#   "white_mask_feather_px": 0.8,
#   "white_mask_erode_iters": 0,
#   "paper_edge_blend": True,
#   "paper_edge_blend_min_alpha": 0.00392156862745098,
#   "mask_align_quad_x": True,
#   "mask_align_use_centroid": True,
#   "mask_align_flip_x": False,
#   "cover_offset_x": 0,
#   "cover_offset_y": 0,
#   "render_scale": 2
# }

# {
#   "id": "simple_flat_example",
#   "template_path": "mockups/02.png",
#   "mode": "simple",
#   "card_geometry": "axis_rect",
#   "fit": "contain",
#   "cover_anchor": "center",
#   "white_threshold": 240,
#   "mask_expand_px": 2,
#   "mask_feather_px": 0.8,
#   "render_scale": 2
# }


# {
#   "id": "simple_tilted_example",
#   "template_path": "mockups/02.png",
#   "mode": "simple",
#   "card_geometry": "quad",
#   "fit": "contain",
#   "cover_anchor": "center",
#   "white_threshold": 240,
#   "mask_expand_px": 2,
#   "mask_feather_px": 0.8,
#   "cover_offset_x": 0,
#   "cover_offset_y": 0,
#   "render_scale": 2
# }

DEFAULT_TEMPLATES = [
{
  "id": "overlay_hands_example",
  "template_path": "mockups/01.png",
  "mode": "overlay",
  "card_geometry": "quad",
  "fit": "cover",
  "cover_anchor": "center",
  "white_threshold": 240,
  "mask_expand_px": 2,
  "mask_feather_px": 0.8,
  "white_mask_feather_px": 0.8,
  "white_mask_erode_iters": 0,
  "paper_edge_blend": True,
  "paper_edge_blend_min_alpha": 0.00392156862745098,
  "mask_align_quad_x": True,
  "mask_align_use_centroid": True,
  "mask_align_flip_x": False,
  "cover_offset_x": 0,
  "cover_offset_y": 0,
  "render_scale": 2
}
]


def is_image_file(name):
    return name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))


def resolve_template_path(template_path):
    """Resolve template file: exact path, then basename in cwd, then mockups-dir/basename."""
    if os.path.isfile(template_path):
        return template_path
    base = os.path.basename(template_path)
    if os.path.isfile(base):
        return base
    alt = os.path.join(MOCKUPS_FOLDER, base)
    if os.path.isfile(alt):
        return alt
    raise FileNotFoundError(
        f"Template not found: {template_path!r} (tried {base!r}, {alt!r})"
    )


def mockup_file_key(template_path_resolved):
    """Short unique-ish name from template path for output filename (no folders)."""
    root, _ = os.path.splitext(os.path.basename(template_path_resolved))
    return root


def load_templates():
    config_path = TEMPLATE_CONFIG_PATH
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, list):
            raise ValueError("template_config.json must contain a JSON array.")
        return loaded
    return DEFAULT_TEMPLATES


def resolve_render_config(spec):
    """
    Normalize template dict into mode (simple|overlay), geometry (quad|axis_rect), fit, cover_anchor.
    Prefers explicit `mode` / `card_geometry`; falls back to legacy `use_case`.
    """
    use_case = str(spec.get("use_case", "")).strip().lower()
    mode_raw = spec.get("mode")
    if mode_raw is not None:
        mode = str(mode_raw).strip().lower()
        if mode not in ("simple", "overlay"):
            raise ValueError(f'template "mode" must be "simple" or "overlay", got {mode_raw!r}')
    elif use_case == "quad_white_mask":
        mode = "overlay"
    else:
        mode = "simple"

    geom_raw = spec.get("card_geometry")
    if geom_raw is None:
        geom_raw = spec.get("geometry")
    using_new_geometry = geom_raw is not None

    if geom_raw is not None:
        g = str(geom_raw).strip().lower()
        if g in ("rect", "flat", "axis", "axis_aligned", "axis_rect"):
            geometry = "axis_rect"
        elif g == "quad":
            geometry = "quad"
        else:
            raise ValueError(
                f'template "card_geometry" must be "quad" or "axis_rect" (aliases: rect, flat), got {geom_raw!r}'
            )
    elif use_case == "contain_rect":
        geometry = "axis_rect"
    else:
        geometry = "quad"

    fit = str(spec.get("fit", "contain")).strip().lower()
    if fit not in ("contain", "cover"):
        raise ValueError(f'template "fit" must be "contain" or "cover", got {fit!r}')
    cover_anchor = str(spec.get("cover_anchor", "center")).strip().lower()
    if cover_anchor not in ("top", "bottom", "center"):
        cover_anchor = "center"

    # Legacy: cover_quad_top meant cover + top unless user opted into the new keys.
    legacy_uc = use_case == "cover_quad_top"
    if legacy_uc and spec.get("mode") is None and not using_new_geometry:
        fit = "cover"
        cover_anchor = "top"

    return {
        "mode": mode,
        "geometry": geometry,
        "fit": fit,
        "cover_anchor": cover_anchor,
        "legacy_use_case": use_case or None,
    }


def resize_contain(image_np, target_w, target_h):
    src_h, src_w = image_np.shape[:2]
    scale = min(target_w / max(src_w, 1), target_h / max(src_h, 1))
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    # Preserve text clarity: cubic for upscaling, area for downscaling.
    if scale >= 1.0:
        interp = cv2.INTER_CUBIC
    else:
        interp = cv2.INTER_AREA
    resized = cv2.resize(image_np, (new_w, new_h), interpolation=interp)
    x = int(round((target_w - new_w) / 2.0))
    y = int(round((target_h - new_h) / 2.0))
    return resized, x, y


def resize_cover_anchor(
    image_np, target_w, target_h, anchor="center", offset_x=0, offset_y=0
):
    src_h, src_w = image_np.shape[:2]
    src_aspect = src_w / max(src_h, 1)
    dst_aspect = target_w / max(target_h, 1)

    if src_aspect > dst_aspect:
        new_h = target_h
        new_w = int(round(new_h * src_aspect))
    else:
        new_w = target_w
        new_h = int(round(new_w / src_aspect))

    resized = cv2.resize(image_np, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    if anchor == "top":
        y0 = 0
    elif anchor == "bottom":
        y0 = max(new_h - target_h, 0)
    else:
        y0 = max(int(round((new_h - target_h) / 2.0)), 0)
    x0 = max(int(round((new_w - target_w) / 2.0)), 0)
    x0 = int(np.clip(x0 + int(offset_x), 0, max(new_w - target_w, 0)))
    y0 = int(np.clip(y0 + int(offset_y), 0, max(new_h - target_h, 0)))
    return resized[y0 : y0 + target_h, x0 : x0 + target_w]


def order_points(pts):
    pts = np.array(pts, dtype=np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def quad_size(quad):
    quad = order_points(quad)
    tl, tr, br, bl = quad
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    # Average opposite edges (minAreaRect pairs can differ by ~1px); max() biased aspect → lateral drift.
    w = int(round((width_a + width_b) / 2.0))
    h = int(round((height_a + height_b) / 2.0))
    return max(1, w), max(1, h)


def nudge_quad_horizontal_to_mask(
    mask_u8, quad, img_w, max_abs_px=None, use_centroid=True, flip_x=False
):
    """
    Translate quad horizontally so its center matches the mask (centroid or AABB center) vs the
    minAreaRect center. Occluded / tilted cards can make this drift; set flip_x if the nudge
    goes the wrong way for a given mockup.
    """
    m = (mask_u8 > 127).astype(np.uint8)
    ys, xs = np.where(m > 0)
    if xs.size == 0:
        return np.asarray(quad, dtype=np.float32)
    if use_centroid:
        M = cv2.moments(m)
        if M["m00"] > 0:
            mask_cx = float(M["m10"] / M["m00"])
        else:
            mask_cx = (float(xs.min()) + float(xs.max())) / 2.0
    else:
        mask_cx = (float(xs.min()) + float(xs.max())) / 2.0
    q = order_points(np.asarray(quad, dtype=np.float32))
    quad_cx = float(q[:, 0].mean())
    dx = mask_cx - quad_cx
    if flip_x:
        dx = -dx
    lim = float(max_abs_px if max_abs_px is not None else 0.05 * float(img_w))
    dx = float(np.clip(dx, -lim, lim))
    out = q.copy()
    out[:, 0] += dx
    out[:, 0] = np.clip(out[:, 0], 0.0, float(img_w - 1))
    return out


def quad_from_axis_rect(rect):
    """Axis-aligned rectangle [x, y, w, h] -> 4 corner points (ordered)."""
    x, y, w, h = [float(v) for v in rect]
    x2 = x + w - 1.0
    y2 = y + h - 1.0
    pts = np.array([[x, y], [x2, y], [x2, y2], [x, y2]], dtype=np.float32)
    return order_points(pts)


def bbox_from_mask(mask_np):
    ys, xs = np.where(mask_np > 0)
    if ys.size == 0 or xs.size == 0:
        raise RuntimeError("Detected mask is empty.")
    left, right = int(xs.min()), int(xs.max())
    top, bottom = int(ys.min()), int(ys.max())
    return [left, top, right - left + 1, bottom - top + 1]


def detect_corners_and_rect(mask_np, image_w, image_h):
    contours, _ = cv2.findContours(mask_np.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise RuntimeError("No contour found in detected white region.")

    cnt = max(contours, key=cv2.contourArea)
    min_rect = cv2.minAreaRect(cnt)
    corners = order_points(cv2.boxPoints(min_rect))

    xs = np.clip(corners[:, 0], 0, image_w - 1)
    ys = np.clip(corners[:, 1], 0, image_h - 1)
    left, right = int(np.floor(xs.min())), int(np.ceil(xs.max()))
    top, bottom = int(np.floor(ys.min())), int(np.ceil(ys.max()))
    rect = [left, top, max(1, right - left + 1), max(1, bottom - top + 1)]
    return corners, rect


# Extra detection attempts (merge over the first-attempt params). Used when the strict pass fails.
_WHITE_DETECT_RELAX_STEPS = (
    {
        "min_area_frac": 0.04,
        "min_rectangularity": 0.52,
        "white_close_iters": 2,
        "allow_touch_border": False,
    },
    {
        "min_area_frac": 0.032,
        "min_rectangularity": 0.38,
        "white_close_iters": 2,
        "allow_touch_border": False,
    },
    {
        "min_area_frac": 0.024,
        "min_rectangularity": 0.28,
        "white_close_iters": 3,
        "allow_touch_border": True,
    },
)


def _detect_white_region_mask_once(
    template_rgb_np,
    white_threshold=240,
    min_area_frac=0.05,
    min_rectangularity=0.72,
    aspect_ratio_min=0.35,
    aspect_ratio_max=2.6,
    white_close_iters=0,
    allow_touch_border=False,
):
    """Single-pass white blob picker (strict filtering)."""
    h, w = template_rgb_np.shape[:2]
    white_mask = np.all(template_rgb_np >= white_threshold, axis=2)
    m = (white_mask.astype(np.uint8)) * 255
    if white_close_iters and white_close_iters > 0:
        k = np.ones((3, 3), dtype=np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k, iterations=int(white_close_iters))
    labeled, num_features = label(m > 127)

    best_mask = None
    best_score = 0.0
    min_area = h * w * float(min_area_frac)

    for i in range(1, num_features + 1):
        ys, xs = np.where(labeled == i)
        if ys.size == 0 or xs.size == 0:
            continue
        if not allow_touch_border:
            if ys.min() == 0 or ys.max() == h - 1 or xs.min() == 0 or xs.max() == w - 1:
                continue

        area = float(xs.size)
        if area < min_area:
            continue

        top, bottom = int(ys.min()), int(ys.max())
        left, right = int(xs.min()), int(xs.max())
        bw = max(right - left + 1, 1)
        bh = max(bottom - top + 1, 1)
        rectangularity = area / (bw * bh)
        ratio = bw / bh

        if rectangularity < float(min_rectangularity):
            continue
        if ratio < float(aspect_ratio_min) or ratio > float(aspect_ratio_max):
            continue

        score = area * rectangularity
        if score > best_score:
            component_mask = np.zeros((h, w), dtype=np.uint8)
            component_mask[labeled == i] = 255
            best_mask = component_mask
            best_score = score

    return best_mask


def detect_white_region_mask(
    template_rgb_np,
    white_threshold=240,
    min_area_frac=0.05,
    min_rectangularity=0.72,
    aspect_ratio_min=0.35,
    aspect_ratio_max=2.6,
    white_close_iters=0,
    allow_touch_border=False,
    auto_relax=True,
):
    """
    Pick the best white-paper / white-screen region. First attempt uses the parameters above (same
    defaults as the original single-pass detector). If auto_relax and that fails, retry with a
    built-in chain of looser rules; then a last attempt with a slightly lower white_threshold.
    Set auto_relax=False to use only one manual pass (expert templates).
    """
    first = {
        "white_threshold": int(white_threshold),
        "min_area_frac": float(min_area_frac),
        "min_rectangularity": float(min_rectangularity),
        "aspect_ratio_min": float(aspect_ratio_min),
        "aspect_ratio_max": float(aspect_ratio_max),
        "white_close_iters": int(white_close_iters),
        "allow_touch_border": bool(allow_touch_border),
    }
    if not auto_relax:
        return _detect_white_region_mask_once(template_rgb_np, **first)

    m = _detect_white_region_mask_once(template_rgb_np, **first)
    if m is not None:
        return m

    for step in _WHITE_DETECT_RELAX_STEPS:
        kw = {**first, **step}
        m = _detect_white_region_mask_once(template_rgb_np, **kw)
        if m is not None:
            return m

    thr_lo = max(200, int(white_threshold) - 22)
    if thr_lo < int(white_threshold):
        kw = {**first, **_WHITE_DETECT_RELAX_STEPS[-1], "white_threshold": thr_lo}
        m = _detect_white_region_mask_once(template_rgb_np, **kw)
        if m is not None:
            return m

    return None


def postprocess_mask(mask_np, expand_px=2):
    mask = mask_np.astype(np.uint8)
    close_kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    if expand_px > 0:
        dilate_kernel = np.ones((3, 3), dtype=np.uint8)
        mask = cv2.dilate(mask, dilate_kernel, iterations=int(expand_px))
    return mask


def paper_blend_for_hand_overlay(base_rgb_np, paper_alpha=None):
    """
    Candidate background RGB for quad_white_mask halo fix: near-neutral paper + grey-on-paper shadows
    → white; skin excluded. Caller must only *use* this where the paper mask is active, or light
    backgrounds (e.g. marble) get flattened to white.
    Optional paper_alpha enables fringe-zone refinement at mask gradients.
    """
    lab = cv2.cvtColor(base_rgb_np, cv2.COLOR_RGB2LAB).astype(np.float32)
    la = lab[:, :, 1] - 128.0
    lb = lab[:, :, 2] - 128.0
    chroma = np.sqrt(la * la + lb * lb)
    gray = cv2.cvtColor(base_rgb_np, cv2.COLOR_RGB2GRAY).astype(np.float32)
    mx = np.max(base_rgb_np.astype(np.float32), axis=2)

    # Near-neutral grey (paper + cool shadows); skin/lips usually have higher chroma or warm A.
    neutral = (np.abs(la) <= 12.0) & (np.abs(lb) <= 12.0)
    not_skin = (chroma < 20.0) & (lab[:, :, 1] <= 136.0)

    clean_paper = (mx >= 230.0) & (chroma <= 18.0) & neutral
    paper_shadow = (
        (gray >= 200.0)
        & (gray <= 252.0)
        & (chroma <= 14.0)
        & neutral
    )
    paperish = (clean_paper | paper_shadow) & not_skin

    if paper_alpha is not None:
        pa = np.asarray(paper_alpha, dtype=np.float32)
        gx = cv2.Sobel(pa, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(pa, cv2.CV_32F, 0, 1, ksize=3)
        edge = np.sqrt(gx * gx + gy * gy)
        in_blend = (pa > 0.03) & (pa < 0.97)
        grey_fringe = (
            (gray >= 176.0)
            & (gray <= 250.0)
            & (chroma <= 16.0)
            & neutral
            & not_skin
        )
        paperish = paperish | (in_blend & (edge > 0.012) & grey_fringe)

    bg = base_rgb_np.astype(np.float32)
    pw = np.array([255.0, 255.0, 255.0], dtype=np.float32).reshape(1, 1, 3)
    return np.where(paperish[..., None], pw, bg)


def render_simple(
    base_rgba, user_rgb_np, rect, fit="contain", cover_anchor="center", cover_offset_x=0, cover_offset_y=0
):
    if fit not in ("contain", "cover"):
        raise ValueError("fit must be 'contain' or 'cover'.")
    x, y, w, h = [int(v) for v in rect]
    if fit == "contain":
        placed, off_x, off_y = resize_contain(user_rgb_np, w, h)
        base_rgba.paste(Image.fromarray(placed).convert("RGBA"), (x + off_x, y + off_y))
    else:
        crop = resize_cover_anchor(
            user_rgb_np, w, h, anchor=cover_anchor, offset_x=cover_offset_x, offset_y=cover_offset_y
        )
        base_rgba.paste(Image.fromarray(crop).convert("RGBA"), (x, y))
    return base_rgba


def _perspective_src_quad(warp_w, warp_h):
    """Pixel-center corners (half-pixel inset) to reduce systematic warp bias vs integer edges."""
    off = 0.5
    return np.array(
        [[off, off], [warp_w - off, off], [warp_w - off, warp_h - off], [off, warp_h - off]],
        dtype=np.float32,
    )


def _build_warp_canvas(user_rgb_np, warp_w, warp_h, fit, cover_anchor, cover_offset_x, cover_offset_y):
    """Shared prepare step for perspective warp (contain vs cover). Inner artwork stays sharp (LANCZOS in warp)."""
    if fit == "contain":
        placed, off_x, off_y = resize_contain(user_rgb_np, warp_w, warp_h)
        canvas = np.full((warp_h, warp_w, 3), 255, dtype=np.uint8)
        ph, pw = placed.shape[:2]
        canvas[off_y : off_y + ph, off_x : off_x + pw] = placed
    else:
        canvas = resize_cover_anchor(
            user_rgb_np,
            warp_w,
            warp_h,
            anchor=cover_anchor,
            offset_x=cover_offset_x,
            offset_y=cover_offset_y,
        )
    return canvas


def render_to_quad(
    base_rgba,
    user_rgb_np,
    quad,
    fit="contain",
    feather_px=0.8,
    cover_anchor="center",
    cover_offset_x=0,
    cover_offset_y=0,
):
    if fit not in ("contain", "cover"):
        raise ValueError("fit must be 'contain' or 'cover'.")

    quad = order_points(np.array(quad, dtype=np.float32))
    warp_w, warp_h = quad_size(quad)
    canvas = _build_warp_canvas(
        user_rgb_np, warp_w, warp_h, fit, cover_anchor, cover_offset_x, cover_offset_y
    )

    src = _perspective_src_quad(warp_w, warp_h)
    matrix = cv2.getPerspectiveTransform(src, quad.astype(np.float32))

    warped = cv2.warpPerspective(
        canvas,
        matrix,
        (base_rgba.width, base_rgba.height),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )

    mask = np.zeros((base_rgba.height, base_rgba.width), dtype=np.uint8)
    cv2.fillConvexPoly(mask, quad.astype(np.int32), 255)
    if feather_px > 0:
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=feather_px, sigmaY=feather_px)

    base_rgba.paste(Image.fromarray(warped).convert("RGBA"), (0, 0), Image.fromarray(mask, mode="L"))
    return base_rgba


def render_to_quad_white_mask(
    base_rgba,
    user_rgb_np,
    quad,
    paper_mask_u8,
    base_rgb_np,
    fit="contain",
    feather_px=0.8,
    cover_anchor="center",
    erode_iters=0,
    paper_edge_blend=True,
    paper_edge_blend_min_alpha=1.0 / 255.0,
    cover_offset_x=0,
    cover_offset_y=0,
):
    """Perspective warp + composite using white-paper mask alpha over the template (optional paper fringe fix)."""
    if fit not in ("contain", "cover"):
        raise ValueError("fit must be 'contain' or 'cover'.")

    quad = order_points(np.array(quad, dtype=np.float32))
    warp_w, warp_h = quad_size(quad)
    canvas = _build_warp_canvas(
        user_rgb_np, warp_w, warp_h, fit, cover_anchor, cover_offset_x, cover_offset_y
    )

    src = _perspective_src_quad(warp_w, warp_h)
    matrix = cv2.getPerspectiveTransform(src, quad.astype(np.float32))

    warped = cv2.warpPerspective(
        canvas,
        matrix,
        (base_rgba.width, base_rgba.height),
        flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_REPLICATE,
    )

    paper_mask = paper_mask_u8
    if erode_iters and erode_iters > 0:
        k = np.ones((3, 3), dtype=np.uint8)
        paper_mask = cv2.erode(paper_mask, k, iterations=int(erode_iters))

    paper_alpha = paper_mask.astype(np.float32) / 255.0
    if feather_px > 0:
        paper_alpha = cv2.GaussianBlur(paper_alpha, (0, 0), sigmaX=feather_px, sigmaY=feather_px)
        paper_alpha = np.clip(paper_alpha, 0.0, 1.0)

    a = paper_alpha[..., None]
    warped_f = warped.astype(np.float32)
    base_orig_f = base_rgb_np.astype(np.float32)
    if paper_edge_blend:
        blended = paper_blend_for_hand_overlay(base_rgb_np, paper_alpha)
        # Only use whitened background where the paper mask applies; α≈0 must stay original template
        # (otherwise bright neutral marble behind the card is flattened to white).
        use_blend = paper_alpha > float(paper_edge_blend_min_alpha)
        base_bg_f = np.where(use_blend[..., None], blended, base_orig_f)
    else:
        base_bg_f = base_orig_f
    out_rgb = warped_f * a + base_bg_f * (1.0 - a)
    out_u8 = np.clip(np.round(out_rgb), 0, 255).astype(np.uint8)

    base_rgba.paste(Image.fromarray(out_u8, mode="RGB").convert("RGBA"))
    return base_rgba


def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    templates = load_templates()

    input_files = [n for n in os.listdir(INPUT_FOLDER) if is_image_file(n)]
    if not input_files:
        raise RuntimeError(f"No input images found in {INPUT_FOLDER}")

    generated_count = 0

    for spec in templates:
        raw_template_path = spec["template_path"]
        template_path = resolve_template_path(raw_template_path)
        template_id = spec.get("id", os.path.splitext(os.path.basename(template_path))[0])
        rc = resolve_render_config(spec)
        render_scale = max(1, int(spec.get("render_scale", INTERNAL_RENDER_SCALE)))
        white_threshold = int(spec.get("white_threshold", 240))
        min_area_frac = float(spec.get("min_area_frac", 0.05))
        min_rectangularity = float(spec.get("min_rectangularity", 0.72))
        aspect_ratio_min = float(spec.get("aspect_ratio_min", 0.35))
        aspect_ratio_max = float(spec.get("aspect_ratio_max", 2.6))
        white_close_iters = int(spec.get("white_close_iters", 0))
        allow_touch_border = bool(spec.get("allow_touch_border", False))
        white_detection_auto_relax = bool(spec.get("white_detection_auto_relax", True))
        mask_expand_px = int(spec.get("mask_expand_px", 2))
        feather_px = float(spec.get("mask_feather_px", 0.8))
        white_mask_feather_px = spec.get("white_mask_feather_px")
        white_mask_erode_iters = int(spec.get("white_mask_erode_iters", 0))
        paper_edge_blend = bool(spec.get("paper_edge_blend", True))
        paper_edge_blend_min_alpha = float(spec.get("paper_edge_blend_min_alpha", 1.0 / 255.0))
        mask_align_x = bool(spec.get("mask_align_quad_x", True))
        mask_align_max_px = spec.get("mask_align_max_px")
        mask_align_use_centroid = bool(spec.get("mask_align_use_centroid", True))
        mask_align_flip_x = bool(spec.get("mask_align_flip_x", False))
        cover_offset_x = int(spec.get("cover_offset_x", 0))
        cover_offset_y = int(spec.get("cover_offset_y", 0))

        base_template = Image.open(template_path).convert("RGBA")
        base_rgb_np = np.array(base_template.convert("RGB"))

        mask_np = detect_white_region_mask(
            base_rgb_np,
            white_threshold=white_threshold,
            min_area_frac=min_area_frac,
            min_rectangularity=min_rectangularity,
            aspect_ratio_min=aspect_ratio_min,
            aspect_ratio_max=aspect_ratio_max,
            white_close_iters=white_close_iters,
            allow_touch_border=allow_touch_border,
            auto_relax=white_detection_auto_relax,
        )
        if mask_np is None:
            raise RuntimeError(f"No valid white area detected for template '{template_id}'.")
        mask_np = postprocess_mask(mask_np, expand_px=mask_expand_px)
        corners, rect = detect_corners_and_rect(mask_np, base_template.width, base_template.height)

        work_w = base_template.width * render_scale
        work_h = base_template.height * render_scale
        work_template = base_template if render_scale == 1 else base_template.resize((work_w, work_h), Image.LANCZOS)
        mask_work = mask_np if render_scale == 1 else cv2.resize(mask_np, (work_w, work_h), interpolation=cv2.INTER_NEAREST)
        work_rgb_np = np.array(work_template.convert("RGB"))
        corners_work, rect_work = detect_corners_and_rect(mask_work, work_w, work_h)

        print(
            f"Template [{template_id}] -> mode={rc['mode']}, geometry={rc['geometry']}, "
            f"fit={rc['fit']}, anchor={rc['cover_anchor']}, render_scale={render_scale}x"
        )
        if rc["legacy_use_case"]:
            print(f"  (legacy use_case={rc['legacy_use_case']!r})")
        print(f"  corners: {[(int(x), int(y)) for x, y in corners]}")
        print(f"  rect: x={rect[0]}, y={rect[1]}, w={rect[2]}, h={rect[3]}")
        print(
            "  work corners: "
            f"{[(int(x), int(y)) for x, y in corners_work]}"
        )

        fit = rc["fit"]
        cover_anchor = rc["cover_anchor"]
        mode = rc["mode"]
        geometry = rc["geometry"]

        for file_name in input_files:
            input_path = os.path.join(INPUT_FOLDER, file_name)
            user_rgb_np = np.array(Image.open(input_path).convert("RGB"))

            if geometry == "axis_rect":
                if mode == "simple":
                    output = render_simple(
                        work_template.copy(),
                        user_rgb_np,
                        rect_work,
                        fit=fit,
                        cover_anchor=cover_anchor,
                        cover_offset_x=cover_offset_x,
                        cover_offset_y=cover_offset_y,
                    )
                else:
                    corners_axis = quad_from_axis_rect(rect_work)
                    wfeather = (
                        float(white_mask_feather_px) * render_scale
                        if white_mask_feather_px is not None
                        else feather_px * render_scale
                    )
                    corners_ov = (
                        nudge_quad_horizontal_to_mask(
                            mask_work,
                            corners_axis,
                            work_w,
                            float(mask_align_max_px) if mask_align_max_px is not None else None,
                            use_centroid=mask_align_use_centroid,
                            flip_x=mask_align_flip_x,
                        )
                        if mask_align_x
                        else corners_axis
                    )
                    output = render_to_quad_white_mask(
                        work_template.copy(),
                        user_rgb_np,
                        corners_ov,
                        mask_work,
                        work_rgb_np,
                        fit=fit,
                        feather_px=wfeather,
                        cover_anchor=cover_anchor,
                        erode_iters=white_mask_erode_iters,
                        paper_edge_blend=paper_edge_blend,
                        paper_edge_blend_min_alpha=paper_edge_blend_min_alpha,
                        cover_offset_x=cover_offset_x,
                        cover_offset_y=cover_offset_y,
                    )
            else:
                feather_scaled = feather_px * render_scale
                if mode == "overlay":
                    wfeather = (
                        float(white_mask_feather_px) * render_scale
                        if white_mask_feather_px is not None
                        else feather_scaled
                    )
                    corners_for_warp = (
                        nudge_quad_horizontal_to_mask(
                            mask_work,
                            corners_work,
                            work_w,
                            float(mask_align_max_px) if mask_align_max_px is not None else None,
                            use_centroid=mask_align_use_centroid,
                            flip_x=mask_align_flip_x,
                        )
                        if mask_align_x
                        else corners_work
                    )
                    output = render_to_quad_white_mask(
                        work_template.copy(),
                        user_rgb_np,
                        corners_for_warp,
                        mask_work,
                        work_rgb_np,
                        fit=fit,
                        feather_px=wfeather,
                        cover_anchor=cover_anchor,
                        erode_iters=white_mask_erode_iters,
                        paper_edge_blend=paper_edge_blend,
                        paper_edge_blend_min_alpha=paper_edge_blend_min_alpha,
                        cover_offset_x=cover_offset_x,
                        cover_offset_y=cover_offset_y,
                    )
                else:
                    output = render_to_quad(
                        work_template.copy(),
                        user_rgb_np,
                        corners_work,
                        fit=fit,
                        feather_px=feather_scaled,
                        cover_anchor=cover_anchor,
                        cover_offset_x=cover_offset_x,
                        cover_offset_y=cover_offset_y,
                    )
            if render_scale > 1:
                output = output.resize((base_template.width, base_template.height), Image.LANCZOS)

            input_stem = os.path.splitext(os.path.basename(file_name))[0]
            mockup_key = mockup_file_key(template_path)
            input_output_dir = os.path.join(OUTPUT_FOLDER, input_stem)
            os.makedirs(input_output_dir, exist_ok=True)
            out_name = f"{input_stem}_{mockup_key}.png"
            output_path = os.path.join(input_output_dir, out_name)
            output.save(output_path)
            generated_count += 1

    print(f"Generated {generated_count} mockups.")


if __name__ == "__main__":
    main()