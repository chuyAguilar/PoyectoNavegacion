def smooth_vector(marker_id, current_vec, storage, alpha):
    if marker_id in storage:
        smoothed = alpha * storage[marker_id] + (1 - alpha) * current_vec
    else:
        smoothed = current_vec

    storage[marker_id] = smoothed
    return smoothed
