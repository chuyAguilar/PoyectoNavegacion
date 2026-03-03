import os

import cv2

OUTPUT_DIR = "project/calibration/images"


def main():

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    print("Presiona SPACE para capturar imagen.")
    print("Presiona Q para salir.")

    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("Calibration Capture", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord(" "):
            filename = os.path.join(OUTPUT_DIR, f"img_{count:02d}.jpg")
            cv2.imwrite(filename, frame)
            print(f"Guardada {filename}")
            count += 1

        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
