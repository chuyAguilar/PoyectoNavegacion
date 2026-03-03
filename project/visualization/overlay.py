import cv2
import numpy as np


def draw_marker_info(frame, marker_id, translation_vec):

    x_mm = translation_vec[0] * 1000.0
    y_mm = translation_vec[1] * 1000.0
    z_mm = translation_vec[2] * 1000.0

    text = f"ID {marker_id} | X:{x_mm:.1f} Y:{y_mm:.1f} Z:{z_mm:.1f} mm"

    cv2.putText(
        frame,
        text,
        (50, 80 + 50 * marker_id),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )


def draw_relative_distance(frame, transforms):

    if 0 in transforms and 1 in transforms:
        p0 = transforms[0]
        p1 = transforms[1]

        dist_mm = np.linalg.norm(p0 - p1) * 1000.0

        cv2.putText(
            frame,
            f"Dist 0-1: {dist_mm:.1f} mm",
            (50, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 255),
            2,
        )
