import os
import cv2
from PIL import Image
import imagehash


def process_and_deduplicate_video(
    video_path: str,
    fps_target: int = 2,
    threshold: int = 10,
    output_dir: str = "temp_frames",
) -> list[dict]:
    os.makedirs(output_dir, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    original_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = max(1, int(original_fps / fps_target))

    unique_keyframes = []
    previous_hash = None
    frame_idx = 0

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        if frame_idx % frame_interval == 0:
            timestamp = round(frame_idx / original_fps, 2)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            current_hash = imagehash.phash(pil_image)

            if previous_hash is None or (current_hash - previous_hash) > threshold:
                frame_path = os.path.join(output_dir, f"frame_{timestamp}.jpg")
                cv2.imwrite(frame_path, frame)
                unique_keyframes.append({
                    "timestamp": timestamp,
                    "filepath": frame_path,
                    "hash": str(current_hash),
                })
                previous_hash = current_hash

        frame_idx += 1

    cap.release()
    return unique_keyframes
